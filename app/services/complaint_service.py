from datetime import datetime, timedelta
from sqlalchemy import func, case
from app import db
from app.models.complaint import Complaint
from app.models.workflow import ComplaintStatusHistory, ComplaintAssignment, Worker
from app.models.attachment import ComplaintAttachment
from app.models.category import ComplaintCategory
from app.models.department import Department
from app.utils.helpers import generate_complaint_ref, haversine_distance, save_uploaded_file
from app.services.sla_service import calculate_sla_due_date
from app.services.notification_service import (
    create_notification,
    notify_admins,
    notify_department_officers
)
from app.services.audit_service import log_action

# Standardized workflow status groups used across dashboards, APIs, and queues
PENDING_STATUSES = ['Submitted', 'Under Review']
ASSIGNED_TO_WORKER_STATUSES = ['Assigned', 'Assigned to Worker']
ACTIVE_WORK_STATUSES = ['In Progress', 'Work Started', 'Rework Required']
COMPLETED_PENDING_VERIF_STATUSES = ['Work Completed', 'Verification Pending']
IN_PROGRESS_STATUSES = [
    'Assigned to Department',
    'Officer Accepted',
    'Accepted',
    'Assigned to Worker',
    'Assigned',
    'Work Started',
    'In Progress',
    'Work Completed',
    'Verification Pending',
    'Rework Required',
]

# Valid status transitions mapping by role
VALID_TRANSITIONS = {
    'admin': {
        'Submitted': ['Under Review', 'Assigned to Department', 'Accepted', 'Assigned', 'Rejected', 'Escalated'],
        'Under Review': ['Assigned to Department', 'Accepted', 'Assigned', 'Rejected', 'Escalated'],
        'Assigned to Department': ['Officer Accepted', 'Accepted', 'Assigned to Worker', 'Assigned', 'Rejected', 'Escalated'],
        'Officer Accepted': ['Assigned to Worker', 'Assigned', 'In Progress', 'Rejected', 'Escalated'],
        'Accepted': ['Assigned to Department', 'Assigned to Worker', 'Assigned', 'In Progress', 'Rejected', 'Escalated'],
        'Assigned to Worker': ['In Progress', 'Work Started', 'Assigned to Department', 'Escalated', 'Rejected'],
        'Assigned': ['In Progress', 'Work Started', 'Assigned to Department', 'Accepted', 'Escalated', 'Rejected'],
        'In Progress': ['Work Completed', 'Verification Pending', 'Escalated'],
        'Work Started': ['In Progress', 'Work Completed', 'Verification Pending', 'Escalated'],
        'Work Completed': ['Verification Pending', 'In Progress', 'Resolved', 'Rework Required'],
        'Verification Pending': ['Resolved', 'Rework Required', 'In Progress', 'Escalated'],
        'Rework Required': ['In Progress', 'Work Started', 'Assigned to Worker', 'Assigned', 'Verification Pending', 'Escalated'],
        'Resolved': ['Reopened'],
        'Rejected': ['Under Review', 'Submitted'],
        'Reopened': ['Under Review', 'Assigned to Department', 'Accepted', 'Assigned', 'Escalated'],
        'Escalated': ['Under Review', 'Assigned to Department', 'Accepted', 'Assigned', 'In Progress', 'Resolved']
    },
    'officer': {
        'Submitted': ['Under Review', 'Assigned to Department', 'Officer Accepted', 'Accepted', 'Rejected'],
        'Under Review': ['Officer Accepted', 'Accepted', 'Rejected', 'Assigned to Worker', 'Assigned'],
        'Assigned to Department': ['Officer Accepted', 'Accepted', 'Assigned to Worker', 'Assigned', 'Rejected'],
        'Officer Accepted': ['Assigned to Worker', 'Assigned', 'In Progress', 'Rejected'],
        'Accepted': ['Assigned to Worker', 'Assigned', 'In Progress', 'Rejected'],
        'Assigned to Worker': ['In Progress', 'Officer Accepted', 'Accepted', 'Rework Required'],
        'Assigned': ['In Progress', 'Accepted', 'Rework Required'],
        'In Progress': ['Work Completed', 'Verification Pending', 'Escalated'],
        'Work Started': ['In Progress', 'Work Completed', 'Verification Pending', 'Escalated'],
        'Work Completed': ['Verification Pending', 'In Progress', 'Resolved', 'Rework Required'],
        'Verification Pending': ['Resolved', 'Rework Required', 'In Progress'],
        'Rework Required': ['Assigned to Worker', 'Assigned', 'In Progress'],
        'Resolved': ['Reopened'],
        'Reopened': ['Under Review', 'Officer Accepted', 'Accepted', 'Assigned to Worker', 'Assigned'],
        'Escalated': ['Under Review', 'Officer Accepted', 'Accepted', 'Assigned to Worker', 'In Progress', 'Resolved']
    },
    'worker': {
        'Assigned to Worker': ['In Progress', 'Work Started'],
        'Assigned': ['In Progress', 'Work Started'],
        'Rework Required': ['In Progress', 'Work Started', 'Verification Pending', 'Work Completed'],
        'Work Started': ['In Progress', 'Verification Pending', 'Work Completed'],
        'In Progress': ['Work Completed', 'Verification Pending'],
        'Work Completed': ['Verification Pending']
    },
    'citizen': {
        'Resolved': ['Reopened']
    }
}

def find_potential_duplicates(category_id, ward_number=None, street_name=None, locality=None, latitude=None, longitude=None, radius_meters=500, days=30):
    """
    Search for similar active complaints in the same category within
    radius_meters or matching ward / locality in past days.
    """
    since = datetime.utcnow() - timedelta(days=days)
    candidates = Complaint.query.filter(
        Complaint.category_id == category_id,
        Complaint.created_at >= since,
        Complaint.status.notin_(['Resolved', 'Rejected'])
    ).all()
    
    matches = []
    for c in candidates:
        is_match = False
        dist_label = "Same Area"
        if latitude is not None and longitude is not None and c.latitude is not None and c.longitude is not None:
            dist = haversine_distance(latitude, longitude, float(c.latitude), float(c.longitude))
            if dist <= radius_meters:
                is_match = True
                dist_label = f"{round(dist)}m away"
        elif ward_number and c.ward_number and str(ward_number).strip().lower() == str(c.ward_number).strip().lower():
            is_match = True
            dist_label = f"Ward {c.ward_number}"
        elif locality and c.locality and str(locality).strip().lower() in str(c.locality).strip().lower():
            is_match = True
            dist_label = f"Locality: {c.locality}"
            
        if is_match:
            from app.utils.helpers import utc_to_local
            local_created = utc_to_local(c.created_at)
            matches.append({
                'id': c.id,
                'complaint_ref': c.complaint_ref,
                'title': c.title,
                'status': c.status,
                'created_at': local_created.strftime('%Y-%m-%d %H:%M'),
                'distance_meters': dist_label
            })
    return matches

def suggest_department_by_category(category_id):
    """Suggest appropriate department based on selected category"""
    cat = ComplaintCategory.query.get(category_id)
    if cat and cat.department:
        return cat.department
    return None

def create_complaint(citizen_id, title, description, category_id, priority,
                     address=None, city=None, ward_number=None,
                     state=None, district=None, street_name=None,
                     locality=None, landmark=None, pincode=None,
                     latitude=None, longitude=None, department_id=None,
                     attachments=None):
    """Create new civic complaint, compute SLA, notify staff and citizen"""
    cat = ComplaintCategory.query.get(category_id)
    if not cat:
        raise ValueError("Invalid complaint category.")
        
    # Auto-assign department if not specified
    if not department_id:
        department_id = cat.department_id
        
    sla_due = calculate_sla_due_date(priority)
    ref_id = generate_complaint_ref()
    
    clean_address = address.strip() if address else None
    if not clean_address and street_name:
        parts = [p for p in [street_name, locality, landmark] if p]
        clean_address = ", ".join(parts)
        
    complaint = Complaint(
        complaint_ref=ref_id,
        citizen_id=citizen_id,
        department_id=department_id,
        assigned_officer_id=None,
        assigned_worker_id=None,
        category_id=category_id,
        title=title.strip(),
        description=description.strip(),
        priority=priority,
        status='Submitted',
        address=clean_address,
        city=city.strip() if city else 'Chennai',
        ward_number=ward_number.strip() if ward_number else None,
        state=state.strip() if state else 'Tamil Nadu',
        district=district.strip() if district else 'Chennai',
        street_name=street_name.strip() if street_name else clean_address,
        locality=locality.strip() if locality else None,
        landmark=landmark.strip() if landmark else None,
        pincode=pincode.strip() if pincode else None,
        latitude=latitude,
        longitude=longitude,
        sla_due_date=sla_due
    )
    db.session.add(complaint)
    db.session.flush()  # get complaint.id
    
    # Record initial history
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_user_id=citizen_id,
        previous_status=None,
        new_status='Submitted',
        remarks='Complaint registered by citizen.'
    )
    db.session.add(history)
    
    # Save attachments if provided
    if attachments:
        for att in attachments:
            attachment_record = ComplaintAttachment(
                complaint_id=complaint.id,
                uploaded_by_user_id=citizen_id,
                attachment_type='initial',
                filename=att['filename'],
                original_name=att['original_name'],
                file_path=att['file_path'],
                file_size=att['file_size'],
                mime_type=att['mime_type'],
                file_data=att.get('file_data'),
                remarks='Initial proof uploaded during complaint creation'
            )
            db.session.add(attachment_record)

    # In-app notifications & audit log committed in a single database transaction
    create_notification(
        user_id=citizen_id,
        complaint_id=complaint.id,
        title="Complaint Submitted Successfully",
        message=f"Your complaint '{title}' was received. Reference ID: {complaint.complaint_ref}",
        link=f"/citizen/complaints/{complaint.id}",
        notification_type='complaint_created',
        commit=False,
    )

    notify_admins(
        title=f"New Complaint: {complaint.complaint_ref}",
        message=f"New complaint submitted in '{cat.name}': {title}",
        link=f"/admin/complaints/{complaint.id}",
        notification_type='new_complaint',
        complaint_id=complaint.id,
        commit=False,
    )

    log_action(
        user_id=citizen_id,
        action='CREATE_COMPLAINT',
        entity_type='complaint',
        entity_id=complaint.id,
        details={'ref': complaint.complaint_ref, 'category': cat.name, 'priority': priority},
        commit=False,
    )

    db.session.commit()
    return complaint

def transition_complaint_status(complaint, new_status, user, remarks=None, rejection_reason=None, notify_citizen=True, notify_admin_on_staff_action=True):
    """
    Enforces role-based state machine transitions, records status history,
    sends contextual notifications, and updates audit logs.
    """
    role = user.role
    allowed_from_current = VALID_TRANSITIONS.get(role, {}).get(complaint.status, [])
    
    # Allow admin to perform any reasonable status update
    if role != 'admin' and new_status not in allowed_from_current:
        raise PermissionError(f"Role '{role}' cannot transition status from '{complaint.status}' to '{new_status}'.")
        
    old_status = complaint.status
    complaint.status = new_status
    complaint.updated_at = datetime.utcnow()
    
    if new_status == 'Rejected':
        if not rejection_reason or not rejection_reason.strip():
            raise ValueError("A mandatory rejection reason is required.")
        complaint.rejection_reason = rejection_reason.strip()
        remarks = f"Rejected: {rejection_reason.strip()}"
        
    elif new_status == 'Resolved':
        complaint.resolved_at = datetime.utcnow()
        if not remarks:
            remarks = "Resolution approved and verified by department authority."
            
    elif new_status == 'Reopened':
        complaint.reopened_count += 1
        complaint.reopen_reason = remarks or "Citizen requested reopening."
        complaint.resolved_at = None
        
    elif new_status == 'Escalated':
        complaint.is_escalated = True
        complaint.escalated_at = datetime.utcnow()
        complaint.escalation_reason = remarks or "Manually escalated by supervisor."
        
    # Record history
    hist = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_user_id=user.id,
        previous_status=old_status,
        new_status=new_status,
        remarks=remarks
    )
    db.session.add(hist)

    # Notify Citizen of status update (skip only if caller dispatches a custom notification)
    status_display = new_status.replace('_', ' ')
    if notify_citizen:
        create_notification(
            user_id=complaint.citizen_id,
            complaint_id=complaint.id,
            title=f"Status Update: {complaint.complaint_ref}",
            message=f"Your complaint is now '{status_display}'. Remarks: {remarks or 'No remarks provided'}",
            link=f"/citizen/complaints/{complaint.id}",
            notification_type='status_changed',
            commit=False,
        )

    # Notify Admins when non-admin staff (Officer/Worker) transitions key workflow statuses
    if notify_admin_on_staff_action and role in ('officer', 'worker', 'citizen'):
        notify_admins(
            title=f"{status_display}: {complaint.complaint_ref}",
            message=f"{user.full_name} ({role.title()}) updated {complaint.complaint_ref} to '{status_display}'. {remarks or ''}".strip(),
            link=f"/admin/complaints/{complaint.id}",
            notification_type='status_changed',
            complaint_id=complaint.id,
            commit=False,
        )

    log_action(
        user_id=user.id,
        action='UPDATE_STATUS',
        entity_type='complaint',
        entity_id=complaint.id,
        details={'from': old_status, 'to': new_status, 'remarks': remarks},
        commit=False,
    )

    db.session.commit()
    return complaint

def assign_department_officer(complaint, department_id, officer_id, assigned_by_admin, admin_remarks=None):
    """
    LEVEL 2: Administrator assigns Department & active Department Officer
    """
    from app.models.user import User
    officer = User.query.filter_by(id=officer_id, role='officer', is_active=True).first()
    if not officer:
        raise ValueError("Selected officer is not an active department officer.")
    if officer.department_id != department_id:
        raise ValueError("The selected officer does not belong to the selected department.")
    
    dept = Department.query.get(department_id)
    if not dept:
        raise ValueError("Invalid department.")
        
    old_status = complaint.status
    complaint.department_id = department_id
    complaint.assigned_officer_id = officer.id
    complaint.officer_assigned_at = datetime.utcnow()
    complaint.admin_remarks = admin_remarks
    complaint.status = 'Assigned to Department'
    complaint.updated_at = datetime.utcnow()
    
    # Create Assignment record
    assignment = ComplaintAssignment(
        complaint_id=complaint.id,
        assigned_by_user_id=assigned_by_admin.id,
        assigned_to_user_id=officer.id,
        status='Assigned',
        instructions=admin_remarks,
        assigned_at=datetime.utcnow()
    )
    db.session.add(assignment)
    
    # Create status history
    hist = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_user_id=assigned_by_admin.id,
        previous_status=old_status,
        new_status='Assigned to Department',
        remarks=f"Administrator assigned to {dept.name} (Officer: {officer.full_name}). Remarks: {admin_remarks or 'None'}"
    )
    db.session.add(hist)

    # Notify Department Officer & Citizen + Audit in one atomic commit
    create_notification(
        user_id=officer.id,
        complaint_id=complaint.id,
        title=f"New Complaint Assigned: {complaint.complaint_ref}",
        message=f"Administrator assigned {complaint.complaint_ref} ('{complaint.title}') to your department queue. Remarks: {admin_remarks or 'None'}",
        link=f"/officer/complaints/{complaint.id}",
        notification_type='assignment',
        commit=False,
    )

    create_notification(
        user_id=complaint.citizen_id,
        complaint_id=complaint.id,
        title="Department Assigned",
        message=f"Your complaint {complaint.complaint_ref} has been reviewed by the Administrator and assigned to the {dept.name} department.",
        link=f"/citizen/complaints/{complaint.id}",
        notification_type='status_changed',
        commit=False,
    )

    log_action(
        user_id=assigned_by_admin.id,
        action='ASSIGN_DEPARTMENT_OFFICER',
        entity_type='complaint',
        entity_id=complaint.id,
        details={'dept_id': department_id, 'officer_id': officer_id, 'remarks': admin_remarks},
        commit=False,
    )
    db.session.commit()
    return assignment

def assign_complaint_to_worker(complaint, worker_user_id, assigned_by_user, instructions=None):
    """
    LEVEL 3: Department Officer assigns Field Worker belonging to the SAME department
    """
    worker = Worker.query.filter_by(user_id=worker_user_id).first()
    if not worker or not worker.user or not worker.user.is_active:
        raise ValueError("Selected user is not an active field worker.")
        
    # An officer cannot assign workers belonging to another department
    if assigned_by_user.role == 'officer':
        if worker.department_id != assigned_by_user.department_id:
            raise PermissionError("An officer cannot assign workers belonging to another department.")
            
    if complaint.department_id and worker.department_id != complaint.department_id:
        raise ValueError("Worker must belong to the complaint's assigned department.")
        
    assignment = ComplaintAssignment(
        complaint_id=complaint.id,
        assigned_by_user_id=assigned_by_user.id,
        assigned_to_user_id=worker_user_id,
        status='Assigned',
        instructions=instructions,
        assigned_at=datetime.utcnow()
    )
    db.session.add(assignment)
    
    worker.active_task_count = (worker.active_task_count or 0) + 1
    
    old_status = complaint.status
    complaint.assigned_worker_id = worker_user_id
    complaint.worker_assigned_at = datetime.utcnow()
    complaint.officer_remarks = instructions
    complaint.status = 'Assigned to Worker'
    complaint.updated_at = datetime.utcnow()
    
    hist = ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_user_id=assigned_by_user.id,
        previous_status=old_status,
        new_status='Assigned to Worker',
        remarks=f"Assigned to Field Technician {worker.user.full_name}. Instructions: {instructions or 'None'}"
    )
    db.session.add(hist)

    dept_name = complaint.department.name if complaint.department else (worker.department.name if worker.department else 'Civic Department')

    # Notify Worker, Citizen, Admins + Audit in one atomic commit
    create_notification(
        user_id=worker_user_id,
        complaint_id=complaint.id,
        title=f"New Field Task Assigned: {complaint.complaint_ref}",
        message=f"Complaint {complaint.complaint_ref} ('{complaint.title}') | Dept: {dept_name} | Location: {complaint.full_address} | Instructions: {instructions or 'Standard inspection & repair'}",
        link=f"/worker/tasks/{complaint.id}",
        notification_type='assignment',
        commit=False,
    )

    create_notification(
        user_id=complaint.citizen_id,
        complaint_id=complaint.id,
        title="Field Technician Assigned",
        message=f"A field technician ({worker.user.full_name}) has been dispatched to address your complaint {complaint.complaint_ref}.",
        link=f"/citizen/complaints/{complaint.id}",
        notification_type='status_changed',
        commit=False,
    )

    if assigned_by_user.role != 'admin':
        notify_admins(
            title=f"Worker Assigned: {complaint.complaint_ref}",
            message=f"Officer {assigned_by_user.full_name} assigned {complaint.complaint_ref} to technician {worker.user.full_name}.",
            link=f"/admin/complaints/{complaint.id}",
            notification_type='assignment',
            complaint_id=complaint.id,
            commit=False,
        )

    log_action(
        user_id=assigned_by_user.id,
        action='ASSIGN_WORKER',
        entity_type='complaint',
        entity_id=complaint.id,
        details={'worker_id': worker_user_id, 'instructions': instructions},
        commit=False,
    )

    db.session.commit()
    return assignment

def officer_verify_work(complaint, officer_user, action, remarks, rework_reason=None):
    """
    LEVEL 5: Officer Verification (APPROVE -> Resolved, RETURN FOR CORRECTION -> Rework Required)
    """
    if officer_user.role != 'officer' and officer_user.role != 'admin':
        raise PermissionError("Only department officers can verify and approve work.")
        
    old_status = complaint.status
    
    if action == 'approve':
        complaint.status = 'Resolved'
        complaint.resolved_at = datetime.utcnow()
        complaint.verification_remarks = remarks or "Verified and approved by department officer."
        complaint.verified_at = datetime.utcnow()
        complaint.updated_at = datetime.utcnow()
        
        # Decrement worker's active tasks and increment completed
        if complaint.assigned_worker_id:
            worker = Worker.query.filter_by(user_id=complaint.assigned_worker_id).first()
            if worker:
                if worker.active_task_count and worker.active_task_count > 0:
                    worker.active_task_count -= 1
                worker.completed_task_count = (worker.completed_task_count or 0) + 1
                
        hist = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_user_id=officer_user.id,
            previous_status=old_status,
            new_status='Resolved',
            remarks=f"Verified and approved by Officer {officer_user.full_name}. Remarks: {remarks or 'Resolution approved'}"
        )
        db.session.add(hist)

        create_notification(
            user_id=complaint.citizen_id,
            complaint_id=complaint.id,
            title=f"Complaint Resolved: {complaint.complaint_ref}",
            message=f"Your complaint '{complaint.title}' has been successfully resolved and verified by Officer {officer_user.full_name}. Please rate our service.",
            link=f"/citizen/complaints/{complaint.id}",
            notification_type='status_changed',
            commit=False,
        )

        notify_admins(
            title=f"Complaint Resolved: {complaint.complaint_ref}",
            message=f"Officer {officer_user.full_name} verified and resolved {complaint.complaint_ref} ({complaint.title}).",
            link=f"/admin/complaints/{complaint.id}",
            notification_type='status_changed',
            complaint_id=complaint.id,
            commit=False,
        )

        log_action(
            user_id=officer_user.id,
            action='VERIFY_RESOLVE',
            entity_type='complaint',
            entity_id=complaint.id,
            details={'remarks': remarks},
            commit=False,
        )
        db.session.commit()

    elif action == 'rework':
        if not rework_reason or not rework_reason.strip():
            raise ValueError("A reason is mandatory when returning work for correction.")

        complaint.status = 'Rework Required'
        complaint.verification_remarks = rework_reason.strip()
        complaint.updated_at = datetime.utcnow()

        latest_assign = complaint.assignments.order_by(ComplaintAssignment.id.desc()).first()
        if latest_assign:
            latest_assign.status = 'Returned'

        hist = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_user_id=officer_user.id,
            previous_status=old_status,
            new_status='Rework Required',
            remarks=f"Returned for rework by Officer {officer_user.full_name}. Reason: {rework_reason.strip()}"
        )
        db.session.add(hist)

        if complaint.assigned_worker_id:
            create_notification(
                user_id=complaint.assigned_worker_id,
                complaint_id=complaint.id,
                title=f"Rework Required: {complaint.complaint_ref}",
                message=f"Officer {officer_user.full_name} returned task '{complaint.title}' for rework. Reason: {rework_reason.strip()}",
                link=f"/worker/tasks/{complaint.id}",
                notification_type='rework_required',
                commit=False,
            )

        create_notification(
            user_id=complaint.citizen_id,
            complaint_id=complaint.id,
            title="Work In Progress Revision",
            message=f"Department officer inspected your complaint {complaint.complaint_ref} and requested additional adjustments from the field team.",
            link=f"/citizen/complaints/{complaint.id}",
            notification_type='status_changed',
            commit=False,
        )

        notify_admins(
            title=f"Rework Requested: {complaint.complaint_ref}",
            message=f"Officer {officer_user.full_name} requested rework on {complaint.complaint_ref}. Reason: {rework_reason.strip()}",
            link=f"/admin/complaints/{complaint.id}",
            notification_type='rework_required',
            complaint_id=complaint.id,
            commit=False,
        )

        log_action(
            user_id=officer_user.id,
            action='RETURN_REWORK',
            entity_type='complaint',
            entity_id=complaint.id,
            details={'reason': rework_reason.strip()},
            commit=False,
        )
        db.session.commit()
    else:
        raise ValueError(f"Unknown verification action: {action}")
        
    return complaint

def get_complaint_9_stage_timeline(complaint):
    """
    LEVEL 6: Build structured 9-stage civic redressal timeline
    """
    if not complaint:
        return []

    history = complaint.status_history.order_by(ComplaintStatusHistory.created_at.asc()).all()
    status_map = {h.new_status: h for h in history}

    # 1. Complaint Submitted
    sub_time = complaint.created_at
    sub_remarks = "Grievance registered and logged into municipal database."

    # 2. Reviewed by Administrator
    reviewed = False
    rev_time = None
    rev_remarks = "Awaiting municipal administrator review."
    if complaint.admin_remarks or complaint.officer_assigned_at or 'Assigned to Department' in status_map or 'Under Review' in status_map:
        reviewed = True
        rev_time = complaint.officer_assigned_at or (status_map.get('Assigned to Department') or status_map.get('Under Review') or complaint).created_at
        rev_remarks = complaint.admin_remarks or "Complaint evaluated and assigned by Administrator."

    # 3. Department Assigned
    dept_assigned = False
    dept_time = None
    dept_remarks = "Pending department assignment."
    if complaint.department_id and (complaint.assigned_officer_id or 'Assigned to Department' in status_map or complaint.status not in ['Submitted', 'Under Review']):
        dept_assigned = True
        dept_time = complaint.officer_assigned_at or (status_map.get('Assigned to Department') or complaint).created_at
        dept_name = complaint.department.name if complaint.department else "Civic Department"
        officer_name = complaint.assigned_officer.full_name if complaint.assigned_officer else "Department Officer"
        dept_remarks = f"Assigned to {dept_name}. Assigned Officer: {officer_name}."

    # 4. Officer Accepted
    officer_accepted = False
    acc_time = None
    acc_remarks = "Awaiting departmental officer acceptance."
    if 'Officer Accepted' in status_map or 'Accepted' in status_map or complaint.assigned_worker_id or complaint.status in ['Officer Accepted', 'Accepted', 'Assigned to Worker', 'Assigned', 'In Progress', 'Work Started', 'Work Completed', 'Verification Pending', 'Resolved', 'Rework Required']:
        officer_accepted = True
        h_acc = status_map.get('Officer Accepted') or status_map.get('Accepted')
        acc_time = h_acc.created_at if h_acc else (complaint.worker_assigned_at or dept_time)
        acc_remarks = (h_acc.remarks if h_acc and h_acc.remarks else None) or "Accepted into active municipal schedule by Department Officer."

    # 5. Worker Assigned
    worker_assigned = False
    work_assign_time = None
    work_assign_remarks = "Pending technician assignment."
    if complaint.assigned_worker_id or 'Assigned to Worker' in status_map or 'Assigned' in status_map or complaint.status in ['Assigned to Worker', 'Assigned', 'In Progress', 'Work Started', 'Work Completed', 'Verification Pending', 'Resolved', 'Rework Required']:
        worker_assigned = True
        h_w = status_map.get('Assigned to Worker') or status_map.get('Assigned')
        work_assign_time = complaint.worker_assigned_at or (h_w.created_at if h_w else None)
        worker_name = complaint.assigned_worker.full_name if complaint.assigned_worker else "Field Technician"
        work_assign_remarks = f"Assigned to {worker_name}." + (f" Instructions: {complaint.officer_remarks}" if complaint.officer_remarks else "")

    # 6. Work Started
    work_started = False
    started_time = None
    started_remarks = "Technician has not yet arrived on site."
    if 'In Progress' in status_map or 'Work Started' in status_map or complaint.status in ['In Progress', 'Work Completed', 'Verification Pending', 'Resolved', 'Rework Required']:
        work_started = True
        h_start = status_map.get('In Progress') or status_map.get('Work Started')
        started_time = h_start.created_at if h_start else None
        started_remarks = (h_start.remarks if h_start and h_start.remarks else None) or "Field technician started site diagnostics and repairs."

    # 7. Work Completed
    work_completed = False
    completed_time = None
    completed_remarks = "Repairs in progress."
    if 'Verification Pending' in status_map or 'Work Completed' in status_map or complaint.status in ['Verification Pending', 'Work Completed', 'Resolved']:
        work_completed = True
        h_comp = status_map.get('Verification Pending') or status_map.get('Work Completed')
        completed_time = h_comp.created_at if h_comp else None
        completed_remarks = (h_comp.remarks if h_comp and h_comp.remarks else None) or "Field execution finished; photographic evidence submitted."

    # 8. Officer Verification
    verified = False
    verified_time = None
    verified_remarks = "Awaiting final inspection by department officer."
    if complaint.verified_at or complaint.status == 'Resolved' or complaint.status == 'Rework Required' or 'Resolved' in status_map or 'Rework Required' in status_map:
        verified = True
        verified_time = complaint.verified_at or (complaint.resolved_at if complaint.status == 'Resolved' else None)
        if complaint.status == 'Rework Required':
            verified_remarks = f"Officer requested rework: {complaint.rejection_reason or 'Additional correction required.'}"
        else:
            verified_remarks = complaint.verification_remarks or "Work verified and approved by Department Officer."

    # 9. Resolved
    is_resolved = complaint.status == 'Resolved'
    resolved_time = complaint.resolved_at if is_resolved else None
    resolved_remarks = "Grievance resolved and closed. Citizen feedback requested." if is_resolved else "Resolution pending final verification."

    stages = [
        {'step': 1, 'title': 'Complaint Submitted', 'is_completed': True, 'timestamp': sub_time, 'remarks': sub_remarks, 'icon': 'file-text'},
        {'step': 2, 'title': 'Reviewed by Administrator', 'is_completed': reviewed, 'timestamp': rev_time, 'remarks': rev_remarks, 'icon': 'shield-check'},
        {'step': 3, 'title': 'Department Assigned', 'is_completed': dept_assigned, 'timestamp': dept_time, 'remarks': dept_remarks, 'icon': 'building-2'},
        {'step': 4, 'title': 'Officer Accepted', 'is_completed': officer_accepted, 'timestamp': acc_time, 'remarks': acc_remarks, 'icon': 'user-check'},
        {'step': 5, 'title': 'Worker Assigned', 'is_completed': worker_assigned, 'timestamp': work_assign_time, 'remarks': work_assign_remarks, 'icon': 'wrench'},
        {'step': 6, 'title': 'Work Started', 'is_completed': work_started, 'timestamp': started_time, 'remarks': started_remarks, 'icon': 'play-circle'},
        {'step': 7, 'title': 'Work Completed', 'is_completed': work_completed, 'timestamp': completed_time, 'remarks': completed_remarks, 'icon': 'check-circle'},
        {'step': 8, 'title': 'Officer Verification', 'is_completed': verified, 'timestamp': verified_time, 'remarks': verified_remarks, 'icon': 'clipboard-check'},
        {'step': 9, 'title': 'Resolved', 'is_completed': is_resolved, 'timestamp': resolved_time, 'remarks': resolved_remarks, 'icon': 'award'}
    ]
    return stages


def get_complaint_aggregate_counts(*filters):
    """
    Compute complaint dashboard KPIs in a SINGLE SQL aggregate query instead of
    7-8 sequential COUNT(*) round-trips.
    """
    row = (
        db.session.query(
            func.count(Complaint.id).label('total'),
            func.sum(case((Complaint.status == 'Submitted', 1), else_=0)).label('submitted'),
            func.sum(case((Complaint.status.in_(['Submitted', 'Assigned to Department']), 1), else_=0)).label('officer_new'),
            func.sum(case((Complaint.status.in_(PENDING_STATUSES), 1), else_=0)).label('pending'),
            func.sum(case((Complaint.status.in_(['Submitted', 'Under Review', 'Assigned to Department']), 1), else_=0)).label('officer_pending'),
            func.sum(case((Complaint.status.in_(IN_PROGRESS_STATUSES), 1), else_=0)).label('in_progress'),
            func.sum(case((Complaint.status.in_(ASSIGNED_TO_WORKER_STATUSES), 1), else_=0)).label('assigned'),
            func.sum(case((Complaint.status.in_(ACTIVE_WORK_STATUSES), 1), else_=0)).label('active_work'),
            func.sum(case((Complaint.status.in_(COMPLETED_PENDING_VERIF_STATUSES), 1), else_=0)).label('completed_pending'),
            func.sum(case((Complaint.status.in_(COMPLETED_PENDING_VERIF_STATUSES + ['Resolved']), 1), else_=0)).label('worker_completed'),
            func.sum(case((Complaint.status == 'Resolved', 1), else_=0)).label('resolved'),
            func.sum(case((Complaint.status == 'Rejected', 1), else_=0)).label('rejected'),
            func.sum(case(((Complaint.is_escalated == True) | (Complaint.status == 'Escalated'), 1), else_=0)).label('overdue'),
        )
        .filter(*filters)
        .one()
    )
    return {
        'total': int(row.total or 0),
        'submitted': int(row.submitted or 0),
        'officer_new': int(row.officer_new or 0),
        'pending': int(row.pending or 0),
        'officer_pending': int(row.officer_pending or 0),
        'in_progress': int(row.in_progress or 0),
        'assigned': int(row.assigned or 0),
        'active_work': int(row.active_work or 0),
        'completed_pending': int(row.completed_pending or 0),
        'worker_completed': int(row.worker_completed or 0),
        'resolved': int(row.resolved or 0),
        'rejected': int(row.rejected or 0),
        'overdue': int(row.overdue or 0),
    }


def build_admin_analytics_payload():
    """
    Build real-time municipal analytics across departments, categories, and workflow statuses
    using lightweight column projections and a single outer-join query (zero N+1 category loads).
    """
    departments = Department.query.order_by(Department.id.asc()).all()
    categories = ComplaintCategory.query.order_by(ComplaintCategory.id.asc()).all()
    now = datetime.utcnow()

    complaint_rows = (
        db.session.query(
            Complaint.department_id,
            ComplaintCategory.department_id.label('cat_dept_id'),
            Complaint.category_id,
            Complaint.status,
            Complaint.is_escalated,
            Complaint.sla_due_date,
        )
        .outerjoin(ComplaintCategory, Complaint.category_id == ComplaintCategory.id)
        .all()
    )

    dept_buckets = {
        d.id: {
            'id': d.id,
            'name': d.name,
            'code': d.code,
            'is_active': bool(d.is_active),
            'total': 0,
            'pending': 0,
            'in_progress': 0,
            'resolved': 0,
            'overdue': 0,
        }
        for d in departments
    }
    unassigned_bucket = {
        'id': None,
        'name': 'Unassigned / Triage',
        'code': 'TRIAGE',
        'is_active': True,
        'total': 0,
        'pending': 0,
        'in_progress': 0,
        'resolved': 0,
        'overdue': 0,
    }
    cat_counts = {c.id: 0 for c in categories}
    uncategorized_count = 0

    total = len(complaint_rows)
    pending_count = 0
    in_progress_count = 0
    resolved_count = 0
    rejected_count = 0
    escalated_count = 0
    overdue_count = 0

    for dept_id, cat_dept_id, cat_id, status, is_escalated, sla_due_date in complaint_rows:
        target_dept_id = dept_id or cat_dept_id
        bucket = dept_buckets.get(target_dept_id) if target_dept_id else unassigned_bucket
        if bucket is None:
            bucket = unassigned_bucket

        bucket['total'] += 1
        if status in PENDING_STATUSES:
            pending_count += 1
            bucket['pending'] += 1
        elif status in IN_PROGRESS_STATUSES:
            in_progress_count += 1
            bucket['in_progress'] += 1
        elif status == 'Resolved':
            resolved_count += 1
            bucket['resolved'] += 1
        elif status == 'Rejected':
            rejected_count += 1
        elif status == 'Escalated':
            escalated_count += 1

        is_row_overdue = (
            (status not in ('Resolved', 'Rejected') and sla_due_date is not None and now > sla_due_date)
            or bool(is_escalated)
            or status == 'Escalated'
        )
        if is_row_overdue:
            overdue_count += 1
            bucket['overdue'] += 1

        if cat_id in cat_counts:
            cat_counts[cat_id] += 1
        else:
            uncategorized_count += 1

    dept_rows = []
    for d in departments:
        b = dept_buckets[d.id]
        b['resolution_rate'] = round((b['resolved'] / b['total']) * 100, 1) if b['total'] else 0.0
        dept_rows.append(b)
    if unassigned_bucket['total'] > 0:
        unassigned_bucket['resolution_rate'] = round((unassigned_bucket['resolved'] / unassigned_bucket['total']) * 100, 1)
        dept_rows.append(unassigned_bucket)

    cat_rows = [
        {'id': c.id, 'name': c.name, 'total': cat_counts[c.id]}
        for c in categories
    ]
    if uncategorized_count > 0:
        cat_rows.append({'id': 0, 'name': 'Other / General', 'total': uncategorized_count})
    cat_rows.sort(key=lambda item: (-item['total'], item['id']))
    active_cats = [item for item in cat_rows if item['total'] > 0]

    resolution_rate = round((resolved_count / total) * 100, 1) if total else 0.0

    return {
        'summary': {
            'total': total,
            'pending': pending_count,
            'in_progress': in_progress_count,
            'resolved': resolved_count,
            'rejected': rejected_count,
            'escalated': escalated_count,
            'overdue': overdue_count,
            'resolution_rate': resolution_rate,
        },
        'dept_labels': [r['name'] for r in dept_rows],
        'dept_totals': [r['total'] for r in dept_rows],
        'dept_resolved': [r['resolved'] for r in dept_rows],
        'dept_rows': dept_rows,
        'cat_labels': [item['name'] for item in active_cats],
        'cat_totals': [item['total'] for item in active_cats],
        'all_cat_labels': [item['name'] for item in cat_rows],
        'all_cat_totals': [item['total'] for item in cat_rows],
        'status_labels': ['Pending / Submitted', 'In Progress', 'Resolved', 'Escalated', 'Rejected'],
        'status_totals': [pending_count, in_progress_count, resolved_count, escalated_count, rejected_count],
    }
