from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app import db
from app.models.complaint import Complaint
from app.models.workflow import ComplaintAssignment, Worker
from app.models.attachment import ComplaintAttachment
from app.services.complaint_service import transition_complaint_status, get_complaint_9_stage_timeline
from app.services.notification_service import create_notification
from app.services.audit_service import log_action
from app.utils.helpers import save_uploaded_file
from app.utils.decorators import login_required, role_required

worker_bp = Blueprint('worker', __name__)

@worker_bp.before_request
@login_required
@role_required('worker')
def before_request():
    pass

@worker_bp.route('/dashboard')
def dashboard():
    worker_user_id = g.user.id
    
    # Query tasks assigned to this worker
    assignments = ComplaintAssignment.query.filter_by(assigned_to_user_id=worker_user_id).all()
    assigned_complaint_ids = [a.complaint_id for a in assignments]
    
    query = Complaint.query.filter(Complaint.id.in_(assigned_complaint_ids)) if assigned_complaint_ids else Complaint.query.filter_by(id=-1)
    
    total = query.count()
    new_tasks = query.filter_by(status='Assigned').count()
    in_progress = query.filter_by(status='In Progress').count()
    completed = query.filter(Complaint.status.in_(['Work Completed', 'Verification Pending', 'Resolved'])).count()
    
    active_tasks = query.filter(Complaint.status.in_(['Assigned', 'In Progress'])).order_by(Complaint.priority.desc()).all()
    
    stats = {
        'total': total,
        'new_tasks': new_tasks,
        'in_progress': in_progress,
        'completed': completed
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
    assignments = ComplaintAssignment.query.filter_by(assigned_to_user_id=worker_user_id).all()
    assigned_complaint_ids = [a.complaint_id for a in assignments]
    
    query = Complaint.query.filter(Complaint.id.in_(assigned_complaint_ids)) if assigned_complaint_ids else Complaint.query.filter_by(id=-1)
    
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
        
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Complaint.complaint_ref.ilike(f'%{search}%')) |
            (Complaint.title.ilike(f'%{search}%'))
        )
        
    task_list = query.order_by(Complaint.created_at.desc()).all()
    return render_template('worker/tasks.html', tasks=task_list, current_status=status, search_query=search)

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
        
        try:
            if action == 'start_work':
                # Worker starts field work
                transition_complaint_status(complaint, 'In Progress', g.user, remarks=remarks or "Field technician started site work.")
                assignment.status = 'In Progress'
                
                # Check for "Before Work" image
                before_img = request.files.get('before_image')
                if before_img and before_img.filename != '':
                    saved = save_uploaded_file(before_img, 'proofs')
                    if saved:
                        att = ComplaintAttachment(
                            complaint_id=complaint.id,
                            uploaded_by_user_id=g.user.id,
                            attachment_type='before_work',
                            filename=saved['filename'],
                            original_name=saved['original_name'],
                            file_path=saved['file_path'],
                            file_size=saved['file_size'],
                            mime_type=saved['mime_type'],
                            remarks='Pre-work site condition'
                        )
                        db.session.add(att)
                        
                db.session.commit()
                flash("Task marked In Progress.", "success")
                
            elif action == 'update_progress':
                progress_notes = request.form.get('progress_notes', '').strip()
                if not progress_notes:
                    flash("Please provide progress details.", "danger")
                    return redirect(url_for('worker.task_detail', complaint_id=complaint.id))
                hist = ComplaintStatusHistory(
                    complaint_id=complaint.id,
                    changed_by_user_id=g.user.id,
                    previous_status=complaint.status,
                    new_status=complaint.status,
                    remarks=f"Progress Update: {progress_notes}"
                )
                db.session.add(hist)
                db.session.commit()
                if complaint.assigned_officer_id:
                    create_notification(
                        complaint.assigned_officer_id,
                        f"Task Progress: {complaint.complaint_ref}",
                        f"Field worker {g.user.full_name} posted progress: {progress_notes}",
                        link=f"/officer/complaints/{complaint.id}"
                    )
                flash("Progress update recorded successfully.", "info")

            elif action == 'submit_completion':
                # Worker finishes work and submits for officer verification
                if not remarks:
                    flash("Please provide completion notes describing work executed.", "danger")
                    return redirect(url_for('worker.task_detail', complaint_id=complaint.id))
                    
                after_img = request.files.get('after_image')
                if not after_img or after_img.filename == '':
                    # Check if an after_work image was already uploaded earlier
                    existing_after = ComplaintAttachment.query.filter_by(
                        complaint_id=complaint.id, attachment_type='after_work'
                    ).first()
                    if not existing_after:
                        flash("A completed work photo (after-work proof) is required for submission.", "danger")
                        return redirect(url_for('worker.task_detail', complaint_id=complaint.id))
                else:
                    saved = save_uploaded_file(after_img, 'proofs')
                    if saved:
                        att = ComplaintAttachment(
                            complaint_id=complaint.id,
                            uploaded_by_user_id=g.user.id,
                            attachment_type='after_work',
                            filename=saved['filename'],
                            original_name=saved['original_name'],
                            file_path=saved['file_path'],
                            file_size=saved['file_size'],
                            mime_type=saved['mime_type'],
                            remarks='Completed work site photo'
                        )
                        db.session.add(att)
                        
                transition_complaint_status(complaint, 'Verification Pending', g.user, remarks=f"Work completed: {remarks}. Awaiting officer verification.")
                assignment.status = 'Completed'
                assignment.completed_at = datetime.utcnow()
                
                # Notify Department Officer
                if complaint.assigned_officer_id:
                    create_notification(
                        complaint.assigned_officer_id,
                        f"Work Submitted for Verification: {complaint.complaint_ref}",
                        f"Worker {g.user.full_name} has completed work on '{complaint.title}' and submitted verification evidence.",
                        link=f"/officer/complaints/{complaint.id}",
                        notification_type='status_changed'
                    )
                    
                # Notify Citizen
                create_notification(
                    complaint.citizen_id,
                    f"Work Completed: {complaint.complaint_ref}",
                    f"Field repairs for '{complaint.title}' are complete and currently undergoing department officer verification.",
                    link=f"/citizen/complaints/{complaint.id}",
                    notification_type='status_changed'
                )
                
                db.session.commit()
                flash("Work submitted successfully! Now pending officer verification.", "success")
                
        except Exception as e:
            db.session.rollback()
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
        flash("Worker profile updated successfully.", "success")
        return redirect(url_for('worker.profile'))
    return render_template('worker/profile.html', user=user)
