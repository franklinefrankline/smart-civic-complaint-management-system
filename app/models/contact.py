from datetime import datetime
from app import db


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    __table_args__ = (
        db.Index('idx_contact_read_created', 'is_read', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self):
        from app.utils.helpers import utc_to_local
        local_dt = utc_to_local(self.created_at) if self.created_at else None
        return {
            'id': self.id,
            'name': self.name,
            'contact': self.contact,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': local_dt.strftime('%d %b %Y, %I:%M %p') if local_dt else ''
        }
