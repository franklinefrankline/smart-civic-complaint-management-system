from datetime import datetime
from app import db

class ComplaintCategory(db.Model):
    __tablename__ = 'complaint_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False)
    default_priority = db.Column(db.Enum('low', 'medium', 'high', 'urgent'), default='medium')
    sla_hours = db.Column(db.Integer, default=48)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    complaints = db.relationship('Complaint', backref='category', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'default_priority': self.default_priority,
            'sla_hours': self.sla_hours,
            'description': self.description,
            'is_active': self.is_active
        }
