import io
import csv
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, Response
from app import db
from app.models.complaint import Complaint
from app.models.workflow import Worker, ComplaintAssignment
from app.models.user import User
from app.services.complaint_service import (
    transition_complaint_status,
    assign_complaint_to_worker,
    officer_verify_work,
    get_complaint_9_stage_timeline
)
from app.services.audit_service import log_action
from app.utils.decorators import login_required, role_required

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
        
    query = Complaint.query.filter_by(department_id=dept_id).filter(
        (Complaint.assigned_officer_id == g.user.id) | (Complaint.assigned_officer_id.is_(None))
    ) if dept_id else Complaint.query.filter_by(id=-1)
    
    total = query.count()
    new_complaints = query.filter(Complaint.status.in_(['Submitted', 'Assigned to Department'])).count()
    pending = query.filter(Complaint.status.in_(['Submitted', 'Under Review', 'Assigned to Department'])).count()
    assigned = query.filter(Complaint.status.in_(['Assigned to Worker', 'Assigned'])).count()
    in_progress = query.filter(Complaint.status.in_(['In Progress', 'Work Started', 'Rework Required'])).count()
    completed = query.filter(Complaint.status.in_(['Work Completed', 'Verification Pending'])).count()
    resolved = query.filter_by(status='Resolved').count()
    overdue = query.filter((Complaint.is_escalated == True) | (Complaint.status == 'Escalated')).count()
    
    recent_complaints = query.order_by(Complaint.created_at.desc()).limit(6).all()
    dept_workers = Worker.query.filter_by(department_id=dept_id).all() if dept_id else []
    
    stats = {
        'total': total,
        'new': new_complaints,
        'pending': pending,
        'assigned': assigned,
        'in_progress': in_progress,
        'completed': completed,
        'resolved': resolved,
        'overdue': overdue
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
    query = Complaint.query.filter_by(department_id=dept_id).filter(
        (Complaint.assigned_officer_id == g.user.id) | (Complaint.assigned_officer_id.is_(None))
    ) if dept_id else Complaint.query.filter_by(id=-1)
    
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
        
    complaint_list = query.order_by(Complaint.created_at.desc()).all()
    
    return render_template(
        'officer/complaints.html',
        complaints=complaint_list,
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
        flash(f"Complaint #{complaint_id} was not found in your authorized department schedule.", "warning")
        return redirect(url_for('officer.complaints'))

    history = complaint.status_history.all()
    attachments = complaint.attachments.all()
    workers = Worker.query.filter_by(department_id=dept_id, is_available=True).all()
    stages = get_complaint_9_stage_timeline(complaint)
    
    if request.method == 'POST':
        action = request.form.get('action')
        remarks = request.form.get('remarks', '').strip()
        
        try:
            if action == 'accept':
                transition_complaint_status(complaint, 'Officer Accepted', g.user, remarks=remarks or "Accepted by Department Officer")
                flash("Complaint accepted into department schedule.", "success")
                
            elif action == 'reject':
                reason = request.form.get('rejection_reason', '').strip()
                if not reason:
                    flash("Mandatory rejection reason required.", "danger")
                    return redirect(url_for('officer.complaint_detail', complaint_id=complaint.id))
                transition_complaint_status(complaint, 'Rejected', g.user, remarks=remarks, rejection_reason=reason)
                flash("Complaint rejected.", "info")
                
            elif action == 'set_priority':
                priority = request.form.get('priority')
                if priority in ['low', 'medium', 'high', 'urgent']:
                    complaint.priority = priority
                    db.session.commit()
                    log_action(g.user.id, 'OFFICER_UPDATE_PRIORITY', 'complaint', complaint.id, details={'priority': priority})
                    flash(f"Priority updated to {priority.upper()}.", "success")
                    
            elif action == 'assign_worker':
                worker_user_id = request.form.get('worker_user_id', type=int)
                instructions = request.form.get('instructions', '').strip()
                if not worker_user_id:
                    flash("Please select an available field worker belonging to your department.", "danger")
                else:
                    assign_complaint_to_worker(complaint, worker_user_id, g.user, instructions)
                    flash("Field technician assigned successfully.", "success")
                    
            elif action == 'verify_resolve':
                officer_verify_work(complaint, g.user, action='approve', remarks=remarks)
                flash("Work verified and complaint successfully resolved!", "success")
                
            elif action == 'return_rework':
                rework_reason = request.form.get('rework_reason', request.form.get('return_remarks', '')).strip()
                if not rework_reason:
                    flash("Please provide a mandatory reason for returning work for rework.", "danger")
                    return redirect(url_for('officer.complaint_detail', complaint_id=complaint.id))
                officer_verify_work(complaint, g.user, action='rework', remarks=remarks, rework_reason=rework_reason)
                flash("Task returned to field worker for rework.", "warning")
                
        except Exception as e:
            db.session.rollback()
            flash(f"Action failed: {str(e)}", "danger")
            
        return redirect(url_for('officer.complaint_detail', complaint_id=complaint.id))
        
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
    pending = len([c for c in complaints if c.status in ['Submitted', 'Under Review', 'Accepted', 'Assigned', 'In Progress']])
    
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
    query = Complaint.query.filter_by(department_id=dept_id, status='Submitted') if dept_id else Complaint.query.filter_by(id=-1)
    incoming_list = query.order_by(Complaint.created_at.desc()).all()
    return render_template('officer/complaints.html', complaints=incoming_list, current_status='Submitted', page_title='Incoming Complaints Requiring Review')

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
        flash("Officer profile updated successfully.", "success")
        return redirect(url_for('officer.profile'))
    return render_template('officer/profile.html', user=user)
