import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, Response, jsonify
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from app import db
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.user import User
from app.models.workflow import Worker, ComplaintAssignment, ComplaintStatusHistory
from app.models.attachment import ComplaintAttachment
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.models.feedback import Feedback
from app.models.contact import ContactMessage
from app.services.complaint_service import (
    transition_complaint_status,
    assign_complaint_to_worker,
    assign_department_officer,
    get_complaint_9_stage_timeline,
    get_complaint_aggregate_counts,
    build_admin_analytics_payload,
    PENDING_STATUSES,
    IN_PROGRESS_STATUSES,
)
from app.services.audit_service import log_action
from app.utils.decorators import login_required, role_required, _is_api_or_ajax

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
@role_required('admin')
def before_request():
    pass

@admin_bp.route('/dashboard')
def dashboard():
    # Single SQL aggregate for citizen count and pending password resets
    user_row = db.session.query(
        func.sum(case((User.role == 'citizen', 1), else_=0)).label('citizens'),
        func.sum(case((User.is_password_reset_required == True, 1), else_=0)).label('resets'),
    ).one()

    recent_complaints = (
        Complaint.query.options(
            joinedload(Complaint.category),
            joinedload(Complaint.department),
            joinedload(Complaint.citizen),
        )
        .order_by(Complaint.created_at.desc())
        .limit(7)
        .all()
    )
    recent_activities = (
        AuditLog.query.options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )

    analytics = build_admin_analytics_payload()
    summary = analytics['summary']
    dept_labels = [r['name'] for r in analytics['dept_rows']]
    dept_complaint_counts = [r['total'] for r in analytics['dept_rows']]
    cat_labels = analytics['cat_labels'] if analytics['cat_labels'] else analytics['all_cat_labels'][:6]
    cat_counts = analytics['cat_totals'] if analytics['cat_totals'] else analytics['all_cat_totals'][:6]

    stats = {
        'citizens': int(user_row.citizens or 0),
        'total': summary['total'],
        'new': summary['submitted'],
        'pending': summary['pending'],
        'in_progress': summary['in_progress'],
        'resolved': summary['resolved'],
        'rejected': summary['rejected'],
        'overdue': summary['overdue'],
        'pending_password_resets': int(user_row.resets or 0)
    }

    chart_data = {
        'dept_labels': dept_labels,
        'dept_counts': dept_complaint_counts,
        'cat_labels': cat_labels,
        'cat_counts': cat_counts,
        'status_counts': [summary['pending'], summary['in_progress'], summary['resolved'], summary['rejected']]
    }

    new_complaints_queue = (
        Complaint.query.filter(
            (Complaint.status == 'Submitted') | (Complaint.assigned_officer_id.is_(None))
        )
        .options(
            joinedload(Complaint.category),
            joinedload(Complaint.department),
            joinedload(Complaint.citizen),
        )
        .order_by(Complaint.created_at.desc())
        .limit(50)
        .all()
    )

    contact_messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(20).all()
    if len(contact_messages) < 20:
        unread_contact_count = sum(1 for m in contact_messages if not m.is_read)
    else:
        unread_contact_count = ContactMessage.query.filter_by(is_read=False).count()

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_complaints=recent_complaints,
        new_complaints_queue=new_complaints_queue,
        recent_activities=recent_activities,
        chart_data=chart_data,
        contact_messages=contact_messages,
        unread_contact_count=unread_contact_count,
    )


@admin_bp.route('/contact-messages/<int:msg_id>/read', methods=['POST'])
def mark_contact_message_read(msg_id):
    msg = db.session.get(ContactMessage, msg_id)
    if msg:
        msg.is_read = True
        db.session.commit()
        if _is_api_or_ajax():
            unread_count = ContactMessage.query.filter_by(is_read=False).count()
            return jsonify({'success': True, 'message': "Contact inquiry marked as reviewed.", 'unread_contact_count': unread_count})
        flash("Contact inquiry marked as reviewed.", "success")
    elif _is_api_or_ajax():
        return jsonify({'success': False, 'message': "Contact inquiry not found."}), 404
    return redirect(url_for('admin.dashboard') + '#contactInquiriesCard')

@admin_bp.route('/complaints', strict_slashes=False)
@admin_bp.route('/complaint', strict_slashes=False)
def complaints():
    query = Complaint.query.options(
        joinedload(Complaint.category),
        joinedload(Complaint.department),
        joinedload(Complaint.citizen),
        joinedload(Complaint.assigned_officer),
        joinedload(Complaint.assigned_worker),
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

    department_id = request.args.get('department_id', type=int)
    if department_id:
        query = query.filter_by(department_id=department_id)

    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    priority = request.args.get('priority')
    if priority:
        query = query.filter_by(priority=priority)

    page = max(1, request.args.get('page', 1, type=int))
    pagination = query.order_by(Complaint.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    departments = Department.query.filter_by(is_active=True).all()
    categories = ComplaintCategory.query.filter_by(is_active=True).all()

    return render_template(
        'admin/complaints.html',
        complaints=pagination.items,
        pagination=pagination,
        departments=departments,
        categories=categories,
        current_status=status,
        current_dept=department_id,
        current_cat=category_id,
        current_priority=priority,
        search_query=search
    )

@admin_bp.route('/complaints/<int:complaint_id>', methods=['GET', 'POST'], strict_slashes=False)
@admin_bp.route('/complaint/<int:complaint_id>', methods=['GET', 'POST'], strict_slashes=False)
def complaint_detail(complaint_id):
    complaint = Complaint.query.get(complaint_id)
    if not complaint:
        if request.method == 'POST' and _is_api_or_ajax():
            return jsonify({'success': False, 'message': f"Complaint #{complaint_id} could not be located or has been archived."}), 404
        flash(f"Complaint #{complaint_id} could not be located or has been archived.", "warning")
        return redirect(url_for('admin.complaints'))

    if request.method == 'POST':
        action = request.form.get('action')
        remarks = request.form.get('remarks', '').strip()
        is_ajax = _is_api_or_ajax()
        success_msg = None

        try:
            if action == 'assign_department_officer':
                dept_id = request.form.get('department_id', type=int)
                officer_id = request.form.get('officer_id', type=int)
                admin_remarks = request.form.get('admin_remarks', '').strip()
                if not dept_id or not officer_id:
                    if is_ajax:
                        return jsonify({'success': False, 'message': "Please select both a department and an active department officer."}), 400
                    flash("Please select both a department and an active department officer.", "danger")
                else:
                    assign_department_officer(complaint, dept_id, officer_id, g.user, admin_remarks=admin_remarks)
                    success_msg = f"Complaint {complaint.complaint_ref} successfully assigned to Department Officer."

            elif action == 'assign_department':
                dept_id = request.form.get('department_id', type=int)
                if dept_id:
                    complaint.department_id = dept_id
                    log_action(g.user.id, 'ASSIGN_DEPARTMENT', 'complaint', complaint.id, details={'dept_id': dept_id}, commit=False)
                    db.session.commit()
                    success_msg = "Department reassigned successfully."

            elif action == 'assign_worker':
                worker_user_id = request.form.get('worker_user_id', type=int)
                instructions = request.form.get('instructions', '')
                if worker_user_id:
                    assign_complaint_to_worker(complaint, worker_user_id, g.user, instructions)
                    success_msg = "Field worker assigned successfully."

            elif action == 'change_status':
                new_status = request.form.get('new_status')
                rejection_reason = request.form.get('rejection_reason', '')
                transition_complaint_status(complaint, new_status, g.user, remarks=remarks, rejection_reason=rejection_reason)
                success_msg = f"Status updated to '{new_status}'."

            elif action == 'change_priority':
                new_priority = request.form.get('new_priority')
                if new_priority in ['low', 'medium', 'high', 'urgent']:
                    complaint.priority = new_priority
                    log_action(g.user.id, 'UPDATE_PRIORITY', 'complaint', complaint.id, details={'priority': new_priority}, commit=False)
                    db.session.commit()
                    success_msg = f"Priority changed to {new_priority.upper()}."

            elif action == 'escalate':
                transition_complaint_status(complaint, 'Escalated', g.user, remarks=remarks or "Administrative escalation")
                success_msg = "Complaint escalated."

            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': success_msg or "Action completed successfully.",
                    'status': complaint.status,
                    'priority': complaint.priority,
                    'reload_sections': action != 'change_priority'
                })
            if success_msg:
                flash(success_msg, "warning" if action == 'escalate' else "success")

        except Exception as e:
            db.session.rollback()
            if is_ajax:
                return jsonify({'success': False, 'message': f"Action failed: {str(e)}"}), 400
            flash(f"Action failed: {str(e)}", "danger")

        return redirect(url_for('admin.complaint_detail', complaint_id=complaint.id))

    history = complaint.status_history.all()
    attachments = complaint.attachments.all()
    departments = Department.query.filter_by(is_active=True).all()
    officers = User.query.filter_by(role='officer', is_active=True).options(joinedload(User.department)).all()
    workers = Worker.query.filter_by(is_available=True).options(joinedload(Worker.user), joinedload(Worker.department)).all()
    stages = get_complaint_9_stage_timeline(complaint, history=history)
        
    return render_template(
        'admin/complaint_detail.html',
        complaint=complaint,
        history=history,
        attachments=attachments,
        departments=departments,
        officers=officers,
        workers=workers,
        stages=stages
    )

@admin_bp.route('/users', methods=['GET', 'POST'])
def users():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_user':
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                      request.is_json or \
                      'application/json' in request.headers.get('Accept', '')

            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            mobile = request.form.get('mobile', '').strip()
            role = request.form.get('role', 'citizen')
            dept_id = request.form.get('department_id', type=int) if role in ['officer', 'worker'] else None
            password = request.form.get('password', 'Admin@123')
            
            email_exists = bool(User.query.filter_by(email=email).first())
            mobile_exists = bool(User.query.filter_by(mobile_number=mobile).first())

            error_msg = None
            error_field = None

            if not full_name:
                error_msg = "Full name is required."
                error_field = "full_name"
            elif not email:
                error_msg = "Email address is required."
                error_field = "email"
            elif not mobile:
                error_msg = "Mobile number is required."
                error_field = "mobile"
            elif email_exists and mobile_exists:
                error_msg = "User with this email and mobile number already exists."
                error_field = "both"
            elif email_exists:
                error_msg = "User with this email already exists."
                error_field = "email"
            elif mobile_exists:
                error_msg = "User with this mobile number already exists."
                error_field = "mobile"
            elif role in ['officer', 'worker'] and not dept_id:
                error_msg = "Please select a department for Officer or Worker role."
                error_field = "department_id"
            elif len(password) < 6:
                error_msg = "Password must be at least 6 characters."
                error_field = "password"

            if error_msg:
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': error_msg,
                        'field': error_field
                    }), 400
                else:
                    flash(error_msg, "danger")
                    role_filter = request.args.get('role')
                    search = request.args.get('search', '').strip()
                    query = User.query
                    if role_filter:
                        query = query.filter_by(role=role_filter)
                    if search:
                        query = query.filter(
                            (User.full_name.ilike(f'%{search}%')) |
                            (User.email.ilike(f'%{search}%')) |
                            (User.mobile_number.ilike(f'%{search}%'))
                        )
                    user_list = query.order_by(User.created_at.desc()).all()
                    departments_list = Department.query.filter_by(is_active=True).all()
                    return render_template(
                        'admin/users.html',
                        users=user_list,
                        departments=departments_list,
                        current_role=role_filter,
                        search_query=search,
                        modal_open=True,
                        modal_error=error_msg,
                        modal_error_field=error_field,
                        form_data=request.form
                    )

            new_user = User(
                full_name=full_name,
                email=email,
                mobile_number=mobile,
                role=role,
                department_id=dept_id,
                is_active=True,
                is_password_reset_required=True,
                password_changed_at=None
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()
            
            if role == 'worker' and dept_id:
                worker_profile = Worker(user_id=new_user.id, department_id=dept_id)
                db.session.add(worker_profile)
                
            db.session.commit()
            log_action(g.user.id, 'CREATE_USER', 'user', new_user.id, details={'role': role, 'email': email})
            flash(f"User {full_name} created successfully.", "success")

            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': f"User {full_name} created successfully."
                }), 200
            else:
                return redirect(url_for('admin.users'))
                
        elif action == 'toggle_status':
            uid = request.form.get('user_id', type=int)
            u = User.query.get(uid)
            if u and u.id != g.user.id:
                u.is_active = not u.is_active
                log_action(g.user.id, 'TOGGLE_USER_STATUS', 'user', u.id, details={'active': u.is_active}, commit=False)
                db.session.commit()
                msg = f"Account for {u.full_name} updated."
                if _is_api_or_ajax():
                    return jsonify({'success': True, 'message': msg, 'is_active': u.is_active, 'reload_sections': True})
                flash(msg, "info")
            elif _is_api_or_ajax():
                return jsonify({'success': False, 'message': "Cannot modify that account."}), 400
            redirect_to = request.referrer or url_for('admin.users')
            return redirect(redirect_to)

        elif action == 'delete_user':
            uid = request.form.get('user_id', type=int)
            u = User.query.get(uid)
            is_ajax = _is_api_or_ajax()
            if not u:
                if is_ajax:
                    return jsonify({'success': False, 'message': "User account not found."}), 404
                flash("User account not found.", "danger")
            elif u.id == g.user.id:
                if is_ajax:
                    return jsonify({'success': False, 'message': "Security restriction: You cannot delete your own active administrator account."}), 400
                flash("Security restriction: You cannot delete your own active administrator account.", "danger")
            else:
                user_name = u.full_name
                user_email = u.email

                Notification.query.filter_by(user_id=u.id).delete()
                if u.is_worker or u.worker_profile:
                    ComplaintAssignment.query.filter_by(assigned_to_user_id=u.id).delete()
                ComplaintAssignment.query.filter_by(assigned_by_user_id=u.id).delete()
                ComplaintStatusHistory.query.filter_by(changed_by_user_id=u.id).update({'changed_by_user_id': None})

                user_complaints = Complaint.query.filter_by(citizen_id=u.id).all()
                for c in user_complaints:
                    Feedback.query.filter_by(complaint_id=c.id).delete()
                    ComplaintAttachment.query.filter_by(complaint_id=c.id).delete()
                    ComplaintStatusHistory.query.filter_by(complaint_id=c.id).delete()
                    ComplaintAssignment.query.filter_by(complaint_id=c.id).delete()
                    db.session.delete(c)

                Feedback.query.filter_by(citizen_id=u.id).delete()
                ComplaintAttachment.query.filter_by(uploaded_by_user_id=u.id).delete()
                AuditLog.query.filter_by(user_id=u.id).update({'user_id': None})

                db.session.delete(u)
                log_action(g.user.id, 'DELETE_USER', 'user', uid, details={'name': user_name, 'email': user_email}, commit=False)
                db.session.commit()

                msg = f"Account for {user_name} ({user_email}) has been permanently deleted."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'reload_sections': True})
                flash(msg, "success")

            redirect_to = request.referrer or url_for('admin.users')
            return redirect(redirect_to)

        return redirect(url_for('admin.users'))

    role_filter = request.args.get('role')
    search = request.args.get('search', '').strip()

    query = User.query.options(joinedload(User.department))
    if role_filter:
        query = query.filter_by(role=role_filter)
    if search:
        query = query.filter(
            (User.full_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.mobile_number.ilike(f'%{search}%'))
        )

    page = max(1, request.args.get('page', 1, type=int))
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    departments = Department.query.filter_by(is_active=True).all()

    return render_template('admin/users.html', users=pagination.items, pagination=pagination, departments=departments, current_role=role_filter, search_query=search)

@admin_bp.route('/departments', methods=['GET', 'POST'])
def departments():
    if request.method == 'POST':
        action = request.form.get('action')
        is_ajax = _is_api_or_ajax()

        if action == 'create':
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip().upper()
            description = request.form.get('description', '').strip()
            email = request.form.get('contact_email', '').strip()
            phone = request.form.get('contact_phone', '').strip()

            if Department.query.filter_by(name=name).first() or Department.query.filter_by(code=code).first():
                if is_ajax:
                    return jsonify({'success': False, 'message': "Department with this name or code already exists."}), 400
                flash("Department with this name or code already exists.", "danger")
            else:
                dept = Department(name=name, code=code, description=description, contact_email=email, contact_phone=phone)
                db.session.add(dept)
                db.session.flush()
                log_action(g.user.id, 'CREATE_DEPARTMENT', 'department', dept.id, details={'code': code}, commit=False)
                db.session.commit()
                msg = f"Department '{name}' created successfully."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'reload_sections': True})
                flash(msg, "success")

        elif action == 'toggle':
            dept_id = request.form.get('department_id', type=int)
            d = Department.query.get(dept_id)
            if d:
                d.is_active = not d.is_active
                db.session.commit()
                if is_ajax:
                    return jsonify({'success': True, 'message': "Department status updated.", 'reload_sections': True})
                flash("Department status updated.", "info")

        elif action == 'delete':
            dept_id = request.form.get('department_id', type=int)
            d = Department.query.get(dept_id)
            if d:
                if d.complaints.count() > 0 or d.categories.count() > 0:
                    msg = "Cannot delete department because active complaints or categories are associated with it."
                    if is_ajax:
                        return jsonify({'success': False, 'message': msg}), 400
                    flash(msg, "warning")
                else:
                    db.session.delete(d)
                    log_action(g.user.id, 'DELETE_DEPARTMENT', 'department', dept_id, commit=False)
                    db.session.commit()
                    if is_ajax:
                        return jsonify({'success': True, 'message': "Department deleted safely.", 'reload_sections': True})
                    flash("Department deleted safely.", "success")

        if is_ajax:
            return jsonify({'success': False, 'message': "Invalid action or department not found."}), 400
        return redirect(url_for('admin.departments'))

    dept_list = Department.query.all()
    return render_template('admin/departments.html', departments=dept_list)

@admin_bp.route('/workers', methods=['GET', 'POST'])
def workers():
    if request.method == 'POST':
        action = request.form.get('action')
        is_ajax = _is_api_or_ajax()
        if action == 'toggle_availability':
            wid = request.form.get('worker_id', type=int)
            w = Worker.query.get(wid)
            if w:
                w.is_available = not w.is_available
                db.session.commit()
                if is_ajax:
                    return jsonify({'success': True, 'message': "Worker availability updated.", 'reload_sections': True})
                flash("Worker availability updated.", "info")
        elif action == 'add_worker':
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            mobile = request.form.get('mobile', '').strip()
            dept_id = request.form.get('department_id', type=int)
            employee_id = request.form.get('employee_id', '').strip().upper() or None
            designation = request.form.get('designation', '').strip() or 'Field Technician'
            password = request.form.get('password', 'Welcome@123')

            err_msg = None
            if not full_name or not email or not mobile or not dept_id:
                err_msg = "All fields including assigned department are required."
            elif User.query.filter_by(email=email).first():
                err_msg = "A user with this email address already exists."
            elif User.query.filter_by(mobile_number=mobile).first():
                err_msg = "A user with this mobile number already exists."
            elif employee_id and Worker.query.filter_by(employee_id=employee_id).first():
                err_msg = "A worker with this Employee ID already exists."

            if err_msg:
                if is_ajax:
                    return jsonify({'success': False, 'message': err_msg}), 400
                flash(err_msg, "danger")
            else:
                new_worker_user = User(
                    full_name=full_name,
                    email=email,
                    mobile_number=mobile,
                    role='worker',
                    department_id=dept_id,
                    is_active=True,
                    is_password_reset_required=True,
                    password_changed_at=None
                )
                new_worker_user.set_password(password)
                db.session.add(new_worker_user)
                db.session.flush()

                new_worker = Worker(
                    user_id=new_worker_user.id,
                    department_id=dept_id,
                    employee_id=employee_id,
                    designation=designation,
                    is_available=True,
                    active_task_count=0
                )
                db.session.add(new_worker)
                db.session.flush()
                log_action(g.user.id, 'CREATE_WORKER', 'worker', new_worker.id, details={'email': email, 'dept_id': dept_id}, commit=False)
                db.session.commit()

                msg = f"Field technician '{full_name}' created successfully with pending initial password reset."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'reload_sections': True})
                flash(msg, "success")
        return redirect(url_for('admin.workers'))

    worker_list = Worker.query.options(joinedload(Worker.user), joinedload(Worker.department)).all()
    departments = Department.query.filter_by(is_active=True).all()
    return render_template('admin/workers.html', workers=worker_list, departments=departments)

@admin_bp.route('/analytics')
def analytics():
    data = build_admin_analytics_payload()
    return render_template(
        'admin/analytics.html',
        summary=data['summary'],
        dept_labels=data['dept_labels'],
        dept_totals=data['dept_totals'],
        dept_resolved=data['dept_resolved'],
        dept_rows=data['dept_rows'],
        cat_labels=data['cat_labels'],
        cat_totals=data['cat_totals'],
        status_labels=data['status_labels'],
        status_totals=data['status_totals'],
        analytics_payload=data,
    )

@admin_bp.route('/audit-logs')
def audit_logs():
    query = AuditLog.query
    action_filter = request.args.get('action')
    if action_filter:
        query = query.filter_by(action=action_filter)
    logs = query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template('admin/audit_logs.html', logs=logs, current_action=action_filter)

@admin_bp.route('/export/complaints')
def export_complaints_csv():
    query = Complaint.query
    
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    dept_id = request.args.get('department_id', type=int)
    if dept_id:
        query = query.filter_by(department_id=dept_id)
        
    complaints = query.order_by(Complaint.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Reference ID', 'Title', 'Citizen', 'Category', 'Department',
        'Priority', 'Status', 'Address', 'City', 'Ward', 'Escalated',
        'Registered Date', 'Resolved Date'
    ])
    
    from app.utils.helpers import utc_to_local
    for c in complaints:
        created_local = utc_to_local(c.created_at)
        resolved_local = utc_to_local(c.resolved_at)
        writer.writerow([
            c.complaint_ref,
            c.title,
            c.citizen.full_name if c.citizen else '',
            c.category.name if c.category else '',
            c.department.name if c.department else 'Unassigned',
            c.priority.upper(),
            c.status,
            c.address or '',
            c.city or '',
            c.ward_number or '',
            'YES' if c.is_escalated else 'NO',
            created_local.strftime('%Y-%m-%d %H:%M') if created_local else '',
            resolved_local.strftime('%Y-%m-%d %H:%M') if resolved_local else ''
        ])
        
    output.seek(0)
    now_local = utc_to_local(datetime.utcnow())
    filename = f"civic_complaints_export_{now_local.strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@admin_bp.route('/citizens')
def citizens():
    search = request.args.get('search', '').strip()
    query = User.query.filter_by(role='citizen')
    if search:
        query = query.filter(
            (User.full_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.mobile_number.ilike(f'%{search}%'))
        )
    citizens_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/citizens.html', citizens=citizens_list, search_query=search)

@admin_bp.route('/officers', methods=['GET', 'POST'])
def officers():
    if request.method == 'POST':
        action = request.form.get('action')
        is_ajax = _is_api_or_ajax()
        if action == 'add_officer':
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            mobile = request.form.get('mobile', '').strip()
            dept_id = request.form.get('department_id', type=int)
            password = request.form.get('password', 'Welcome@123')

            err_msg = None
            if not full_name or not email or not mobile or not dept_id:
                err_msg = "All fields including assigned department are required."
            elif User.query.filter_by(email=email).first():
                err_msg = "A user with this email address already exists."
            elif User.query.filter_by(mobile_number=mobile).first():
                err_msg = "A user with this mobile number already exists."

            if err_msg:
                if is_ajax:
                    return jsonify({'success': False, 'message': err_msg}), 400
                flash(err_msg, "danger")
            else:
                new_officer = User(
                    full_name=full_name,
                    email=email,
                    mobile_number=mobile,
                    role='officer',
                    department_id=dept_id,
                    is_active=True,
                    is_password_reset_required=True,
                    password_changed_at=None
                )
                new_officer.set_password(password)
                db.session.add(new_officer)
                db.session.commit()
                log_action(g.user.id, 'CREATE_OFFICER', 'user', new_officer.id, details={'dept_id': dept_id, 'email': email})
                msg = f"Department Officer {full_name} created successfully."
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'reload_sections': True})
                flash(msg, "success")
        return redirect(url_for('admin.officers'))

    search = request.args.get('search', '').strip()
    query = User.query.filter_by(role='officer')
    if search:
        query = query.filter(
            (User.full_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.mobile_number.ilike(f'%{search}%'))
        )
    officers_list = query.order_by(User.created_at.desc()).all()
    departments = Department.query.filter_by(is_active=True).all()
    return render_template('admin/officers.html', officers=officers_list, departments=departments, search_query=search)

@admin_bp.route('/assignments', methods=['GET', 'POST'])
def assignments():
    if request.method == 'POST':
        action = request.form.get('action')
        is_ajax = _is_api_or_ajax()
        if action == 'assign_worker':
            complaint_id = request.form.get('complaint_id', type=int)
            worker_user_id = request.form.get('worker_user_id', type=int)
            instructions = request.form.get('instructions', '').strip()

            complaint = Complaint.query.get(complaint_id)
            if not complaint:
                if is_ajax:
                    return jsonify({'success': False, 'message': "Selected complaint could not be found."}), 404
                flash("Selected complaint could not be found.", "danger")
            elif not worker_user_id:
                if is_ajax:
                    return jsonify({'success': False, 'message': "Please select an available field technician to dispatch."}), 400
                flash("Please select an available field technician to dispatch.", "danger")
            else:
                try:
                    assign_complaint_to_worker(complaint, worker_user_id, g.user, instructions=instructions)
                    msg = f"Work order dispatched for {complaint.complaint_ref} successfully."
                    if is_ajax:
                        return jsonify({'success': True, 'message': msg, 'reload_sections': True})
                    flash(msg, "success")
                except Exception as e:
                    db.session.rollback()
                    if is_ajax:
                        return jsonify({'success': False, 'message': f"Dispatch failed: {str(e)}"}), 400
                    flash(f"Dispatch failed: {str(e)}", "danger")
            return redirect(url_for('admin.assignments'))

    status_filter = request.args.get('status')
    query = ComplaintAssignment.query.options(
        joinedload(ComplaintAssignment.complaint),
        joinedload(ComplaintAssignment.assigned_to),
        joinedload(ComplaintAssignment.assigned_by),
    )
    if status_filter:
        query = query.filter_by(status=status_filter)
    assignment_list = query.order_by(ComplaintAssignment.assigned_at.desc()).limit(100).all()

    assignable_complaints = Complaint.query.filter(
        Complaint.status.in_(['Submitted', 'Under Review', 'Assigned to Department', 'Officer Accepted', 'Accepted', 'In Progress', 'Assigned', 'Rework Required'])
    ).order_by(Complaint.created_at.desc()).all()

    workers = Worker.query.filter_by(is_available=True).options(joinedload(Worker.user), joinedload(Worker.department)).all()

    return render_template(
        'admin/assignments.html',
        assignments=assignment_list,
        current_status=status_filter,
        assignable_complaints=assignable_complaints,
        workers=workers
    )

@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    from app.models.audit import SystemSetting
    if request.method == 'POST':
        for key, val in request.form.items():
            if key.startswith('setting_'):
                k = key.replace('setting_', '')
                setting = SystemSetting.query.filter_by(setting_key=k).first()
                if setting:
                    setting.setting_value = val
                else:
                    db.session.add(SystemSetting(setting_key=k, setting_value=val))
        log_action(g.user.id, 'UPDATE_SETTINGS', 'system_settings', 'all', commit=False)
        db.session.commit()
        msg = "System configuration parameters updated."
        if _is_api_or_ajax():
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('admin.settings'))
    settings_list = SystemSetting.query.all()
    settings_dict = {s.setting_key: s.setting_value for s in settings_list}
    return render_template('admin/settings.html', settings=settings_list, settings_dict=settings_dict)

@admin_bp.route('/clean-demo-data', methods=['POST'])
def clean_demo_data():
    """Administrative action to purge all test complaints, assignments, notifications, and demo citizens from production."""
    try:
        from app.models.complaint import Complaint
        from app.models.workflow import ComplaintAssignment, ComplaintStatusHistory
        from app.models.attachment import ComplaintAttachment
        from app.models.notification import Notification
        from app.models.feedback import Feedback
        from app.models.audit import AuditLog
        from app.models.user import User

        # Delete all test complaints and their associated records
        ComplaintAssignment.query.delete()
        ComplaintStatusHistory.query.delete()
        ComplaintAttachment.query.delete()
        Notification.query.delete()
        Feedback.query.delete()
        AuditLog.query.delete()
        Complaint.query.delete()

        # Delete demo citizen test accounts
        demo_citizens = User.query.filter_by(role='citizen', email='citizen@civic.gov').all()
        for c in demo_citizens:
            db.session.delete(c)

        db.session.commit()
        flash("All test complaints, assignments, notifications, and demo citizen accounts have been removed from the live database.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error purging test data: {str(e)}", "danger")
    return redirect(url_for('admin.settings'))

@admin_bp.route('/notifications')
def notifications():
    from app.models.notification import Notification
    notifs = Notification.query.filter_by(user_id=g.user.id).order_by(Notification.created_at.desc()).all()
    return render_template('admin/notifications.html', notifications=notifs)
