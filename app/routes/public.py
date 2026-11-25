from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from app import db
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.complaint import Complaint
from app.models.user import User
from app.models.feedback import Feedback
from app.models.contact import ContactMessage

from app.services.complaint_service import get_complaint_9_stage_timeline
from app.services.notification_service import notify_admins

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    departments = Department.query.filter_by(is_active=True).all()
    categories = ComplaintCategory.query.filter_by(is_active=True).limit(8).all()
    
    # Live stats
    total_complaints = Complaint.query.count()
    resolved_complaints = Complaint.query.filter_by(status='Resolved').count()
    active_departments = Department.query.filter_by(is_active=True).count()
    
    avg_rating = 4.8
    feedbacks = Feedback.query.all()
    if feedbacks:
        avg_rating = round(sum(f.rating for f in feedbacks) / len(feedbacks), 1)
        
    stats = {
        'total': total_complaints,
        'resolved': resolved_complaints,
        'departments': active_departments,
        'rating': avg_rating
    }
    
    return render_template(
        'public/index.html',
        departments=departments,
        categories=categories,
        stats=stats
    )

@public_bp.route('/about')
def about():
    departments_count = Department.query.filter_by(is_active=True).count()
    return render_template('public/about.html', departments_count=departments_count)

@public_bp.route('/how-it-works')
def how_it_works():
    return render_template('public/how_it_works.html')

@public_bp.route('/departments')
def departments():
    dept_list = Department.query.filter_by(is_active=True).all()
    return render_template('public/departments.html', departments=dept_list)

@public_bp.route('/track', methods=['GET', 'POST'])
def track():
    complaint = None
    not_found = False
    
    ref = request.args.get('ref') or (request.form.get('ref') if request.method == 'POST' else None)
    identifier = request.args.get('identifier') or (request.form.get('identifier') if request.method == 'POST' else None)
    
    if ref:
        ref = ref.strip().upper()
        query = Complaint.query.filter_by(complaint_ref=ref)
        
        # Privacy verification if phone/email provided
        if identifier:
            identifier = identifier.strip().lower()
            complaint_obj = query.first()
            if complaint_obj and complaint_obj.citizen:
                citizen = complaint_obj.citizen
                if citizen.email.lower() == identifier or citizen.mobile_number.endswith(identifier[-4:]):
                    complaint = complaint_obj
                else:
                    not_found = True
            else:
                not_found = True
        else:
            complaint = query.first()
            if not complaint:
                not_found = True
                
    stages = get_complaint_9_stage_timeline(complaint) if complaint else []
    return render_template('public/track.html', complaint=complaint, not_found=not_found, search_ref=ref, stages=stages)

@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        contact_info = (request.form.get('contact') or '').strip()
        message_text = (request.form.get('message') or '').strip()

        if not name or not contact_info or not message_text:
            flash("Please enter your name, email/phone, and inquiry message.", "danger")
            return redirect(url_for('public.contact'))

        user_id = session.get('user_id')
        msg = ContactMessage(
            name=name[:120],
            contact=contact_info[:150],
            message=message_text,
            user_id=user_id,
            is_read=False,
        )
        db.session.add(msg)
        db.session.commit()

        preview = (message_text[:160] + '...') if len(message_text) > 160 else message_text
        notify_admins(
            title=f"New Contact Inquiry: {name}",
            message=f"From {name} ({contact_info}): {preview}",
            notification_type='info',
            link=url_for('admin.dashboard') + '#contactInquiriesCard',
        )

        flash("Thank you for reaching out. Your inquiry has been sent to the civic administration dashboard.", "success")
        return redirect(url_for('public.contact'))
    return render_template('public/contact.html')

@public_bp.route('/set-language/<lang>')
def set_language(lang):
    if lang in ['en', 'ta', 'hi']:
        session['lang'] = lang
    referer = request.headers.get('Referer')
    return redirect(referer or url_for('public.index'))

@public_bp.route('/privacy')
def privacy():
    return render_template('public/privacy.html')

@public_bp.route('/cookies')
def cookies():
    return render_template('public/cookies.html')

@public_bp.route('/terms')
def terms():
    return render_template('public/terms.html')
