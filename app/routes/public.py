from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, jsonify, current_app
from app import db
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.user import User
from app.models.feedback import Feedback
from app.models.contact import ContactMessage

from app.services.complaint_service import (
    get_complaint_9_stage_timeline,
    get_complaint_aggregate_counts,
    lookup_tracked_complaint,
)
from app.services.notification_service import notify_admins
from app.utils.decorators import _is_api_or_ajax
from app.utils.ttl_cache import app_cache

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    use_cache = not current_app.config.get('TESTING')
    cached = app_cache.get('public:index') if use_cache else None
    if cached is not None:
        return render_template(
            'public/index.html',
            departments=cached['departments'],
            categories=cached['categories'],
            stats=cached['stats']
        )

    departments = Department.query.filter_by(is_active=True).all()
    categories = ComplaintCategory.query.filter_by(is_active=True).limit(8).all()
    
    # Live stats (aggregated directly in SQL)
    counts = get_complaint_aggregate_counts()
    total_complaints = counts['total']
    resolved_complaints = counts['resolved']
    active_departments = len(departments)

    avg_rating_val = db.session.query(db.func.avg(Feedback.rating)).scalar()
    avg_rating = round(float(avg_rating_val), 1) if avg_rating_val is not None else 4.8
        
    stats = {
        'total': total_complaints,
        'resolved': resolved_complaints,
        'departments': active_departments,
        'rating': avg_rating
    }
    if use_cache:
        dept_snap = [{'id': d.id, 'name': d.name, 'code': d.code, 'description': d.description, 'contact_email': d.contact_email, 'contact_phone': d.contact_phone} for d in departments]
        cat_snap = [{'id': c.id, 'name': c.name, 'description': c.description, 'default_priority': c.default_priority, 'sla_hours': c.sla_hours} for c in categories]
        app_cache.set('public:index', {'departments': dept_snap, 'categories': cat_snap, 'stats': stats}, ttl_seconds=30)

    return render_template(
        'public/index.html',
        departments=departments,
        categories=categories,
        stats=stats
    )

@public_bp.route('/about')
def about():
    use_cache = not current_app.config.get('TESTING')
    departments_count = app_cache.get('public:dept_count') if use_cache else None
    if departments_count is None:
        departments_count = Department.query.filter_by(is_active=True).count()
        if use_cache:
            app_cache.set('public:dept_count', departments_count, ttl_seconds=60)
    return render_template('public/about.html', departments_count=departments_count)

@public_bp.route('/how-it-works')
def how_it_works():
    return render_template('public/how_it_works.html')

@public_bp.route('/departments')
def departments():
    use_cache = not current_app.config.get('TESTING')
    dept_list = app_cache.get('public:departments') if use_cache else None
    if dept_list is None:
        rows = Department.query.filter_by(is_active=True).all()
        if use_cache:
            dept_list = [{'id': d.id, 'name': d.name, 'code': d.code, 'description': d.description, 'contact_email': d.contact_email, 'contact_phone': d.contact_phone} for d in rows]
            app_cache.set('public:departments', dept_list, ttl_seconds=60)
        else:
            dept_list = rows
    return render_template('public/departments.html', departments=dept_list)

@public_bp.route('/track', methods=['GET', 'POST'])
def track():
    ref = request.args.get('ref') or (request.form.get('ref') if request.method == 'POST' else None)
    identifier = request.args.get('identifier') or (request.form.get('identifier') if request.method == 'POST' else None)
    complaint, not_found, clean_ref, stages = lookup_tracked_complaint(ref, identifier)
    return render_template('public/track.html', complaint=complaint, not_found=not_found, search_ref=clean_ref, stages=stages)

@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        contact_info = (request.form.get('contact') or '').strip()
        message_text = (request.form.get('message') or '').strip()

        if not name or not contact_info or not message_text:
            err_msg = "Please enter your name, contact info, and inquiry message."
            if _is_api_or_ajax():
                return jsonify({'success': False, 'message': err_msg}), 400
            flash(err_msg, "danger")
            return redirect(url_for('public.contact'))

        user_id = session.get('user_id')
        msg = ContactMessage(
            name=name[:120],
            contact=contact_info[:150],
            message=message_text,
            user_id=user_id,
            is_read=False,
        )
        db.session.add(msg)

        preview = (message_text[:160] + '...') if len(message_text) > 160 else message_text
        notify_admins(
            title=f"New Contact Inquiry: {name}",
            message=f"From {name} ({contact_info}): {preview}",
            notification_type='info',
            link=url_for('admin.dashboard') + '#contactInquiriesCard',
            commit=False,
        )
        db.session.commit()

        ok_msg = "Thank you for reaching out. Your inquiry has been sent to the civic administration dashboard."
        if _is_api_or_ajax():
            return jsonify({'success': True, 'message': ok_msg})
        flash(ok_msg, "success")
        return redirect(url_for('public.contact'))
    return render_template('public/contact.html')

@public_bp.route('/set-language/<lang>')
def set_language(lang):
    if lang in ['en', 'ta', 'hi']:
        session['lang'] = lang
    referer = request.headers.get('Referer')
    return redirect(referer or url_for('public.index'))

@public_bp.route('/privacy')
def privacy():
    return render_template('public/privacy.html')

@public_bp.route('/cookies')
def cookies():
    return render_template('public/cookies.html')

@public_bp.route('/terms')
def terms():
    return render_template('public/terms.html')
