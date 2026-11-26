from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session, jsonify
from sqlalchemy.orm import joinedload
from app import db
from app.models.complaint import Complaint
from app.models.category import ComplaintCategory
from app.models.department import Department
from app.models.feedback import Feedback
from app.services.complaint_service import (
    create_complaint,
    transition_complaint_status,
    get_complaint_9_stage_timeline,
    get_complaint_aggregate_counts,
    PENDING_STATUSES,
    IN_PROGRESS_STATUSES,
)
from app.utils.decorators import login_required, role_required, _is_api_or_ajax
from app.utils.helpers import save_uploaded_file
from app.services.audit_service import log_action
from app.services.notification_service import notify_admins

citizen_bp = Blueprint('citizen', __name__)

@citizen_bp.before_request
@login_required
@role_required('citizen')
def before_request():
    pass

@citizen_bp.route('/dashboard')
def dashboard():
    user = g.user
    counts = get_complaint_aggregate_counts(Complaint.citizen_id == user.id)
    recent_complaints = (
        Complaint.query.filter_by(citizen_id=user.id)
        .options(joinedload(Complaint.category), joinedload(Complaint.department))
        .order_by(Complaint.created_at.desc())
        .limit(5)
        .all()
    )

    stats = {
        'total': counts['total'],
        'pending': counts['pending'],
        'in_progress': counts['in_progress'],
        'resolved': counts['resolved'],
        'rejected': counts['rejected']
    }

    return render_template('citizen/dashboard.html', stats=stats, recent_complaints=recent_complaints)

@citizen_bp.route('/complaints', strict_slashes=False)
@citizen_bp.route('/complaint', strict_slashes=False)
def complaints():
    user = g.user
    query = Complaint.query.filter_by(citizen_id=user.id).options(
        joinedload(Complaint.category),
        joinedload(Complaint.department),
    )

    # Search
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Complaint.complaint_ref.ilike(f'%{search}%')) |
            (Complaint.title.ilike(f'%{search}%')) |
            (Complaint.description.ilike(f'%{search}%'))
        )

    # Filters
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    priority = request.args.get('priority')
    if priority:
        query = query.filter_by(priority=priority)

    page = max(1, request.args.get('page', 1, type=int))
    pagination = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    categories = ComplaintCategory.query.filter_by(is_active=True).all()

    return render_template(
        'citizen/complaints_list.html',
        complaints=pagination.items,
        pagination=pagination,
        categories=categories,
        current_status=status,
        current_category=category_id,
        current_priority=priority,
        search_query=search
    )

@citizen_bp.route('/complaints/new', methods=['GET', 'POST'])
def new_complaint():
    user = g.user
    categories = ComplaintCategory.query.filter_by(is_active=True).all()
    departments = Department.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category_id = request.form.get('category_id', type=int)
        department_id = request.form.get('department_id', type=int)
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        state = request.form.get('state', 'Tamil Nadu').strip()
        district = request.form.get('district', 'Chennai').strip()
        city = request.form.get('city', user.city or 'Chennai').strip()
        ward_number = request.form.get('ward_number', user.ward_number or '').strip()
        street_name = request.form.get('street_name', '').strip()
        locality = request.form.get('locality', '').strip()
        landmark = request.form.get('landmark', '').strip()
        pincode = request.form.get('pincode', '').strip()
        address = request.form.get('address', '').strip()
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        
        if not title or len(title) < 5:
            flash("Please provide a descriptive complaint title (minimum 5 characters).", "danger")
            return render_template('citizen/new_complaint.html', categories=categories, departments=departments)
            
        if not description or len(description) < 15:
            flash("Please provide sufficient complaint details (minimum 15 characters).", "danger")
            return render_template('citizen/new_complaint.html', categories=categories, departments=departments)
            
        if not category_id:
            flash("Please select a valid complaint category.", "danger")
            return render_template('citizen/new_complaint.html', categories=categories, departments=departments)
            
        # Handle file uploads
        uploaded_attachments = []
        files = request.files.getlist('attachments')
        for f in files:
            if f and f.filename != '':
                saved = save_uploaded_file(f, 'complaints')
                if saved:
                    uploaded_attachments.append(saved)
                    
        try:
            complaint = create_complaint(
                citizen_id=user.id,
                title=title,
                description=description,
                category_id=category_id,
                priority=priority,
                address=address,
                city=city,
                ward_number=ward_number,
                state=state,
                district=district,
                street_name=street_name,
                locality=locality,
                landmark=landmark,
                pincode=pincode,
                latitude=latitude,
                longitude=longitude,
                department_id=department_id,
                attachments=uploaded_attachments
            )
            flash(f"Complaint registered successfully! Your tracking Reference ID is {complaint.complaint_ref}.", "success")
            return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error registering complaint: {str(e)}", "danger")
            
    return render_template('citizen/new_complaint.html', categories=categories, departments=departments)

@citizen_bp.route('/complaints/<int:complaint_id>', strict_slashes=False)
@citizen_bp.route('/complaint/<int:complaint_id>', strict_slashes=False)
def complaint_detail(complaint_id):
    user = g.user
    complaint = Complaint.query.filter_by(id=complaint_id, citizen_id=user.id).first()
    if not complaint:
        flash(f"Complaint #{complaint_id} was not found or is not accessible.", "warning")
        return redirect(url_for('citizen.complaints'))

    history = complaint.status_history.all()
    attachments = complaint.attachments.all()
    existing_feedback = Feedback.query.filter_by(complaint_id=complaint.id).first()
    stages = get_complaint_9_stage_timeline(complaint, history=history)
    
    return render_template(
        'citizen/complaint_detail.html',
        complaint=complaint,
        history=history,
        attachments=attachments,
        existing_feedback=existing_feedback,
        stages=stages
    )

@citizen_bp.route('/complaints/<int:complaint_id>/reopen', methods=['POST'])
def reopen_complaint(complaint_id):
    user = g.user
    complaint = Complaint.query.filter_by(id=complaint_id, citizen_id=user.id).first_or_404()

    if complaint.status != 'Resolved':
        msg = "Only resolved complaints can be reopened."
        if _is_api_or_ajax():
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "warning")
        return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))

    reason = request.form.get('reopen_reason', '').strip()
    if not reason or len(reason) < 10:
        msg = "Please provide a comprehensive explanation for reopening this issue."
        if _is_api_or_ajax():
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "danger")
        return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))

    try:
        transition_complaint_status(complaint, 'Reopened', user, remarks=f"Reopened by citizen: {reason}")
        msg = "Complaint has been reopened for departmental review."
        if _is_api_or_ajax():
            return jsonify({'success': True, 'message': msg, 'status': complaint.status, 'reload_sections': True})
        flash(msg, "info")
    except Exception as e:
        if _is_api_or_ajax():
            return jsonify({'success': False, 'message': f"Failed to reopen complaint: {str(e)}"}), 400
        flash(f"Failed to reopen complaint: {str(e)}", "danger")

    return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))

@citizen_bp.route('/complaints/<int:complaint_id>/feedback', methods=['POST'])
def submit_feedback(complaint_id):
    user = g.user
    complaint = Complaint.query.filter_by(id=complaint_id, citizen_id=user.id).first_or_404()

    if complaint.status != 'Resolved':
        msg = "Feedback can only be submitted after complaint resolution."
        if _is_api_or_ajax():
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "warning")
        return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))

    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    speed_rating = request.form.get('response_speed_rating', type=int)
    quality_rating = request.form.get('work_quality_rating', type=int)

    if not rating or rating < 1 or rating > 5:
        msg = "Please select a rating between 1 and 5 stars."
        if _is_api_or_ajax():
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "danger")
        return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))

    existing = Feedback.query.filter_by(complaint_id=complaint.id).first()
    if existing:
        existing.rating = rating
        existing.comment = comment
        existing.response_speed_rating = speed_rating
        existing.work_quality_rating = quality_rating
        existing.is_satisfied = rating >= 3
    else:
        fb = Feedback(
            complaint_id=complaint.id,
            citizen_id=user.id,
            rating=rating,
            comment=comment,
            response_speed_rating=speed_rating,
            work_quality_rating=quality_rating,
            is_satisfied=rating >= 3
        )
        db.session.add(fb)

    notify_admins(
        title=f"Citizen Feedback ({rating}/5): {complaint.complaint_ref}",
        message=f"{user.full_name} rated '{complaint.title}' {rating}/5 stars. {comment[:120] if comment else ''}".strip(),
        link=url_for('admin.dashboard') + '#citizenFeedbackCard',
        notification_type='info',
        complaint_id=complaint.id,
        commit=False,
    )
    log_action(user.id, 'SUBMIT_FEEDBACK', 'complaint', complaint.id, details={'rating': rating}, commit=False)
    db.session.commit()

    msg = "Thank you! Your feedback helps us improve civic governance services."
    if _is_api_or_ajax():
        return jsonify({'success': True, 'message': msg, 'reload_sections': True})
    flash(msg, "success")
    return redirect(url_for('citizen.complaint_detail', complaint_id=complaint.id))

@citizen_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user = g.user
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        ward_number = request.form.get('ward_number', '').strip()
        new_password = request.form.get('new_password', '')

        if full_name:
            user.full_name = full_name
        user.address = address
        user.city = city
        user.ward_number = ward_number

        if new_password:
            user.set_password(new_password)
            user.is_password_reset_required = False
            user.password_changed_at = datetime.utcnow()

        db.session.commit()
        msg = "Profile information updated successfully."
        if _is_api_or_ajax():
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('citizen.profile'))

    return render_template('citizen/profile.html', user=user)

@citizen_bp.route('/notifications')
def notifications():
    from app.models.notification import Notification
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(Notification.created_at.desc()).all()
    return render_template('citizen/notifications.html', notifications=notifs)

@citizen_bp.route('/feedback')
def feedback():
    user = g.user
    resolved_complaints = Complaint.query.filter_by(citizen_id=user.id, status='Resolved').order_by(Complaint.resolved_at.desc()).all()
    return render_template('citizen/feedback.html', complaints=resolved_complaints)
