from flask import Blueprint, jsonify, request, session, g
from app import db
from app.models.complaint import Complaint
from app.models.category import ComplaintCategory
from app.models.department import Department
from app.models.user import User
from app.models.notification import Notification
from app.services.complaint_service import find_potential_duplicates, suggest_department_by_category
from app.services.notification_service import mark_as_read, mark_all_as_read
from app.services.sla_service import check_and_escalate_overdue_complaints
from app.utils.decorators import login_required

api_bp = Blueprint('api', __name__)

@api_bp.route('/stats/summary')
def stats_summary():
    total = Complaint.query.count()
    resolved = Complaint.query.filter_by(status='Resolved').count()
    pending = Complaint.query.filter(Complaint.status.in_(['Submitted', 'Under Review'])).count()
    in_progress = Complaint.query.filter(Complaint.status.in_(['Accepted', 'Assigned', 'In Progress', 'Work Completed', 'Verification Pending'])).count()
    overdue = Complaint.query.filter_by(is_escalated=True).count()
    
    return jsonify({
        'total': total,
        'resolved': resolved,
        'pending': pending,
        'in_progress': in_progress,
        'overdue': overdue
    })

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
