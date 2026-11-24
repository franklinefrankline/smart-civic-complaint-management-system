from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum('citizen', 'admin', 'officer', 'worker'), nullable=False, default='citizen')
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(191), unique=True, nullable=False, index=True)
    mobile_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    ward_number = db.Column(db.String(50), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_password_reset_required = db.Column(db.Boolean, default=False, nullable=False)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    department = db.relationship('Department', foreign_keys=[department_id], backref=db.backref('staff_members', lazy='dynamic'))
    complaints = db.relationship('Complaint', foreign_keys='Complaint.citizen_id', backref='citizen', lazy='dynamic')
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    worker_profile = db.relationship('Worker', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def is_admin(self):
        return self.role == 'admin'
        
    @property
    def is_officer(self):
        return self.role == 'officer'
        
    @property
    def is_worker(self):
        return self.role == 'worker'
        
    @property
    def is_citizen(self):
        return self.role == 'citizen'
        
    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'full_name': self.full_name,
            'email': self.email,
            'mobile_number': self.mobile_number,
            'address': self.address,
            'city': self.city,
            'ward_number': self.ward_number,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'is_active': self.is_active,
            'is_password_reset_required': self.is_password_reset_required,
            'password_changed_at': self.password_changed_at.strftime('%Y-%m-%d %H:%M:%S') if self.password_changed_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
