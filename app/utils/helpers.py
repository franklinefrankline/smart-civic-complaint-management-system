import os
import re
import uuid
import math
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import current_app, request, has_request_context
from markupsafe import Markup, escape


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
    """
    Validate uploaded file, read binary bytes for persistent DB storage,
    and write a local copy to UPLOAD_FOLDER when writable.
    """
    if not file_obj or file_obj.filename == '':
        return None

    if not allowed_file(file_obj.filename):
        return None

    orig_name = secure_filename(file_obj.filename)
    ext = orig_name.rsplit('.', 1)[1].lower() if '.' in orig_name else 'jpg'
    unique_filename = f"{uuid.uuid4().hex}_{int(datetime.utcnow().timestamp())}.{ext}"

    # Read binary bytes into memory for persistent DB storage
    stream = file_obj.stream
    try:
        stream.seek(0)
    except Exception:
        pass
    file_bytes = stream.read()
    file_size = len(file_bytes)

    # Best-effort disk cache write (ephemeral on Render, persistent locally)
    try:
        target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, unique_filename)
        with open(file_path, 'wb') as out_fp:
            out_fp.write(file_bytes)
    except Exception:
        pass

    relative_path = f"uploads/{subfolder}/{unique_filename}"

    return {
        'filename': unique_filename,
        'original_name': orig_name,
        'file_path': relative_path,
        'file_size': file_size,
        'mime_type': file_obj.mimetype,
        'file_data': file_bytes
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


def get_request_tz_offset_minutes(default_offset_minutes=330):
    """
    Resolve timezone offset east of UTC in minutes from browser cookie `sccmt_tz_offset`
    (JS Date.getTimezoneOffset() is minutes west of UTC, e.g. -330 for IST +05:30).
    Defaults to +330 minutes (IST) so first-visit SSR displays accurate local time.
    """
    if has_request_context():
        raw = request.cookies.get('sccmt_tz_offset')
        if raw is not None:
            try:
                js_offset = int(raw)
                if -840 <= js_offset <= 840:
                    return -js_offset
            except (TypeError, ValueError):
                pass
    return default_offset_minutes


def utc_to_local(dt, default_offset_minutes=330):
    """Convert naive UTC datetime stored in DB into user's local datetime."""
    if not dt:
        return None
    offset_mins = get_request_tz_offset_minutes(default_offset_minutes=default_offset_minutes)
    return dt + timedelta(minutes=offset_mins)


def format_local_time(dt, fmt='%d %b %Y, %I:%M %p', fallback=''):
    """
    Render a UTC datetime in user's local time wrapped in <time data-utc="...">
    so both SSR (via tz cookie / IST default) and live client JS display exact current local time.
    """
    if not dt:
        return fallback
    local_dt = utc_to_local(dt)
    rendered = local_dt.strftime(fmt)
    iso_utc = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return Markup(
        f'<time datetime="{iso_utc}" data-utc="{iso_utc}" data-fmt="{escape(fmt)}">{escape(rendered)}</time>'
    )
