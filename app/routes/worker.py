from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from sqlalchemy.orm import joinedload
from app import db
from app.models.complaint import Complaint
from app.models.workflow import ComplaintAssignment, Worker, ComplaintStatusHistory
from app.models.attachment import ComplaintAttachment
from app.services.complaint_service import (
    transition_complaint_status,
    get_complaint_9_stage_timeline,
    get_complaint_aggregate_counts,
    ASSIGNED_TO_WORKER_STATUSES,
    ACTIVE_WORK_STATUSES,
    COMPLETED_PENDING_VERIF_STATUSES,
)
from app.services.notification_service import create_notification, notify_admins, notify_department_officers
from app.services.audit_service import log_action
from app.utils.helpers import save_uploaded_file
from app.utils.decorators import login_required, role_required, _is_api_or_ajax

worker_bp = Blueprint('worker', __name__)

@worker_bp.before_request
@login_required
@role_required('worker')
def before_request():
    pass

@worker_bp.route('/dashboard')
def dashboard():
    worker_user_id = g.user.id
    assigned_complaint_ids = [
        r[0]
        for r in db.session.query(ComplaintAssignment.complaint_id)
        .filter_by(assigned_to_user_id=worker_user_id)
        .distinct()
        .all()
    ]

    if assigned_complaint_ids:
        counts = get_complaint_aggregate_counts(Complaint.id.in_(assigned_complaint_ids))
        active_tasks = (
            Complaint.query.filter(Complaint.id.in_(assigned_complaint_ids))
            .filter(Complaint.status.in_(ASSIGNED_TO_WORKER_STATUSES + ACTIVE_WORK_STATUSES))
            .options(joinedload(Complaint.category), joinedload(Complaint.department))
            .order_by(Complaint.priority.desc())
            .all()
        )
    else:
        counts = get_complaint_aggregate_counts(Complaint.id == -1)
        active_tasks = []

    stats = {
        'total': counts['total'],
        'new_tasks': counts['assigned'],
        'in_progress': counts['active_work'],
        'completed': counts['worker_completed']
    }

    return render_template(
        'worker/dashboard.html',
        stats=stats,
        active_tasks=active_tasks
    )

@worker_bp.route('/tasks', strict_slashes=False)
@worker_bp.route('/task', strict_slashes=False)
def tasks():
    worker_user_id = g.user.id
    assigned_complaint_ids = [
        r[0]
        for r in db.session.query(ComplaintAssignment.complaint_id)
        .filter_by(assigned_to_user_id=worker_user_id)
        .distinct()
        .all()
    ]

    query = (
        Complaint.query.filter(Complaint.id.in_(assigned_complaint_ids))
        .options(joinedload(Complaint.category), joinedload(Complaint.department))
        if assigned_complaint_ids else Complaint.query.filter_by(id=-1)
    )

    status = request.args.get('status')
    if status:
        if status in ASSIGNED_TO_WORKER_STATUSES:
            query = query.filter(Complaint.status.in_(ASSIGNED_TO_WORKER_STATUSES))
        elif status in ('In Progress', 'Work Started'):
            query = query.filter(Complaint.status.in_(ACTIVE_WORK_STATUSES))
        elif status in COMPLETED_PENDING_VERIF_STATUSES:
            query = query.filter(Complaint.status.in_(COMPLETED_PENDING_VERIF_STATUSES))
        else:
            query = query.filter_by(status=status)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Complaint.complaint_ref.ilike(f'%{search}%')) |
            (Complaint.title.ilike(f'%{search}%'))
        )

    page = max(1, request.args.get('page', 1, type=int))
    pagination = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template('worker/tasks.html', tasks=pagination.items, pagination=pagination, current_status=status, search_query=search)

@worker_bp.route('/tasks/<int:complaint_id>', methods=['GET', 'POST'], strict_slashes=False)
@worker_bp.route('/task/<int:complaint_id>', methods=['GET', 'POST'], strict_slashes=False)
def task_detail(complaint_id):
    worker_user_id = g.user.id
    
    # Verify assignment
    assignment = ComplaintAssignment.query.filter_by(
        complaint_id=complaint_id,
        assigned_to_user_id=worker_user_id
    ).first()
    if not assignment:
        flash(f"Task #{complaint_id} was not found in your assignments queue.", "warning")
        return redirect(url_for('worker.tasks'))
    
    complaint = assignment.complaint
    history = complaint.status_history.all()
    attachments = complaint.attachments.all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        remarks = request.form.get('remarks', '').strip()
        is_ajax = _is_api_or_ajax()
        success_msg = None

        try:
            if action == 'start_work':
                # Worker starts field work in one atomic transaction
                old_status = complaint.status
                complaint.status = 'In Progress'
                complaint.updated_at = datetime.utcnow()
                assignment.status = 'In Progress'

                db.session.add(ComplaintStatusHistory(
                    complaint_id=complaint.id,
                    changed_by_user_id=g.user.id,
                    previous_status=old_status,
                    new_status='In Progress',
                    remarks=remarks or "Field technician started site work."
                ))

                before_img = request.files.get('before_image')
                if before_img and before_img.filename != '':
                    saved = save_uploaded_file(before_img, 'proofs')
                    if saved:
                        db.session.add(ComplaintAttachment(
                            complaint_id=complaint.id,
                            uploaded_by_user_id=g.user.id,
                            attachment_type='before_work',
                            filename=saved['filename'],
                            original_name=saved['original_name'],
                            file_path=saved['file_path'],
                            file_size=saved['file_size'],
                            mime_type=saved['mime_type'],
                            file_data=saved.get('file_data'),
                            remarks='Pre-work site condition'
                        ))

                start_remarks = remarks or "Field technician started site work."
                create_notification(
                    user_id=complaint.citizen_id,
                    complaint_id=complaint.id,
                    title=f"Status Update: {complaint.complaint_ref}",
                    message=f"Your complaint is now 'In Progress'. Remarks: {start_remarks}",
                    link=f"/citizen/complaints/{complaint.id}",
                    notification_type='status_changed',
                    commit=False,
                )
                notify_admins(
                    title=f"In Progress: {complaint.complaint_ref}",
                    message=f"{g.user.full_name} (Worker) updated {complaint.complaint_ref} to 'In Progress'. {start_remarks}",
                    link=f"/admin/complaints/{complaint.id}",
                    notification_type='status_changed',
                    complaint_id=complaint.id,
                    commit=False,
                )
                if complaint.assigned_officer_id:
                    create_notification(
                        complaint.assigned_officer_id,
                        f"Work Started: {complaint.complaint_ref}",
                        f"Field technician {g.user.full_name} started work on '{complaint.title}'.",
                        link=f"/officer/complaints/{complaint.id}",
                        notification_type='status_changed',
                        complaint_id=complaint.id,
                        commit=False,
                    )
                elif complaint.department_id:
                    notify_department_officers(
                        complaint.department_id,
                        f"Work Started: {complaint.complaint_ref}",
                        f"Field technician {g.user.full_name} started work on '{complaint.title}'.",
                        link=f"/officer/complaints/{complaint.id}",
                        notification_type='status_changed',
                        complaint_id=complaint.id,
                        commit=False,
                    )
                log_action(
                    user_id=g.user.id,
                    action='UPDATE_STATUS',
                    entity_type='complaint',
                    entity_id=complaint.id,
                    details={'from': old_status, 'to': 'In Progress', 'remarks': start_remarks},
                    commit=False,
                )
                db.session.commit()
                success_msg = "Task marked In Progress."

            elif action == 'update_progress':
                progress_notes = request.form.get('progress_notes', '').strip()
                if not progress_notes:
                    if is_ajax:
                        return jsonify({'success': False, 'message': "Please provide progress details."}), 400
                    flash("Please provide progress details.", "danger")
                    return redirect(url_for('worker.task_detail', complaint_id=complaint.id))
                hist = ComplaintStatusHistory(
                    complaint_id=complaint.id,
                    changed_by_user_id=g.user.id,
                    previous_status=complaint.status,
                    new_status=complaint.status,
                    remarks=f"Progress Update: {progress_notes}"
                )
                complaint.updated_at = datetime.utcnow()
                db.session.add(hist)
                if complaint.assigned_officer_id:
                    create_notification(
                        complaint.assigned_officer_id,
                        f"Task Progress: {complaint.complaint_ref}",
                        f"Field worker {g.user.full_name} posted progress: {progress_notes}",
                        link=f"/officer/complaints/{complaint.id}",
                        notification_type='status_changed',
                        complaint_id=complaint.id,
                        commit=False,
                    )
                db.session.commit()
                success_msg = "Progress update recorded successfully."

            elif action == 'submit_completion':
                if not remarks:
                    if is_ajax:
                        return jsonify({'success': False, 'message': "Please provide completion notes describing work executed."}), 400
                    flash("Please provide completion notes describing work executed.", "danger")
                    return redirect(url_for('worker.task_detail', complaint_id=complaint.id))

                after_img = request.files.get('after_image')
                if not after_img or after_img.filename == '':
                    existing_after = ComplaintAttachment.query.filter_by(
                        complaint_id=complaint.id, attachment_type='after_work'
                    ).first()
                    if not existing_after:
                        if is_ajax:
                            return jsonify({'success': False, 'message': "A completed work photo (after-work proof) is required for submission."}), 400
                        flash("A completed work photo (after-work proof) is required for submission.", "danger")
                        return redirect(url_for('worker.task_detail', complaint_id=complaint.id))
                else:
                    saved = save_uploaded_file(after_img, 'proofs')
                    if saved:
                        db.session.add(ComplaintAttachment(
                            complaint_id=complaint.id,
                            uploaded_by_user_id=g.user.id,
                            attachment_type='after_work',
                            filename=saved['filename'],
                            original_name=saved['original_name'],
                            file_path=saved['file_path'],
                            file_size=saved['file_size'],
                            mime_type=saved['mime_type'],
                            file_data=saved.get('file_data'),
                            remarks='Completed work site photo'
                        ))

                old_status = complaint.status
                comp_remarks = f"Work completed: {remarks}. Awaiting officer verification."
                complaint.status = 'Verification Pending'
                assignment.status = 'Completed'
                assignment.completed_at = datetime.utcnow()
                complaint.updated_at = datetime.utcnow()
                db.session.add(ComplaintStatusHistory(
                    complaint_id=complaint.id,
                    changed_by_user_id=g.user.id,
                    previous_status=old_status,
                    new_status='Verification Pending',
                    remarks=comp_remarks
                ))

                if complaint.assigned_officer_id:
                    create_notification(
                        complaint.assigned_officer_id,
                        f"Work Submitted for Verification: {complaint.complaint_ref}",
                        f"Worker {g.user.full_name} has completed work on '{complaint.title}' and submitted verification evidence.",
                        link=f"/officer/complaints/{complaint.id}",
                        notification_type='verification_pending',
                        complaint_id=complaint.id,
                        commit=False,
                    )
                elif complaint.department_id:
                    notify_department_officers(
                        complaint.department_id,
                        f"Work Submitted for Verification: {complaint.complaint_ref}",
                        f"Worker {g.user.full_name} has completed work on '{complaint.title}' and submitted verification evidence.",
                        link=f"/officer/complaints/{complaint.id}",
                        notification_type='verification_pending',
                        complaint_id=complaint.id,
                        commit=False,
                    )

                create_notification(
                    complaint.citizen_id,
                    f"Work Completed: {complaint.complaint_ref}",
                    f"Field repairs for '{complaint.title}' are complete and currently undergoing department officer verification.",
                    link=f"/citizen/complaints/{complaint.id}",
                    notification_type='status_changed',
                    complaint_id=complaint.id,
                    commit=False,
                )

                notify_admins(
                    title=f"Completion Evidence Submitted: {complaint.complaint_ref}",
                    message=f"Technician {g.user.full_name} submitted completion evidence for {complaint.complaint_ref}. Pending officer verification.",
                    link=f"/admin/complaints/{complaint.id}",
                    notification_type='verification_pending',
                    complaint_id=complaint.id,
                    commit=False,
                )

                log_action(
                    user_id=g.user.id,
                    action='UPDATE_STATUS',
                    entity_type='complaint',
                    entity_id=complaint.id,
                    details={'from': old_status, 'to': 'Verification Pending', 'remarks': comp_remarks},
                    commit=False,
                )
                db.session.commit()
                success_msg = "Work submitted successfully! Now pending officer verification."

            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': success_msg or "Task updated.",
                    'status': complaint.status,
                    'reload_sections': True
                })
            if success_msg:
                flash(success_msg, "info" if action == 'update_progress' else "success")

        except Exception as e:
            db.session.rollback()
            if is_ajax:
                return jsonify({'success': False, 'message': f"Update failed: {str(e)}"}), 400
            flash(f"Update failed: {str(e)}", "danger")

        return redirect(url_for('worker.task_detail', complaint_id=complaint.id))
        
    stages = get_complaint_9_stage_timeline(complaint)
    return render_template(
        'worker/task_detail.html',
        complaint=complaint,
        assignment=assignment,
        history=history,
        attachments=attachments,
        stages=stages
    )

@worker_bp.route('/history')
def history():
    worker_user_id = g.user.id
    assignments = ComplaintAssignment.query.filter_by(
        assigned_to_user_id=worker_user_id,
        status='Completed'
    ).order_by(ComplaintAssignment.completed_at.desc()).all()
    
    return render_template('worker/history.html', assignments=assignments)

@worker_bp.route('/notifications')
def notifications():
    from app.models.notification import Notification
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(Notification.created_at.desc()).all()
    return render_template('worker/notifications.html', notifications=notifs)

@worker_bp.route('/profile', methods=['GET', 'POST'])
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
        msg = "Worker profile updated successfully."
        if _is_api_or_ajax():
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('worker.profile'))
    return render_template('worker/profile.html', user=user)
