import json
from datetime import datetime
from flask import request
from app import db
from app.models.audit import AuditLog

def log_action(user_id, action, entity_type, entity_id=None, details=None, ip_address=None, user_agent=None):
    """
    Log an administrative, operational or user action to the audit_logs table
    """
    try:
        if ip_address is None and request:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if user_agent is None and request:
            user_agent = request.user_agent.string if request.user_agent else None
            
        if isinstance(details, dict):
            details_str = json.dumps(details, default=str)
        else:
            details_str = str(details) if details else None
            
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=ip_address[:50] if ip_address else None,
            user_agent=user_agent[:255] if user_agent else None,
            details=details_str
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry
    except Exception as e:
        db.session.rollback()
        # Non-fatal log failure to prevent breaking caller
        return None
