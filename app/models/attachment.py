from datetime import datetime
from sqlalchemy.dialects.mysql import LONGBLOB
from app import db


class ComplaintAttachment(db.Model):
    __tablename__ = 'complaint_attachments'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    attachment_type = db.Column(
        db.Enum('initial', 'before_work', 'after_work', 'verification'),
        nullable=False,
        default='initial'
    )
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    file_data = db.deferred(db.Column(db.LargeBinary().with_variant(LONGBLOB, 'mysql'), nullable=True))
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'attachment_type': self.attachment_type,
            'filename': self.filename,
            'original_name': self.original_name,
            'file_path': self.file_path,
            'remarks': self.remarks,
            'uploaded_by': self.uploaded_by.full_name if self.uploaded_by else 'User',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
