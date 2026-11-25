from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from app import db
from app.models.user import User
from app.utils.helpers import validate_email, validate_mobile_number, validate_password_strength
from app.services.audit_service import log_action

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('user_role')
        role_dashboards = {
            'admin': 'admin.dashboard',
            'officer': 'officer.dashboard',
            'worker': 'worker.dashboard',
            'citizen': 'citizen.dashboard'
        }
        return redirect(url_for(role_dashboards.get(role, 'public.index')))
        
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        
        if not login_id or not password:
            flash("Please enter both your email/mobile and password.", "danger")
            return render_template('public/login.html', login_id=login_id)
            
        # Search by email or mobile number
        user = User.query.filter(
            (User.email == login_id.lower()) | (User.mobile_number == login_id)
        ).first()
        
        if not user or not user.check_password(password):
            flash("Invalid credentials. Please verify your email/mobile and password.", "danger")
            return render_template('public/login.html', login_id=login_id)
            
        if not user.is_active:
            flash("Your account has been deactivated. Please contact municipal administration.", "danger")
            return render_template('public/login.html', login_id=login_id)
            
        # Check if user is required to reset password on initial login
        if user.is_password_reset_required:
            session.clear()
            session['force_reset_user_id'] = user.id
            session['force_reset_name'] = user.full_name
            session['force_reset_email'] = user.email
            session['force_reset_role'] = user.role
            flash("Welcome! Since this is your first login, please set a new password to activate your account.", "info")
            return redirect(url_for('auth.force_reset_password'))

        # Set session (always persistent so refreshes never unexpectedly log users out)
        session.clear()
        session['user_id'] = user.id
        session['user_role'] = user.role
        session['user_name'] = user.full_name
        session.permanent = True
        
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        
        log_action(user.id, 'USER_LOGIN', 'user', user.id, details={'role': user.role, 'remember': remember})
        
        # Route to respective dashboard or safe relative next path
        role_dashboards = {
            'admin': 'admin.dashboard',
            'officer': 'officer.dashboard',
            'worker': 'worker.dashboard',
            'citizen': 'citizen.dashboard'
        }
        next_page = request.args.get('next', '').strip()
        if next_page and next_page.startswith('/') and not next_page.startswith('//'):
            return redirect(next_page)
            
        return redirect(url_for(role_dashboards.get(user.role, 'public.index')))
        
    return render_template('public/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('public.index'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        ward_number = request.form.get('ward_number', '').strip()
        
        form_data = {
            'full_name': full_name, 'email': email, 'mobile': mobile,
            'address': address, 'city': city, 'ward_number': ward_number
        }
        
        # Validations
        if not full_name or len(full_name) < 2:
            flash("Please provide a valid full name.", "danger")
            return render_template('public/register.html', **form_data)
            
        valid_email, email_res = validate_email(email)
        if not valid_email:
            flash(email_res, "danger")
            return render_template('public/register.html', **form_data)
        email = email_res
        
        valid_mob, mob_res = validate_mobile_number(mobile)
        if not valid_mob:
            flash(mob_res, "danger")
            return render_template('public/register.html', **form_data)
        mobile = mob_res
        
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('public/register.html', **form_data)
            
        valid_pw, pw_msg = validate_password_strength(password)
        if not valid_pw:
            flash(pw_msg, "danger")
            return render_template('public/register.html', **form_data)
            
        # Uniqueness checks
        if User.query.filter_by(email=email).first():
            flash("An account with this email address already exists. Please log in.", "danger")
            return render_template('public/register.html', **form_data)
            
        if User.query.filter_by(mobile_number=mobile).first():
            flash("An account with this mobile number already exists. Please log in.", "danger")
            return render_template('public/register.html', **form_data)
            
        new_user = User(
            role='citizen',
            full_name=full_name,
            email=email,
            mobile_number=mobile,
            address=address if address else None,
            city=city if city else 'City Centre',
            ward_number=ward_number if ward_number else 'Ward 1',
            is_active=True
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        log_action(new_user.id, 'CITIZEN_REGISTER', 'user', new_user.id)
        
        flash("Registration successful! You may now sign in with your credentials.", "success")
        return redirect(url_for('auth.login'))
        
    return render_template('public/register.html')

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        log_action(user_id, 'USER_LOGOUT', 'user', user_id)
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('public.index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        flash("If an active account exists with the provided details, password reset instructions have been dispatched.", "info")
        return redirect(url_for('auth.login'))
    return render_template('public/forgot_password.html')

@auth_bp.route('/force-reset-password', methods=['GET', 'POST'])
def force_reset_password():
    user_id = session.get('force_reset_user_id')
    if not user_id:
        flash("Session expired or invalid access. Please sign in.", "warning")
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user or not user.is_active:
        session.clear()
        flash("Invalid user account. Please contact municipal administration.", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password or not confirm_password:
            flash("Please enter and confirm your new password.", "danger")
            return render_template('public/force_reset_password.html', user=user)
            
        if new_password != confirm_password:
            flash("New passwords do not match. Please re-enter.", "danger")
            return render_template('public/force_reset_password.html', user=user)
            
        if len(new_password) < 6:
            flash("New password must be at least 6 characters long.", "danger")
            return render_template('public/force_reset_password.html', user=user)
            
        # Update user password and clear reset flag
        user.set_password(new_password)
        user.is_password_reset_required = False
        user.password_changed_at = datetime.utcnow()
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        
        log_action(user.id, 'PASSWORD_RESET_INITIAL', 'user', user.id, details={'role': user.role})
        
        # Log user in directly and route to their dashboard
        session.clear()
        session['user_id'] = user.id
        session['user_role'] = user.role
        session['user_name'] = user.full_name
        
        flash("Your password has been successfully updated! Welcome to your dashboard.", "success")
        
        role_dashboards = {
            'admin': 'admin.dashboard',
            'officer': 'officer.dashboard',
            'worker': 'worker.dashboard',
            'citizen': 'citizen.dashboard'
        }
        return redirect(url_for(role_dashboards.get(user.role, 'public.index')))
        
    return render_template('public/force_reset_password.html', user=user)
