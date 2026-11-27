import re
from sqlalchemy import func
from app import db
from app.models.user import User
from app.utils.helpers import validate_email, validate_mobile_number

DUP_EMAIL_TITLE = "Email Already Registered!"
DUP_EMAIL_MSG = "This email address is already associated with an existing account. Please enter a different email address."
DUP_MOBILE_TITLE = "Phone Number Already Registered!"
DUP_MOBILE_MSG = "This phone number is already associated with an existing account. Please enter a different phone number."
DUP_BOTH_TITLE = "Account Details Already Exist!"
DUP_BOTH_MSG = "This email address and phone number are already registered. Please enter different details."


def duplicate_title_for_field(field, default_title="Validation Error"):
    """Return the standardized alert popup title for a duplicate or validation field."""
    mapping = {
        'email': DUP_EMAIL_TITLE,
        'mobile': DUP_MOBILE_TITLE,
        'both': DUP_BOTH_TITLE,
        'employee_id': "Employee ID Already Exists!",
    }
    return mapping.get(field, default_title)


def normalize_email_value(email):
    """Trim whitespace and lowercase an email address consistently."""
    return (email or '').strip().lower()


def normalize_phone_value(mobile):
    """Strip whitespace and formatting punctuation consistently from phone numbers."""
    return re.sub(r'[\s\-\+\(\)]', '', (mobile or '').strip())


def _normalized_mobile_column():
    expr = User.mobile_number
    for ch in (' ', '-', '+', '(', ')'):
        expr = func.replace(expr, ch, '')
    return expr


def check_duplicate_user_contacts(email_raw, mobile_raw, exclude_user_id=None):
    """
    Check email (case-insensitive) and phone number (punctuation-normalized)
    uniqueness against existing User rows in the database.
    Returns: (error_message, error_field, clean_email, clean_mobile)
    """
    clean_email = normalize_email_value(email_raw)
    clean_mobile = normalize_phone_value(mobile_raw)

    email_exists = False
    if clean_email:
        email_q = User.query.filter(func.lower(User.email) == clean_email)
        if exclude_user_id is not None:
            email_q = email_q.filter(User.id != exclude_user_id)
        email_exists = email_q.first() is not None

    mobile_exists = False
    if clean_mobile:
        norm_col = _normalized_mobile_column()
        raw_trimmed = (mobile_raw or '').strip()
        mobile_q = User.query.filter((norm_col == clean_mobile) | (User.mobile_number == raw_trimmed))
        if exclude_user_id is not None:
            mobile_q = mobile_q.filter(User.id != exclude_user_id)
        mobile_exists = mobile_q.first() is not None

    if email_exists and mobile_exists:
        return DUP_BOTH_MSG, 'both', clean_email, clean_mobile
    if email_exists:
        return DUP_EMAIL_MSG, 'email', clean_email, clean_mobile
    if mobile_exists:
        return DUP_MOBILE_MSG, 'mobile', clean_email, clean_mobile
    return None, None, clean_email, clean_mobile


def validate_contact_and_duplicates(email_raw, mobile_raw, exclude_user_id=None):
    """
    Validate & normalize email + phone format and check database uniqueness.
    Returns: (error_message, error_field, clean_email, clean_mobile)
    """
    raw_email = (email_raw or '').strip()
    raw_mobile = (mobile_raw or '').strip()

    if not raw_email:
        return "Email address is required.", 'email', '', normalize_phone_value(raw_mobile)
    ok_email, email_res = validate_email(raw_email)
    if not ok_email:
        return email_res, 'email', normalize_email_value(raw_email), normalize_phone_value(raw_mobile)

    if not raw_mobile:
        return "Phone number is required.", 'mobile', email_res, ''
    ok_mobile, mobile_res = validate_mobile_number(raw_mobile)
    if not ok_mobile:
        return mobile_res, 'mobile', email_res, normalize_phone_value(raw_mobile)

    return check_duplicate_user_contacts(email_res, mobile_res, exclude_user_id=exclude_user_id)


def resolve_duplicate_integrity_error(exc, email_raw, mobile_raw, exclude_user_id=None):
    """
    Safely recover from a DB unique constraint IntegrityError (e.g. concurrent submit race)
    and map it cleanly to an error message and field identifier.
    """
    db.session.rollback()
    msg, field, _, _ = check_duplicate_user_contacts(email_raw, mobile_raw, exclude_user_id=exclude_user_id)
    if msg:
        return msg, field

    detail = str(getattr(exc, 'orig', exc)).lower()
    if 'employee_id' in detail:
        return "A worker with this Employee ID already exists.", 'employee_id'
    if 'mobile' in detail or 'phone' in detail:
        return DUP_MOBILE_MSG, 'mobile'
    if 'email' in detail:
        return DUP_EMAIL_MSG, 'email'
    return DUP_BOTH_MSG, 'both'
