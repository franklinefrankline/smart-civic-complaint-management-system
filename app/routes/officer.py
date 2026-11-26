import io
import csv
import time
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, Response, jsonify, current_app
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
    COMPLETED_PENDING_VERIF_STATUSES,
    IN_PROGRESS_STATUSES,
)
from app.services.sla_service import check_and_escalate_overdue_complaints
from app.services.audit_service import log_action
from app.utils.decorators import login_required, role_required, _is_api_or_ajax
from app.utils.helpers import validate_email, validate_mobile_number

officer_bp = Blueprint('officer', __name__)

@officer_bp.before_request
@login_required
@role_required('officer')
def before_request():
    pass

def _officer_dept_scope_filter(dept_id):
    return (Complaint.department_id == dept_id) & (
        (Complaint.assigned_officer_id == g.user.id) | (Complaint.assigned_officer_id.is_(None))
    )


def _escalated_or_overdue_expr(now=None):
    now = now or datetime.utcnow()
    return (
        (Complaint.is_escalated == True)
        | (Complaint.status == 'Escalated')
        | (
            Complaint.status.notin_(['Resolved', 'Rejected'])
            & Complaint.sla_due_date.isnot(None)
            & (Complaint.sla_due_date < now)
        )
    )


_LAST_SLA_SWEEP_TS = 0.0


def _sync_overdue_escalations(force=False):
    global _LAST_SLA_SWEEP_TS
    now_mono = time.monotonic()
    if not force and not current_app.config.get('TESTING') and (now_mono - _LAST_SLA_SWEEP_TS) < 60.0:
        return
    try:
        check_and_escalate_overdue_complaints()
        _LAST_SLA_SWEEP_TS = now_mono
    except Exception:
        db.session.rollback()


def _render_officer_queue(
    extra_filter=None,
    *,
    page_title='Department Complaint Queue',
    page_subtitle=None,
    default_status=None,
    allow_status_filter=True,
    order_clauses=None,
    filter_action=None,
    reset_url=None,
    empty_message=None,
):
    dept_id = g.user.department_id
    if dept_id:
        query = (
            Complaint.query.filter(_officer_dept_scope_filter(dept_id))
            .options(joinedload(Complaint.category), joinedload(Complaint.citizen), joinedload(Complaint.assigned_worker))
        )
        if extra_filter is not None:
            query = query.filter(extra_filter)
    else:
        query = Complaint.query.filter_by(id=-1)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            (Complaint.complaint_ref.ilike(f'%{search}%')) |
            (Complaint.title.ilike(f'%{search}%')) |
            (Complaint.description.ilike(f'%{search}%'))
        )

    status = request.args.get('status') if allow_status_filter else default_status
    if allow_status_filter and status:
        if status == 'Escalated':
            query = query.filter(_escalated_or_overdue_expr())
        elif status in COMPLETED_PENDING_VERIF_STATUSES:
            query = query.filter(Complaint.status.in_(COMPLETED_PENDING_VERIF_STATUSES))
        else:
            query = query.filter_by(status=status)

    priority = request.args.get('priority')
    if priority:
        query = query.filter_by(priority=priority)

    clauses = order_clauses or (Complaint.created_at.desc(),)
    page = max(1, request.args.get('page', 1, type=int))
    pagination = query.order_by(*clauses).paginate(page=page, per_page=25, error_out=False)

    return render_template(
        'officer/complaints.html',
        complaints=pagination.items,
        pagination=pagination,
        current_status=status,
        current_priority=priority,
        search_query=search,
        page_title=page_title,
        page_subtitle=page_subtitle,
        filter_action=filter_action or url_for('officer.complaints'),
        reset_url=reset_url or url_for('officer.complaints'),
        show_status_filter=allow_status_filter,
        empty_message=empty_message,
    )


@officer_bp.route('/dashboard')
def dashboard():
    dept_id = g.user.department_id
    if not dept_id:
        flash("You are not currently assigned to any civic department. Please contact an administrator.", "warning")

    if dept_id:
        _sync_overdue_escalations()
        dept_filter = _officer_dept_scope_filter(dept_id)
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
    return _render_officer_queue(
        page_title='Department Complaint Queue',
        empty_message='No complaints found matching the selected filters.',
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
    stages = get_complaint_9_stage_timeline(complaint, history=history)
        
    return render_template(
        'officer/complaint_detail.html',
        complaint=complaint,
        history=history,
        attachments=attachments,
        workers=workers,
        stages=stages
    )

def _get_department_worker_for_officer(worker_id, dept_id):
    """Fetch a worker and enforce strict department + role isolation for Department Officers."""
    worker = Worker.query.options(joinedload(Worker.user), joinedload(Worker.department)).filter_by(id=worker_id).first()
    if not worker or not worker.user:
        return None, ("Field worker record not found.", 404)
    if worker.department_id != dept_id or worker.user.role != 'worker':
        return None, ("Access denied: You can only manage field workers belonging to your own department.", 403)
    return worker, None


@officer_bp.route('/workers', methods=['GET', 'POST'])
@officer_bp.route('/manage-workers', methods=['GET', 'POST'])
def workers():
    dept_id = g.user.department_id
    is_ajax = _is_api_or_ajax()

    if not dept_id:
        msg = "You are not currently assigned to any civic department. Contact an administrator before managing field workers."
        if request.method == 'POST':
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 403
            flash(msg, "danger")
            return redirect(url_for('officer.dashboard'))
        flash(msg, "warning")
        return render_template(
            'officer/workers.html',
            workers=[],
            department=None,
            stats={'total': 0, 'active': 0, 'available': 0, 'active_tasks': 0},
            assignable_complaints=[],
            search_query='',
            current_status='',
        )

    if request.method == 'POST':
        payload = request.get_json(silent=True) if request.is_json else request.form
        action = (payload.get('action') or '').strip()

        # Backend security enforcement: reject any tampered role or cross-department parameter
        submitted_role = (payload.get('role') or '').strip().lower()
        if submitted_role and submitted_role != 'worker':
            err_msg = "Access denied: Department Officers can only create and manage Field Worker accounts."
            log_action(g.user.id, 'BLOCKED_OFFICER_PRIVILEGE_ESCALATION', 'user', g.user.id, details={'attempted_role': submitted_role})
            if is_ajax:
                return jsonify({'success': False, 'message': err_msg}), 403
            flash(err_msg, "danger")
            return redirect(url_for('officer.workers'))

        submitted_dept = payload.get('department_id')
        if submitted_dept is not None and str(submitted_dept).strip() != '':
            if str(submitted_dept).strip() != str(dept_id):
                err_msg = "Access denied: You can only add or manage workers within your assigned department."
                log_action(g.user.id, 'BLOCKED_CROSS_DEPARTMENT_WORKER_OP', 'department', dept_id, details={'attempted_dept': str(submitted_dept)})
                if is_ajax:
                    return jsonify({'success': False, 'message': err_msg}), 403
                flash(err_msg, "danger")
                return redirect(url_for('officer.workers'))

        try:
            if action == 'add_worker':
                full_name = (payload.get('full_name') or '').strip()
                email = (payload.get('email') or '').strip()
                mobile_raw = (payload.get('mobile') or '').strip()
                employee_id = (payload.get('employee_id') or '').strip().upper()
                designation = (payload.get('designation') or '').strip() or 'Field Technician'
                password = payload.get('password') or ''
                status_val = (payload.get('account_status') or 'active').strip().lower()
                is_active = status_val != 'inactive'
                require_reset = str(payload.get('require_reset') or '').lower() in ('1', 'true', 'on', 'yes')

                err_msg = None
                err_field = None
                clean_email = email.lower()
                clean_mobile = mobile_raw

                if not full_name:
                    err_msg, err_field = "Full Name is required.", "full_name"
                elif not email:
                    err_msg, err_field = "Email Address is required.", "email"
                else:
                    ok_email, email_res = validate_email(email)
                    if not ok_email:
                        err_msg, err_field = email_res, "email"
                    else:
                        clean_email = email_res

                if not err_msg:
                    if not mobile_raw:
                        err_msg, err_field = "Phone Number is required.", "mobile"
                    else:
                        ok_mobile, mobile_res = validate_mobile_number(mobile_raw)
                        if not ok_mobile:
                            err_msg, err_field = mobile_res, "mobile"
                        else:
                            clean_mobile = mobile_res

                if not err_msg and not employee_id:
                    err_msg, err_field = "Employee ID is required.", "employee_id"
                if not err_msg and len(password) < 6:
                    err_msg, err_field = "Password must be at least 6 characters long.", "password"

                if not err_msg:
                    if User.query.filter_by(email=clean_email).first():
                        err_msg, err_field = "A user with this email address already exists.", "email"
                    elif User.query.filter_by(mobile_number=clean_mobile).first():
                        err_msg, err_field = "A user with this phone number already exists.", "mobile"
                    elif Worker.query.filter_by(employee_id=employee_id).first():
                        err_msg, err_field = "This Employee ID is already assigned to another worker.", "employee_id"

                if err_msg:
                    if is_ajax:
                        return jsonify({'success': False, 'message': err_msg, 'field': err_field}), 400
                    flash(err_msg, "danger")
                    return redirect(url_for('officer.workers'))

                new_user = User(
                    full_name=full_name,
                    email=clean_email,
                    mobile_number=clean_mobile,
                    role='worker',
                    department_id=dept_id,
                    is_active=is_active,
                    is_password_reset_required=require_reset,
                    password_changed_at=None if require_reset else datetime.utcnow(),
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.flush()

                new_worker = Worker(
                    user_id=new_user.id,
                    department_id=dept_id,
                    employee_id=employee_id,
                    designation=designation,
                    is_available=is_active,
                    active_task_count=0,
                    completed_task_count=0,
                )
                db.session.add(new_worker)
                db.session.flush()

                log_action(
                    g.user.id,
                    'OFFICER_CREATE_WORKER',
                    'worker',
                    new_worker.id,
                    details={'email': clean_email, 'employee_id': employee_id, 'dept_id': dept_id, 'is_active': is_active},
                    commit=False,
                )
                db.session.commit()

                msg = f"Field worker '{full_name}' ({employee_id}) created in {g.user.department.name if g.user.department else 'your department'}."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'worker': new_worker.to_dict(), 'reload_sections': True})
                flash(msg, "success")

            elif action == 'edit_worker':
                worker_id = int(payload.get('worker_id') or 0)
                worker, err = _get_department_worker_for_officer(worker_id, dept_id)
                if err:
                    if is_ajax:
                        return jsonify({'success': False, 'message': err[0]}), err[1]
                    flash(err[0], "danger")
                    return redirect(url_for('officer.workers'))

                full_name = (payload.get('full_name') or '').strip()
                email = (payload.get('email') or '').strip()
                mobile_raw = (payload.get('mobile') or '').strip()
                employee_id = (payload.get('employee_id') or '').strip().upper()
                designation = (payload.get('designation') or '').strip() or 'Field Technician'
                new_password = payload.get('password') or ''
                status_val = (payload.get('account_status') or ('active' if worker.user.is_active else 'inactive')).strip().lower()
                is_active = status_val != 'inactive'
                is_available_raw = payload.get('is_available')
                is_available = is_active and (str(is_available_raw).lower() in ('1', 'true', 'on', 'yes', 'available') if is_available_raw is not None else worker.is_available)

                err_msg = None
                err_field = None
                clean_email = worker.user.email
                clean_mobile = worker.user.mobile_number

                if not full_name:
                    err_msg, err_field = "Full Name is required.", "full_name"
                else:
                    ok_email, email_res = validate_email(email)
                    if not ok_email:
                        err_msg, err_field = email_res, "email"
                    else:
                        clean_email = email_res

                if not err_msg:
                    ok_mobile, mobile_res = validate_mobile_number(mobile_raw)
                    if not ok_mobile:
                        err_msg, err_field = mobile_res, "mobile"
                    else:
                        clean_mobile = mobile_res

                if not err_msg and not employee_id:
                    err_msg, err_field = "Employee ID is required.", "employee_id"
                if not err_msg and new_password and len(new_password) < 6:
                    err_msg, err_field = "New password must be at least 6 characters.", "password"

                if not err_msg:
                    dup_email = User.query.filter(User.email == clean_email, User.id != worker.user_id).first()
                    dup_mobile = User.query.filter(User.mobile_number == clean_mobile, User.id != worker.user_id).first()
                    dup_emp = Worker.query.filter(Worker.employee_id == employee_id, Worker.id != worker.id).first()
                    if dup_email:
                        err_msg, err_field = "Another user already uses this email address.", "email"
                    elif dup_mobile:
                        err_msg, err_field = "Another user already uses this phone number.", "mobile"
                    elif dup_emp:
                        err_msg, err_field = "Another worker already uses this Employee ID.", "employee_id"

                if err_msg:
                    if is_ajax:
                        return jsonify({'success': False, 'message': err_msg, 'field': err_field}), 400
                    flash(err_msg, "danger")
                    return redirect(url_for('officer.workers'))

                worker.user.full_name = full_name
                worker.user.email = clean_email
                worker.user.mobile_number = clean_mobile
                worker.user.is_active = is_active
                worker.employee_id = employee_id
                worker.designation = designation
                worker.is_available = is_available
                if new_password:
                    worker.user.set_password(new_password)
                    worker.user.password_changed_at = datetime.utcnow()

                log_action(
                    g.user.id,
                    'OFFICER_UPDATE_WORKER',
                    'worker',
                    worker.id,
                    details={'email': clean_email, 'employee_id': employee_id, 'is_active': is_active, 'is_available': is_available},
                    commit=False,
                )
                db.session.commit()

                msg = f"Worker '{full_name}' updated successfully."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'worker': worker.to_dict(), 'reload_sections': True})
                flash(msg, "success")

            elif action == 'toggle_status':
                worker_id = int(payload.get('worker_id') or 0)
                worker, err = _get_department_worker_for_officer(worker_id, dept_id)
                if err:
                    if is_ajax:
                        return jsonify({'success': False, 'message': err[0]}), err[1]
                    flash(err[0], "danger")
                    return redirect(url_for('officer.workers'))

                worker.user.is_active = not bool(worker.user.is_active)
                if not worker.user.is_active:
                    worker.is_available = False
                else:
                    worker.is_available = True

                log_action(
                    g.user.id,
                    'OFFICER_TOGGLE_WORKER_STATUS',
                    'worker',
                    worker.id,
                    details={'is_active': worker.user.is_active},
                    commit=False,
                )
                db.session.commit()

                state_label = "activated" if worker.user.is_active else "deactivated"
                msg = f"Worker '{worker.user.full_name}' account {state_label}."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'is_active': worker.user.is_active, 'reload_sections': True})
                flash(msg, "info")

            elif action == 'toggle_availability':
                worker_id = int(payload.get('worker_id') or 0)
                worker, err = _get_department_worker_for_officer(worker_id, dept_id)
                if err:
                    if is_ajax:
                        return jsonify({'success': False, 'message': err[0]}), err[1]
                    flash(err[0], "danger")
                    return redirect(url_for('officer.workers'))

                if not worker.user.is_active and not worker.is_available:
                    msg = "Activate this worker account before setting duty status to Available."
                    if is_ajax:
                        return jsonify({'success': False, 'message': msg}), 400
                    flash(msg, "warning")
                    return redirect(url_for('officer.workers'))

                worker.is_available = not bool(worker.is_available)
                log_action(
                    g.user.id,
                    'OFFICER_TOGGLE_WORKER_AVAILABILITY',
                    'worker',
                    worker.id,
                    details={'is_available': worker.is_available},
                    commit=False,
                )
                db.session.commit()

                msg = f"Duty availability for '{worker.user.full_name}' updated."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'is_available': worker.is_available, 'reload_sections': True})
                flash(msg, "info")

            elif action == 'assign_complaint':
                worker_id = int(payload.get('worker_id') or 0)
                complaint_id = int(payload.get('complaint_id') or 0)
                instructions = (payload.get('instructions') or '').strip()

                worker, err = _get_department_worker_for_officer(worker_id, dept_id)
                if err:
                    if is_ajax:
                        return jsonify({'success': False, 'message': err[0]}), err[1]
                    flash(err[0], "danger")
                    return redirect(url_for('officer.workers'))

                complaint = Complaint.query.filter_by(id=complaint_id, department_id=dept_id).first()
                if not complaint:
                    msg = "Complaint not found in your department queue."
                    if is_ajax:
                        return jsonify({'success': False, 'message': msg}), 404
                    flash(msg, "danger")
                    return redirect(url_for('officer.workers'))

                assign_complaint_to_worker(complaint, worker.user_id, g.user, instructions=instructions)
                msg = f"Complaint {complaint.complaint_ref} assigned to {worker.user.full_name}."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'reload_sections': True})
                flash(msg, "success")

            else:
                if is_ajax:
                    return jsonify({'success': False, 'message': "Invalid worker management action."}), 400
                flash("Invalid worker management action.", "danger")

        except Exception as e:
            db.session.rollback()
            if is_ajax:
                return jsonify({'success': False, 'message': f"Worker operation failed: {str(e)}"}), 400
            flash(f"Worker operation failed: {str(e)}", "danger")

        return redirect(url_for('officer.workers'))

    # GET: List and filter workers belonging strictly to the officer's department
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip().lower()

    all_dept_workers = (
        Worker.query.join(Worker.user)
        .filter(Worker.department_id == dept_id, User.role == 'worker')
        .options(joinedload(Worker.user), joinedload(Worker.department))
        .order_by(User.full_name.asc())
        .all()
    )

    stats = {
        'total': len(all_dept_workers),
        'active': sum(1 for w in all_dept_workers if w.user and w.user.is_active),
        'available': sum(1 for w in all_dept_workers if w.user and w.user.is_active and w.is_available),
        'active_tasks': sum(w.active_task_count or 0 for w in all_dept_workers),
    }

    worker_list = all_dept_workers
    if search:
        s_lower = search.lower()
        worker_list = [
            w for w in worker_list
            if s_lower in (w.user.full_name or '').lower()
            or s_lower in (w.user.email or '').lower()
            or s_lower in (w.user.mobile_number or '').lower()
            or s_lower in (w.employee_id or '').lower()
            or s_lower in (w.designation or '').lower()
        ]
    if status_filter == 'active':
        worker_list = [w for w in worker_list if w.user and w.user.is_active]
    elif status_filter == 'inactive':
        worker_list = [w for w in worker_list if w.user and not w.user.is_active]
    elif status_filter == 'available':
        worker_list = [w for w in worker_list if w.user and w.user.is_active and w.is_available]
    elif status_filter == 'busy':
        worker_list = [w for w in worker_list if not w.is_available]

    assignable_complaints = (
        Complaint.query.filter(
            Complaint.department_id == dept_id,
            Complaint.status.in_(['Submitted', 'Assigned to Department', 'Officer Accepted', 'Accepted', 'Reopened']),
        )
        .order_by(Complaint.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        'officer/workers.html',
        workers=worker_list,
        department=g.user.department,
        stats=stats,
        assignable_complaints=assignable_complaints,
        search_query=search,
        current_status=status_filter,
    )

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
    return _render_officer_queue(
        Complaint.status.in_(['Submitted', 'Assigned to Department']),
        page_title='Incoming Complaints Requiring Review',
        page_subtitle='Newly submitted or admin-routed grievances awaiting department acceptance or worker dispatch.',
        default_status='Assigned to Department',
        allow_status_filter=False,
        order_clauses=(Complaint.created_at.desc(),),
        filter_action=url_for('officer.incoming'),
        reset_url=url_for('officer.incoming'),
        empty_message='No incoming complaints are currently awaiting department review.',
    )


@officer_bp.route('/verification')
def verification():
    return _render_officer_queue(
        Complaint.status.in_(COMPLETED_PENDING_VERIF_STATUSES),
        page_title='Work Verification Queue',
        page_subtitle='Completed field work submitted by technicians awaiting your verification and resolution approval.',
        default_status='Verification Pending',
        allow_status_filter=False,
        order_clauses=(Complaint.updated_at.desc(),),
        filter_action=url_for('officer.verification'),
        reset_url=url_for('officer.verification'),
        empty_message='No completed tasks are currently awaiting work verification.',
    )


@officer_bp.route('/escalations')
def escalations():
    _sync_overdue_escalations(force=True)
    return _render_officer_queue(
        _escalated_or_overdue_expr(),
        page_title='Escalated Department Complaints',
        page_subtitle='SLA-overdue and administratively escalated complaints requiring immediate supervisor action.',
        default_status='Escalated',
        allow_status_filter=False,
        order_clauses=(Complaint.escalated_at.asc(), Complaint.created_at.asc()),
        filter_action=url_for('officer.escalations'),
        reset_url=url_for('officer.escalations'),
        empty_message='No escalated or overdue complaints in your department right now.',
    )

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
