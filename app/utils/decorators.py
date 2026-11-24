from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, g
from app.models.user import User

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
            
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.clear()
            flash("Your account is either inactive or does not exist. Please contact support.", "danger")
            return redirect(url_for('auth.login'))
            
        if user.is_password_reset_required:
            session.clear()
            session['force_reset_user_id'] = user.id
            session['force_reset_name'] = user.full_name
            session['force_reset_email'] = user.email
            session['force_reset_role'] = user.role
            flash("You must set a new password before accessing your account.", "info")
            return redirect(url_for('auth.force_reset_password'))

        g.user = user
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                flash("Please sign in to access this section.", "warning")
                return redirect(url_for('auth.login', next=request.url))
                
            user = User.query.get(user_id)
            if not user or not user.is_active:
                session.clear()
                flash("Your account is inactive. Please contact support.", "danger")
                return redirect(url_for('auth.login'))
                
            g.user = user
            
            if user.role not in allowed_roles:
                # Redirect user to their own role dashboard to prevent cross-dashboard access
                role_dashboards = {
                    'admin': 'admin.dashboard',
                    'officer': 'officer.dashboard',
                    'worker': 'worker.dashboard',
                    'citizen': 'citizen.dashboard'
                }
                dest = role_dashboards.get(user.role, 'public.index')
                flash(f"Unauthorized access. You have been redirected to your {user.role.title()} dashboard.", "danger")
                return redirect(url_for(dest))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
