import io
import csv
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, Response, jsonify
from sqlalchemy.orm import joinedload
from app import db
from app.models.complaint import Complaint
from app.models.workflow import Worker, ComplaintAssignment
from app.models.user import User
from app.services.complaint_service import (
    transition_complaint_status,
    assign_complaint_to_worker,
    officer_verify_work,
    get_complaint_9_stage_timeline,
    get_complaint_aggregate_counts,
    IN_PROGRESS_STATUSES,
)
from app.services.audit_service import log_action
from app.utils.decorators import login_required, role_required, _is_api_or_ajax

officer_bp = Blueprint('officer', __name__)

@officer_bp.before_request
@login_required
@role_required('officer')
def before_request():
    pass

@officer_bp.route('/dashboard')
def dashboard():
    dept_id = g.user.department_id
    if not dept_id:
        flash("You are not currently assigned to any civic department. Please contact an administrator.", "warning")

    if dept_id:
        dept_filter = (Complaint.department_id == dept_id) & (
            (Complaint.assigned_officer_id == g.user.id) | (Complaint.assigned_officer_id.is_(None))
        )
        counts = get_complaint_aggregate_counts(dept_filter)
        recent_complaints = (
            Complaint.query.filter(dept_filter)
            .options(joinedload(Complaint.category), joinedload(Complaint.citizen))
            .order_by(Complaint.created_at.desc())
            .limit(6)
            .all()
        )
        dept_workers = Worker.query.filter_by(department_id=dept_id).options(joinedload(Worker.user)).all()
    else:
        counts = get_complaint_aggregate_counts(Complaint.id == -1)
        recent_complaints = []
        dept_workers = []

    stats = {
        'total': counts['total'],
        'new': counts['officer_new'],
        'pending': counts['officer_pending'],
        'assigned': counts['assigned'],
        'in_progress': counts['active_work'],
        'completed': counts['completed_pending'],
        'resolved': counts['resolved'],
        'overdue': counts['overdue']
    }

    return render_template(
        'officer/dashboard.html',
        stats=stats,
        recent_complaints=recent_complaints,
        workers=dept_workers,
        department=g.user.department
    )

@officer_bp.route('/complaints', strict_slashes=False)
@officer_bp.route('/complaint', strict_slashes=False)
def complaints():
    dept_id = g.user.department_id
    query = (
        Complaint.query.filter_by(department_id=dept_id)
        .filter((Complaint.assigned_officer_id == g.user.id) | (Complaint.assigned_officer_id.is_(None)))
        .options(joinedload(Complaint.category), joinedload(Complaint.citizen), joinedload(Complaint.assigned_worker))
        if dept_id else Complaint.query.filter_by(id=-1)
    )

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Complaint.complaint_ref.ilike(f'%{search}%')) |
            (Complaint.title.ilike(f'%{search}%')) |
            (Complaint.description.ilike(f'%{search}%'))
        )

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    priority = request.args.get('priority')
    if priority:
        query = query.filter_by(priority=priority)

    page = max(1, request.args.get('page', 1, type=int))
    pagination = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=25, error_out=False)

    return render_template(
        'officer/complaints.html',
        complaints=pagination.items,
        pagination=pagination,
        current_status=status,
        current_priority=priority,
        search_query=search
    )

@officer_bp.route('/complaints/<int:complaint_id>', methods=['GET', 'POST'], strict_slashes=False)
@officer_bp.route('/complaint/<int:complaint_id>', methods=['GET', 'POST'], strict_slashes=False)
def complaint_detail(complaint_id):
    dept_id = g.user.department_id
    complaint = Complaint.query.filter_by(id=complaint_id, department_id=dept_id).filter(
        (Complaint.assigned_officer_id == g.user.id) | (Complaint.assigned_officer_id.is_(None))
    ).first()
    if not complaint:
        if request.method == 'POST' and _is_api_or_ajax():
            return jsonify({'success': False, 'message': f"Complaint #{complaint_id} was not found in your authorized department schedule."}), 404
        flash(f"Complaint #{complaint_id} was not found in your authorized department schedule.", "warning")
        return redirect(url_for('officer.complaints'))

    if request.method == 'POST':
        action = request.form.get('action')
        remarks = request.form.get('remarks', '').strip()
        is_ajax = _is_api_or_ajax()
        success_msg = None

        try:
            if action == 'accept':
                transition_complaint_status(complaint, 'Officer Accepted', g.user, remarks=remarks or "Accepted by Department Officer")
                success_msg = "Complaint accepted into department schedule."

            elif action == 'reject':
                reason = request.form.get('rejection_reason', '').strip()
                if not reason:
                    if is_ajax:
                        return jsonify({'success': False, 'message': "Mandatory rejection reason required."}), 400
                    flash("Mandatory rejection reason required.", "danger")
                    return redirect(url_for('officer.complaint_detail', complaint_id=complaint.id))
                transition_complaint_status(complaint, 'Rejected', g.user, remarks=remarks, rejection_reason=reason)
                success_msg = "Complaint rejected."

            elif action == 'set_priority':
                priority = request.form.get('priority')
                if priority in ['low', 'medium', 'high', 'urgent']:
                    complaint.priority = priority
                    log_action(g.user.id, 'OFFICER_UPDATE_PRIORITY', 'complaint', complaint.id, details={'priority': priority}, commit=False)
                    db.session.commit()
                    success_msg = f"Priority updated to {priority.upper()}."

            elif action == 'assign_worker':
                worker_user_id = request.form.get('worker_user_id', type=int)
                instructions = request.form.get('instructions', '').strip()
                if not worker_user_id:
                    if is_ajax:
                        return jsonify({'success': False, 'message': "Please select an available field worker belonging to your department."}), 400
                    flash("Please select an available field worker belonging to your department.", "danger")
                else:
                    assign_complaint_to_worker(complaint, worker_user_id, g.user, instructions)
                    success_msg = "Field technician assigned successfully."

            elif action == 'verify_resolve':
                officer_verify_work(complaint, g.user, action='approve', remarks=remarks)
                success_msg = "Work verified and complaint successfully resolved!"

            elif action == 'return_rework':
                rework_reason = request.form.get('rework_reason', request.form.get('return_remarks', '')).strip()
                if not rework_reason:
                    if is_ajax:
                        return jsonify({'success': False, 'message': "Please provide a mandatory reason for returning work for rework."}), 400
                    flash("Please provide a mandatory reason for returning work for rework.", "danger")
                    return redirect(url_for('officer.complaint_detail', complaint_id=complaint.id))
                officer_verify_work(complaint, g.user, action='rework', remarks=remarks, rework_reason=rework_reason)
                success_msg = "Task returned to field worker for rework."

            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': success_msg or "Action completed successfully.",
                    'status': complaint.status,
                    'priority': complaint.priority,
                    'reload_sections': action != 'set_priority'
                })
            if success_msg:
                flash(success_msg, "success" if action != 'return_rework' else "warning")

        except Exception as e:
            db.session.rollback()
            if is_ajax:
                return jsonify({'success': False, 'message': f"Action failed: {str(e)}"}), 400
            flash(f"Action failed: {str(e)}", "danger")

        return redirect(url_for('officer.complaint_detail', complaint_id=complaint.id))

    history = complaint.status_history.all()
    attachments = complaint.attachments.all()
    workers = Worker.query.filter_by(department_id=dept_id, is_available=True).options(joinedload(Worker.user)).all()
    stages = get_complaint_9_stage_timeline(complaint)
        
    return render_template(
        'officer/complaint_detail.html',
        complaint=complaint,
        history=history,
        attachments=attachments,
        workers=workers,
        stages=stages
    )

@officer_bp.route('/workers')
def workers():
    dept_id = g.user.department_id
    worker_list = Worker.query.filter_by(department_id=dept_id).all() if dept_id else []
    return render_template('officer/workers.html', workers=worker_list)

@officer_bp.route('/reports')
def reports():
    dept_id = g.user.department_id
    complaints = Complaint.query.filter_by(department_id=dept_id).all() if dept_id else []
    
    total = len(complaints)
    resolved = len([c for c in complaints if c.status == 'Resolved'])
    pending = len([c for c in complaints if c.status in (['Submitted', 'Under Review'] + IN_PROGRESS_STATUSES)])
    
    return render_template(
        'officer/reports.html',
        complaints=complaints,
        total=total,
        resolved=resolved,
        pending=pending
    )

@officer_bp.route('/incoming')
def incoming():
    dept_id = g.user.department_id
    query = Complaint.query.filter_by(department_id=dept_id).filter(
        Complaint.status.in_(['Submitted', 'Assigned to Department'])
    ) if dept_id else Complaint.query.filter_by(id=-1)
    incoming_list = query.order_by(Complaint.created_at.desc()).all()
    return render_template('officer/complaints.html', complaints=incoming_list, current_status='Assigned to Department', page_title='Incoming Complaints Requiring Review')

@officer_bp.route('/verification')
def verification():
    dept_id = g.user.department_id
    query = Complaint.query.filter_by(department_id=dept_id, status='Verification Pending') if dept_id else Complaint.query.filter_by(id=-1)
    verif_list = query.order_by(Complaint.updated_at.desc()).all()
    return render_template('officer/complaints.html', complaints=verif_list, current_status='Verification Pending', page_title='Work Verification Queue')

@officer_bp.route('/escalations')
def escalations():
    dept_id = g.user.department_id
    query = Complaint.query.filter_by(department_id=dept_id).filter((Complaint.is_escalated == True) | (Complaint.status == 'Escalated')) if dept_id else Complaint.query.filter_by(id=-1)
    esc_list = query.order_by(Complaint.created_at.asc()).all()
    return render_template('officer/complaints.html', complaints=esc_list, current_status='Escalated', page_title='Escalated Department Complaints')

@officer_bp.route('/notifications')
def notifications():
    from app.models.notification import Notification
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(Notification.created_at.desc()).all()
    return render_template('officer/notifications.html', notifications=notifs)

@officer_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    user = g.user
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        new_password = request.form.get('new_password', '').strip()
        if full_name:
            user.full_name = full_name
        if new_password:
            user.set_password(new_password)
            user.is_password_reset_required = False
            user.password_changed_at = datetime.utcnow()
        db.session.commit()
        msg = "Officer profile updated successfully."
        if _is_api_or_ajax():
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('officer.profile'))
    return render_template('officer/profile.html', user=user)
