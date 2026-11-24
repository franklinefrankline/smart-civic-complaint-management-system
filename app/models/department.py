from datetime import datetime
from app import db

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    contact_email = db.Column(db.String(150), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    categories = db.relationship('ComplaintCategory', backref='department', lazy='dynamic')
    complaints = db.relationship('Complaint', foreign_keys='Complaint.department_id', backref='department', lazy='dynamic')
    workers = db.relationship('Worker', backref='department', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'is_active': self.is_active,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'categories_count': self.categories.count(),
            'complaints_count': self.complaints.count()
        }
