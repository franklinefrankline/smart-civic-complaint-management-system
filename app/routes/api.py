import json
import time
from flask import Blueprint, jsonify, request, session, g, Response, stream_with_context, current_app
from sqlalchemy import text, func, case
from app import db
from app.models.complaint import Complaint
from app.models.category import ComplaintCategory
from app.models.department import Department
from app.models.user import User
from app.models.notification import Notification
from app.services.complaint_service import (
    find_potential_duplicates,
    suggest_department_by_category,
    build_admin_analytics_payload,
    get_complaint_aggregate_counts,
    PENDING_STATUSES,
    IN_PROGRESS_STATUSES,
)
from app.services.notification_service import mark_as_read, mark_all_as_read
from app.services.sla_service import check_and_escalate_overdue_complaints
from app.services.location_service import reverse_geocode_coordinates
from app.utils.decorators import login_required

api_bp = Blueprint('api', __name__)


@api_bp.route('/health')
def api_health():
    if current_app.config.get('DB_STARTUP_ERROR'):
        return jsonify({
            'status': 'error',
            'service': 'smart-civic-complaint-system',
            'database': 'misconfigured',
            'message': current_app.config['DB_STARTUP_ERROR'],
        }), 503
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'ok',
            'service': 'smart-civic-complaint-system',
            'database': 'connected',
            'dialect': db.engine.dialect.name
        }), 200
    except Exception:
        return jsonify({
            'status': 'degraded',
            'service': 'smart-civic-complaint-system',
            'database': 'disconnected'
        }), 503


@api_bp.route('/stats/summary')
def stats_summary():
    counts = get_complaint_aggregate_counts()
    return jsonify({
        'total': counts['total'],
        'resolved': counts['resolved'],
        'pending': counts['pending'],
        'in_progress': counts['in_progress'],
        'overdue': counts['overdue']
    })


@api_bp.route('/admin/analytics-data')
@login_required
def admin_analytics_data():
    if g.user.role != 'admin':
        return jsonify({'error': 'Administrator access required.'}), 403
    return jsonify(build_admin_analytics_payload())

@api_bp.route('/reverse-geocode', methods=['GET'])
@login_required
def reverse_geocode():
    """Reverse-geocode GPS coordinates into normalized Indian administrative address fields."""
    try:
        lat = float(request.args.get('lat', ''))
        lng = float(request.args.get('lng', ''))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Valid latitude and longitude coordinates are required.'}), 400

    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return jsonify({'success': False, 'message': 'Coordinates are outside valid geographic bounds.'}), 400

    result = reverse_geocode_coordinates(lat, lng)
    status_code = 200 if result.get('success') else 502
    return jsonify(result), status_code


@api_bp.route('/complaints/locations')
def complaint_locations():
    """
    Returns sanitized complaint coordinates.
    Filters by caller's role if logged in.
    Does NOT leak private citizen details.
    """
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None
    
    query = Complaint.query.filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    )
    
    if user:
        if user.role == 'officer' and user.department_id:
            query = query.filter_by(department_id=user.department_id)
        elif user.role == 'worker':
            query = query.join(Complaint.assignments).filter_by(assigned_to_user_id=user.id)
        elif user.role == 'citizen':
            query = query.filter_by(citizen_id=user.id)
    else:
        # Public view: only show non-private high-level points
        query = query.filter(Complaint.status.notin_(['Rejected']))
        
    complaints = query.limit(300).all()
    
    data = []
    for c in complaints:
        data.append({
            'id': c.id,
            'ref': c.complaint_ref,
            'title': c.title,
            'status': c.status,
            'priority': c.priority,
            'category': c.category.name if c.category else 'General',
            'department': c.department.name if c.department else 'Unassigned',
            'latitude': float(c.latitude),
            'longitude': float(c.longitude),
            'address': c.address or c.city or 'Civic Area',
            'created_at': c.created_at.strftime('%Y-%m-%d')
        })
        
    return jsonify({'complaints': data})

@api_bp.route('/complaints/check-duplicate', methods=['POST'])
def check_duplicate():
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    category_id = payload.get('category_id')
    ward_number = payload.get('ward_number')
    street_name = payload.get('street_name')
    locality = payload.get('locality')
    lat = payload.get('latitude')
    lng = payload.get('longitude')
    
    if not category_id:
        return jsonify({'duplicates': [], 'has_duplicates': False})
        
    matches = find_potential_duplicates(
        category_id=category_id,
        ward_number=ward_number,
        street_name=street_name,
        locality=locality,
        latitude=lat,
        longitude=lng
    )
    return jsonify({
        'has_duplicates': len(matches) > 0,
        'duplicates': matches
    })

@api_bp.route('/departments/by-category/<int:category_id>')
def get_department_by_category(category_id):
    dept = suggest_department_by_category(category_id)
    if dept:
        return jsonify({
            'department_id': dept.id,
            'department_name': dept.name,
            'department_code': dept.code
        })
    return jsonify({'department_id': None, 'department_name': None})

@api_bp.route('/notifications')
def get_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'unread_count': 0, 'notifications': []})
        
    notifs = Notification.query.filter_by(user_id=user_id)\
        .order_by(Notification.created_at.desc()).limit(15).all()
        
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    
    return jsonify({
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifs]
    })

@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
def read_notification(notification_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False}), 401
    success = mark_as_read(notification_id, user_id)
    return jsonify({'success': success})

@api_bp.route('/notifications/read-all', methods=['POST'])
def read_all_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False}), 401
    mark_all_as_read(user_id)
    return jsonify({'success': True})

@api_bp.route('/sla/check', methods=['POST'])
def trigger_sla_check():
    """Sweep overdue complaints and trigger auto-escalation"""
    escalated = check_and_escalate_overdue_complaints()
    return jsonify({'status': 'ok', 'escalated_count': escalated})


def _build_user_live_snapshot(user_id, role, department_id, since_notif_id=None):
    """Build strictly user/role-scoped real-time snapshot using combined SQL aggregates."""
    query = Complaint.query

    if role == 'officer' and department_id:
        query = query.filter_by(department_id=department_id).filter(
            (Complaint.assigned_officer_id == user_id) | (Complaint.assigned_officer_id.is_(None))
        )
    elif role == 'officer':
        query = query.filter_by(id=-1)
    elif role == 'worker':
        from app.models.workflow import ComplaintAssignment
        assigned_ids = [
            a.complaint_id
            for a in ComplaintAssignment.query.filter_by(assigned_to_user_id=user_id).all()
        ]
        query = query.filter(Complaint.id.in_(assigned_ids)) if assigned_ids else query.filter_by(id=-1)
    elif role == 'citizen':
        query = query.filter_by(citizen_id=user_id)

    total_row = query.with_entities(
        func.count(Complaint.id).label('total'),
        func.sum(case((Complaint.status.in_(PENDING_STATUSES), 1), else_=0)).label('pending'),
        func.max(Complaint.id).label('latest_id'),
        func.max(Complaint.updated_at).label('latest_updated'),
    ).one()
    total_count = int(total_row.total or 0)
    pending_count = int(total_row.pending or 0)
    latest_id = int(total_row.latest_id or 0)
    latest_updated = total_row.latest_updated.isoformat() if total_row.latest_updated else ''

    notif_agg = (
        db.session.query(
            func.sum(case((Notification.is_read == False, 1), else_=0)).label('unread'),
            func.max(Notification.id).label('latest_notif_id'),
        )
        .filter(Notification.user_id == user_id)
        .one()
    )
    unread_notifs = int(notif_agg.unread or 0)
    latest_notif_id = int(notif_agg.latest_notif_id or 0)

    latest_notif = None
    new_notifications = []
    if since_notif_id is not None and latest_notif_id > since_notif_id:
        missed = (
            Notification.query.filter(
                Notification.user_id == user_id,
                Notification.id > since_notif_id
            )
            .order_by(Notification.id.asc())
            .limit(20)
            .all()
        )
        new_notifications = [n.to_dict() for n in missed]
        if missed:
            latest_notif = missed[-1]
    elif latest_notif_id > 0:
        latest_notif = db.session.get(Notification, latest_notif_id)

    fingerprint = f"{total_count}:{pending_count}:{latest_id}:{latest_updated}"
    return {
        'fingerprint': fingerprint,
        'total_count': total_count,
        'pending_count': pending_count,
        'latest_id': latest_id,
        'unread_notifications': unread_notifs,
        'latest_notif_id': latest_notif_id,
        'latest_notification': latest_notif.to_dict() if latest_notif else None,
        'new_notifications': new_notifications,
        'role': role,
    }


@api_bp.route('/live-updates')
@login_required
def live_updates():
    """
    Lightweight live sync endpoint polled as fallback or on focus so Admin, Officer,
    Worker, and Citizen views update automatically without manual page refresh.
    """
    since_id = request.args.get('since_id', type=int)
    snapshot = _build_user_live_snapshot(
        g.user.id,
        g.user.role,
        g.user.department_id,
        since_notif_id=since_id
    )
    return jsonify(snapshot)


@api_bp.route('/stream')
@login_required
def realtime_stream():
    """
    Authenticated Server-Sent Events (SSE) stream backed directly by MySQL/DB.
    Reconnects cleanly every ~25s and supports Last-Event-ID for missed notification recovery.
    """
    user_id = g.user.id
    role = g.user.role
    dept_id = g.user.department_id
    is_testing = bool(current_app.config.get('TESTING'))
    since_id = None
    try:
        raw_since = request.headers.get('Last-Event-ID') or request.args.get('since_id')
        if raw_since is not None and str(raw_since).strip() != '':
            since_id = int(raw_since)
    except (TypeError, ValueError):
        since_id = None

    @stream_with_context
    def event_generator():
        yield "retry: 2000\n\n"
        last_fp = None
        last_unread = None
        cursor_notif_id = since_id
        ticks = 1 if is_testing else 4

        for tick in range(ticks):
            try:
                db.session.remove()
                snapshot = _build_user_live_snapshot(
                    user_id,
                    role,
                    dept_id,
                    since_notif_id=cursor_notif_id
                )
                fp = snapshot['fingerprint']
                unread = snapshot['unread_notifications']
                latest_nid = snapshot['latest_notif_id']

                has_new = (cursor_notif_id is not None and latest_nid > cursor_notif_id) or (cursor_notif_id is None and tick == 0)
                if tick == 0 or fp != last_fp or unread != last_unread or has_new:
                    event_id = latest_nid if latest_nid is not None else 0
                    cursor_notif_id = latest_nid
                    last_fp = fp
                    last_unread = unread
                    yield f"id: {event_id}\nevent: sync\ndata: {json.dumps(snapshot)}\n\n"
                elif tick % 6 == 0:
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': int(time.time())})}\n\n"
            except GeneratorExit:
                break
            except Exception:
                db.session.rollback()
                yield f"event: heartbeat\ndata: {json.dumps({'status': 'recovering'})}\n\n"

            if not is_testing and tick < ticks - 1:
                time.sleep(1.5)

    headers = {
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }
    return Response(event_generator(), mimetype='text/event-stream', headers=headers)


@api_bp.route('/language', methods=['GET', 'POST'])
def api_language():
    """Read or persist user interface language in session, cookie, and DB user preference."""
    from app.utils.translations import SUPPORTED_LANGUAGES
    if request.method == 'POST':
        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        raw_lang = (payload.get('lang') or payload.get('language') or '').strip().lower()
        if raw_lang not in SUPPORTED_LANGUAGES:
            return jsonify({'success': False, 'message': 'Unsupported language selection.'}), 400
        session['lang'] = raw_lang
        g.active_lang = raw_lang
        uid = session.get('user_id')
        if uid:
            user_obj = User.query.get(uid)
            if user_obj and user_obj.preferred_language != raw_lang:
                user_obj.preferred_language = raw_lang
                db.session.commit()
        resp = jsonify({'success': True, 'lang': raw_lang})
        resp.set_cookie('sccmt_lang', raw_lang, max_age=31536000, path='/', samesite='Lax')
        resp.set_cookie('sccmt_lang_explicit', '1', max_age=31536000, path='/', samesite='Lax')
        return resp

    current = session.get('lang') or request.cookies.get('sccmt_lang') or 'en'
    if current not in SUPPORTED_LANGUAGES:
        current = 'en'
    return jsonify({'success': True, 'lang': current})

