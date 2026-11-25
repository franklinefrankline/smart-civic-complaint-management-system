from datetime import datetime
from app import db

class Worker(db.Model):
    __tablename__ = 'workers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=True, index=True)
    designation = db.Column(db.String(100), default='Field Technician')
    is_available = db.Column(db.Boolean, default=True)
    active_task_count = db.Column(db.Integer, default=0)
    completed_task_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.user.full_name if self.user else None,
            'email': self.user.email if self.user else None,
            'mobile': self.user.mobile_number if self.user else None,
            'employee_id': self.employee_id,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'designation': self.designation,
            'is_active': bool(self.user.is_active) if self.user else False,
            'is_available': self.is_available,
            'active_task_count': self.active_task_count,
            'completed_task_count': self.completed_task_count
        }

class ComplaintAssignment(db.Model):
    __tablename__ = 'complaint_assignments'
    __table_args__ = (
        db.Index('idx_assign_to_status', 'assigned_to_user_id', 'status'),
        db.Index('idx_assign_complaint', 'complaint_id'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False)
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    status = db.Column(
        db.Enum('Assigned', 'Accepted', 'In Progress', 'Completed', 'Returned'),
        default='Assigned'
    )
    instructions = db.Column(db.Text, nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_user_id], backref='tasks_assigned')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_user_id], backref='tasks_received')

class ComplaintStatusHistory(db.Model):
    __tablename__ = 'complaint_status_history'
    __table_args__ = (
        db.Index('idx_hist_complaint_created', 'complaint_id', 'created_at'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    previous_status = db.Column(db.String(60), nullable=True)
    new_status = db.Column(db.String(60), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    changed_by = db.relationship('User', foreign_keys=[changed_by_user_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'previous_status': self.previous_status,
            'new_status': self.new_status,
            'remarks': self.remarks,
            'changed_by_name': self.changed_by.full_name if self.changed_by else 'System Auto',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
