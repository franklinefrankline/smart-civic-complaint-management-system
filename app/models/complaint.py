from datetime import datetime
from app import db

class Complaint(db.Model):
    __tablename__ = 'complaints'
    __table_args__ = (
        db.Index('idx_comp_status', 'status'),
        db.Index('idx_comp_citizen_created', 'citizen_id', 'created_at'),
        db.Index('idx_comp_dept_status_created', 'department_id', 'status', 'created_at'),
        db.Index('idx_comp_officer_created', 'assigned_officer_id', 'created_at'),
        db.Index('idx_comp_worker', 'assigned_worker_id'),
        db.Index('idx_comp_category', 'category_id'),
        db.Index('idx_comp_priority', 'priority'),
        db.Index('idx_comp_created', 'created_at'),
        db.Index('idx_comp_updated', 'updated_at'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_ref = db.Column(db.String(50), unique=True, nullable=False, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('complaint_categories.id', ondelete='RESTRICT'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Enum('low', 'medium', 'high', 'urgent'), nullable=False, default='medium')
    status = db.Column(db.String(60), nullable=False, default='Submitted')
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    assigned_worker_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    officer_assigned_at = db.Column(db.DateTime, nullable=True)
    worker_assigned_at = db.Column(db.DateTime, nullable=True)
    admin_remarks = db.Column(db.Text, nullable=True)
    officer_remarks = db.Column(db.Text, nullable=True)
    verification_remarks = db.Column(db.Text, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    ward_number = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(100), default='Tamil Nadu')
    district = db.Column(db.String(100), default='Chennai')
    street_name = db.Column(db.String(255), nullable=True)
    locality = db.Column(db.String(150), nullable=True)
    landmark = db.Column(db.String(150), nullable=True)
    pincode = db.Column(db.String(20), nullable=True)
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    is_escalated = db.Column(db.Boolean, default=False)
    escalated_at = db.Column(db.DateTime, nullable=True)
    escalation_reason = db.Column(db.Text, nullable=True)
    
    sla_due_date = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    reopen_reason = db.Column(db.Text, nullable=True)
    reopened_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assigned_officer = db.relationship('User', foreign_keys=[assigned_officer_id], backref='officer_assigned_complaints')
    assigned_worker = db.relationship('User', foreign_keys=[assigned_worker_id], backref='worker_assigned_complaints')
    assignments = db.relationship('ComplaintAssignment', backref='complaint', lazy='dynamic', cascade='all, delete-orphan')
    status_history = db.relationship('ComplaintStatusHistory', backref='complaint', lazy='dynamic', order_by='ComplaintStatusHistory.created_at.desc()', cascade='all, delete-orphan')
    attachments = db.relationship('ComplaintAttachment', backref='complaint', lazy='dynamic', cascade='all, delete-orphan')
    feedback = db.relationship('Feedback', backref='complaint', uselist=False, cascade='all, delete-orphan')
    
    @property
    def is_overdue(self):
        if self.status in ['Resolved', 'Rejected']:
            return False
        if self.sla_due_date and datetime.utcnow() > self.sla_due_date:
            return True
        return False
        
    @property
    def full_address(self):
        parts = []
        if self.street_name or self.address:
            parts.append(self.street_name or self.address)
        if self.locality:
            parts.append(self.locality)
        if self.landmark:
            parts.append(f"Near {self.landmark}")
        if self.ward_number:
            parts.append(f"Ward {self.ward_number}")
        if self.city:
            parts.append(self.city)
        if self.district and self.district != self.city:
            parts.append(self.district)
        if self.state:
            parts.append(self.state)
        if self.pincode:
            parts.append(f"PIN: {self.pincode}")
        return ", ".join(parts) if parts else "Address details recorded"

    @property
    def latest_assignment(self):
        return self.assignments.order_by(db.desc('assigned_at')).first()
        
    def to_dict(self):
        return {
            'id': self.id,
            'complaint_ref': self.complaint_ref,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'category_name': self.category.name if self.category else 'Unknown',
            'department_name': self.department.name if self.department else 'Unassigned',
            'department_id': self.department_id,
            'citizen_name': self.citizen.full_name if self.citizen else 'Citizen',
            'citizen_id': self.citizen_id,
            'address': self.address,
            'city': self.city,
            'ward_number': self.ward_number,
            'state': self.state,
            'district': self.district,
            'street_name': self.street_name,
            'locality': self.locality,
            'landmark': self.landmark,
            'pincode': self.pincode,
            'full_address': self.full_address,
            'latitude': float(self.latitude) if self.latitude is not None else None,
            'longitude': float(self.longitude) if self.longitude is not None else None,
            'is_escalated': self.is_escalated,
            'is_overdue': self.is_overdue,
            'sla_due_date': self.sla_due_date.strftime('%Y-%m-%d %H:%M:%S') if self.sla_due_date else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'resolved_at': self.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if self.resolved_at else None
        }
