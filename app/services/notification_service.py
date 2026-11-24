from datetime import datetime
from app import db
from app.models.notification import Notification
from app.models.user import User

def create_notification(user_id, title, message, link=None, notification_type='info'):
    """Create in-app notification for a given user"""
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            link=link,
            notification_type=notification_type
        )
        db.session.add(notif)
        db.session.commit()
        return notif
    except Exception as e:
        db.session.rollback()
        return None

def notify_admins(title, message, link=None, notification_type='admin_alert'):
    """Broadcast notification to all active administrators"""
    admins = User.query.filter_by(role='admin', is_active=True).all()
    for admin in admins:
        create_notification(admin.id, title, message, link, notification_type)

def notify_department_officers(department_id, title, message, link=None, notification_type='dept_alert'):
    """Broadcast notification to all officers belonging to a department"""
    officers = User.query.filter_by(role='officer', department_id=department_id, is_active=True).all()
    for officer in officers:
        create_notification(officer.id, title, message, link, notification_type)

def mark_as_read(notification_id, user_id):
    """Mark a specific notification as read"""
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif and not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.utcnow()
        db.session.commit()
        return True
    return False

def mark_all_as_read(user_id):
    """Mark all unread notifications for a user as read"""
    Notification.query.filter_by(user_id=user_id, is_read=False).update({
        'is_read': True,
        'read_at': datetime.utcnow()
    })
    db.session.commit()
    return True
