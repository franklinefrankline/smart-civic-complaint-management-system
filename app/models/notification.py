from datetime import datetime
from app import db


class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = (
        db.Index('idx_notif_user_read', 'user_id', 'is_read'),
        db.Index('idx_notif_complaint', 'complaint_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    notification_type = db.Column(db.String(50), default='info')
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    complaint = db.relationship('Complaint', foreign_keys=[complaint_id])

    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'title': self.title,
            'message': self.message,
            'link': self.link,
            'notification_type': self.notification_type,
            'is_read': bool(self.is_read),
            'read_at': self.read_at.strftime('%Y-%m-%d %H:%M:%S') if self.read_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'time_ago': self.time_ago
        }

    @property
    def time_ago(self):
        if not self.created_at:
            return "Just now"
        delta = datetime.utcnow() - self.created_at
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = delta.seconds // 60
        if minutes > 0:
            return f"{minutes}m ago"
        return "Just now"
