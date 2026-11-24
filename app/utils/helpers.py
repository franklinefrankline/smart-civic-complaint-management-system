import os
import re
import uuid
import math
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

def generate_complaint_ref():
    """Generates unique complaint reference ID: CMP-YYYYMM-XXXXX"""
    now = datetime.utcnow()
    rand_str = uuid.uuid4().hex[:5].upper()
    return f"CMP-{now.strftime('%Y%m')}-{rand_str}"

def allowed_file(filename):
    """Validate allowed file extension against configuration"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file_obj, subfolder='complaints'):
    """Securely save uploaded file and return relative path and metadata"""
    if not file_obj or file_obj.filename == '':
        return None
        
    if not allowed_file(file_obj.filename):
        return None
        
    orig_name = secure_filename(file_obj.filename)
    ext = orig_name.rsplit('.', 1)[1].lower() if '.' in orig_name else 'jpg'
    unique_filename = f"{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"
    
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(target_dir, exist_ok=True)
    
    file_path = os.path.join(target_dir, unique_filename)
    file_obj.save(file_path)
    
    file_size = os.path.getsize(file_path)
    relative_path = f"uploads/{subfolder}/{unique_filename}"
    
    return {
        'filename': unique_filename,
        'original_name': orig_name,
        'file_path': relative_path,
        'file_size': file_size,
        'mime_type': file_obj.mimetype
    }

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth in meters
    """
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
        return 9999999.0
        
    R = 6371000  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def validate_password_strength(password):
    """
    Validate password:
    - Minimum 8 characters
    - At least one letter and at least one number
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit."
    return True, ""

def validate_mobile_number(mobile):
    """Validate 10-15 digit mobile number format"""
    cleaned = re.sub(r'[\s\-\+\(\)]', '', mobile)
    if not re.match(r'^\d{10,15}$', cleaned):
        return False, "Mobile number must be between 10 and 15 digits."
    return True, cleaned

def validate_email(email):
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(pattern, email.strip()):
        return False, "Invalid email address format."
    return True, email.strip().lower()
