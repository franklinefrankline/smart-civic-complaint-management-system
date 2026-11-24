from datetime import datetime
from app import db

class Feedback(db.Model):
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False, unique=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment = db.Column(db.Text, nullable=True)
    response_speed_rating = db.Column(db.Integer, nullable=True)
    work_quality_rating = db.Column(db.Integer, nullable=True)
    is_satisfied = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    citizen = db.relationship('User', foreign_keys=[citizen_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'rating': self.rating,
            'comment': self.comment,
            'response_speed_rating': self.response_speed_rating,
            'work_quality_rating': self.work_quality_rating,
            'is_satisfied': self.is_satisfied,
            'citizen_name': self.citizen.full_name if self.citizen else 'Citizen',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
