from datetime import datetime
from flask import current_app
from app import db
from app.models.notification import Notification
from app.models.user import User
from app.utils.ttl_cache import app_cache


def _get_active_admin_ids():
    use_cache = bool(current_app and not current_app.config.get('TESTING'))
    if use_cache:
        cached = app_cache.get('notif:admin_ids')
        if cached is not None:
            return cached
    ids = [r[0] for r in db.session.query(User.id).filter_by(role='admin', is_active=True).all()]
    if use_cache:
        app_cache.set('notif:admin_ids', ids, ttl_seconds=120)
    return ids


def _get_dept_officer_ids(department_id):
    use_cache = bool(current_app and not current_app.config.get('TESTING'))
    key = f'notif:dept_officers:{department_id}'
    if use_cache:
        cached = app_cache.get(key)
        if cached is not None:
            return cached
    ids = [
        r[0]
        for r in db.session.query(User.id).filter_by(role='officer', department_id=department_id, is_active=True).all()
    ]
    if use_cache:
        app_cache.set(key, ids, ttl_seconds=120)
    return ids


def create_notification(user_id, title, message, link=None, notification_type='info', complaint_id=None, commit=True):
    """Create in-app notification permanently in the database for a given user."""
    try:
        notif = Notification(
            user_id=user_id,
            complaint_id=complaint_id,
            title=title,
            message=message,
            link=link,
            notification_type=notification_type
        )
        db.session.add(notif)
        if commit:
            db.session.commit()
        return notif
    except Exception:
        db.session.rollback()
        return None


def notify_admins(title, message, link=None, notification_type='admin_alert', complaint_id=None, commit=True):
    """Broadcast notification to all active administrators in a single batch insert."""
    admin_ids = _get_active_admin_ids()
    if not admin_ids:
        return []
    notifs = [
        Notification(
            user_id=aid,
            complaint_id=complaint_id,
            title=title,
            message=message,
            link=link,
            notification_type=notification_type,
        )
        for aid in admin_ids
    ]
    try:
        db.session.add_all(notifs)
        if commit:
            db.session.commit()
        return notifs
    except Exception:
        db.session.rollback()
        return []


def notify_department_officers(department_id, title, message, link=None, notification_type='dept_alert', complaint_id=None, commit=True):
    """Broadcast notification to all officers belonging to a department in a single batch insert."""
    officer_ids = _get_dept_officer_ids(department_id)
    if not officer_ids:
        return []
    notifs = [
        Notification(
            user_id=oid,
            complaint_id=complaint_id,
            title=title,
            message=message,
            link=link,
            notification_type=notification_type,
        )
        for oid in officer_ids
    ]
    try:
        db.session.add_all(notifs)
        if commit:
            db.session.commit()
        return notifs
    except Exception:
        db.session.rollback()
        return []


def mark_as_read(notification_id, user_id):
    """Mark a specific notification belonging to user_id as read."""
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif and not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.utcnow()
        db.session.commit()
        return True
    return False


def mark_all_as_read(user_id):
    """Mark all unread notifications for user_id as read."""
    Notification.query.filter_by(user_id=user_id, is_read=False).update({
        'is_read': True,
        'read_at': datetime.utcnow()
    })
    db.session.commit()
    return True
