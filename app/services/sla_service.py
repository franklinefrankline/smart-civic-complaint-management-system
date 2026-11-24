from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models.complaint import Complaint
from app.models.workflow import ComplaintStatusHistory
from app.services.notification_service import notify_admins, notify_department_officers, create_notification
from app.services.audit_service import log_action

def calculate_sla_due_date(priority, start_time=None):
    """Compute SLA due date based on complaint priority"""
    if start_time is None:
        start_time = datetime.utcnow()
    sla_map = current_app.config.get('SLA_HOURS', {
        'urgent': 24,
        'high': 48,
        'medium': 96,
        'low': 168
    })
    hours = sla_map.get(priority.lower(), 96)
    return start_time + timedelta(hours=hours)

def check_and_escalate_overdue_complaints():
    """
    Background or periodic sweep checking all active complaints
    that have breached their SLA resolution target.
    """
    now = datetime.utcnow()
    overdue_complaints = Complaint.query.filter(
        Complaint.status.notin_(['Resolved', 'Rejected']),
        Complaint.sla_due_date.isnot(None),
        Complaint.sla_due_date < now,
        Complaint.is_escalated == False
    ).all()
    
    escalated_count = 0
    for complaint in overdue_complaints:
        complaint.is_escalated = True
        complaint.escalated_at = now
        complaint.escalation_reason = f"System SLA breached: Resolution exceeded deadline of {complaint.sla_due_date.strftime('%Y-%m-%d %H:%M')}."
        
        # Log to history
        hist = ComplaintStatusHistory(
            complaint_id=complaint.id,
            changed_by_user_id=None,
            previous_status=complaint.status,
            new_status='Escalated',
            remarks=complaint.escalation_reason
        )
        db.session.add(hist)
        
        # Notify admins and department officers
        notify_admins(
            title=f"SLA Breached: {complaint.complaint_ref}",
            message=f"Complaint '{complaint.title}' ({complaint.priority.upper()}) is overdue and escalated.",
            link=f"/admin/complaints/{complaint.id}",
            notification_type='escalation'
        )
        if complaint.department_id:
            notify_department_officers(
                department_id=complaint.department_id,
                title=f"URGENT: Complaint Escalated {complaint.complaint_ref}",
                message=f"Complaint '{complaint.title}' exceeded SLA target and has been escalated.",
                link=f"/officer/complaints/{complaint.id}",
                notification_type='escalation'
            )
            
        log_action(
            user_id=None,
            action='AUTO_ESCALATE_OVERDUE',
            entity_type='complaint',
            entity_id=complaint.id,
            details={'ref': complaint.complaint_ref, 'sla_due_date': str(complaint.sla_due_date)}
        )
        escalated_count += 1
        
    if escalated_count > 0:
        db.session.commit()
        
    return escalated_count
