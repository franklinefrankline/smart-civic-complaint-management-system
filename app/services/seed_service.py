"""
Seeding service for initializing civic departments, categories, settings, 
and default system users (Administrator, Department Officers, Field Workers, Citizen).
"""
from app import db
from app.models.user import User
from app.models.department import Department
from app.models.category import ComplaintCategory
from app.models.workflow import Worker
from app.models.audit import SystemSetting

def seed_all():
    """Populate database with initial civic departments, categories, and test accounts."""
    # 1. System Settings
    settings = [
        ('portal_name', 'Smart Civic Complaint Management System', 'Portal Title'),
        ('sla_low_hours', '168', 'Low priority SLA resolution target'),
        ('sla_medium_hours', '96', 'Medium priority SLA resolution target'),
        ('sla_high_hours', '48', 'High priority SLA resolution target'),
        ('sla_urgent_hours', '24', 'Urgent priority SLA resolution target'),
        ('duplicate_radius_meters', '500', 'Radius in meters for duplicate warning')
    ]
    for key, val, desc in settings:
        if not SystemSetting.query.filter_by(setting_key=key).first():
            db.session.add(SystemSetting(setting_key=key, setting_value=val, description=desc))

    # 2. Suggested Civic Departments
    departments_data = [
        ("Water Supply & Sewage", "WATER", "Responsible for drinking water distribution, pipeline leakages, and sewage blockages.", "water.desk@civic.gov", "044-2561-1001"),
        ("Electricity & Power", "ELEC", "Handles power outages, transformer sparks, damaged wires, and street light poles.", "power.desk@civic.gov", "044-2561-1002"),
        ("Roads & Transportation", "ROADS", "Fixes potholes, damaged asphalt, missing road barriers, and footpath repairs.", "roads.desk@civic.gov", "044-2561-1003"),
        ("Sanitation & Waste Management", "SAN", "Solid waste removal, garbage dump clearance, and community bin sanitization.", "sanitation.desk@civic.gov", "044-2561-1004"),
        ("Drainage & Flood Control", "DRAIN", "Monsoon drain clearance, clogged culverts, and stagnant water removal.", "drainage.desk@civic.gov", "044-2561-1005"),
        ("Street Lighting", "LIGHT", "Repair of non-functioning streetlights, timing automation, and bulb replacements.", "lighting.desk@civic.gov", "044-2561-1006"),
        ("Public Health & Vector Control", "HEALTH", "Fogging operations, mosquito breeding eradication, and hygiene compliance.", "health.desk@civic.gov", "044-2561-1007"),
        ("Parks & Public Spaces", "PARKS", "Maintenance of public parks, play equipment, fallen trees, and open green belts.", "parks.desk@civic.gov", "044-2561-1008"),
        ("Other Civic Services", "CIVIC", "General municipal inquiries, civic encroachments, and stray animal reporting.", "general.desk@civic.gov", "044-2561-1009"),
        ("CS & BS", "4014", "Computer Science & Business Systems Municipal Branch.", "csbs.desk@civic.gov", "044-2561-1010")
    ]

    dept_objs = {}
    for name, code, desc, email, phone in departments_data:
        dept = Department.query.filter_by(code=code).first()
        if not dept:
            dept = Department(name=name, code=code, description=desc, contact_email=email, contact_phone=phone, is_active=True)
            db.session.add(dept)
            db.session.flush()
        dept_objs[code] = dept

    # 3. Complaint Categories
    categories_data = [
        ("Drinking Water Pipe Leakage", "WATER", "urgent", 24, "Pipe bursts, heavy water wastage, contamination"),
        ("Contaminated Water Supply", "WATER", "high", 48, "Muddy or smelling tap water in household"),
        ("Low Water Pressure", "WATER", "medium", 96, "Weak pressure or erratic timing of municipal supply"),
        ("Power Line Hazard / Sparks", "ELEC", "urgent", 24, "Fallen wire, sparking junction box, immediate danger"),
        ("Streetlight Defect / Dark Zone", "LIGHT", "medium", 72, "Bulb burnt out or entire stretch flickering"),
        ("Deep Pothole / Road Cave-in", "ROADS", "high", 48, "Crater on main vehicular road posing accident risk"),
        ("Broken Footpath / Paver Blocks", "ROADS", "low", 168, "Pedestrian pathway damaged or missing tiles"),
        ("Overflowing Garbage Dump", "SAN", "high", 48, "Commercial or residential community bin overflowing"),
        ("Door-to-Door Waste Not Collected", "SAN", "medium", 72, "Daily waste collection truck missed route"),
        ("Clogged Stormwater Drain", "DRAIN", "high", 48, "Waterlogging on road during rains due to blocked drain"),
        ("Stagnant Water / Mosquito Hazard", "HEALTH", "medium", 96, "Need for anti-larval spraying and chemical fogging"),
        ("Fallen Tree / Heavy Branch", "PARKS", "urgent", 24, "Tree fallen blocking thoroughfare or electric line")
    ]

    for name, dept_code, priority, sla, desc in categories_data:
        cat = ComplaintCategory.query.filter_by(name=name).first()
        if not cat and dept_code in dept_objs:
            cat = ComplaintCategory(
                name=name,
                department_id=dept_objs[dept_code].id,
                default_priority=priority,
                sla_hours=sla,
                description=desc,
                is_active=True
            )
            db.session.add(cat)
            db.session.flush()

    # 4. Master Administrator
    admin = User.query.filter_by(email="admin@civic.gov").first()
    if not admin:
        admin = User(
            role='admin',
            full_name='Chief Municipal Commissioner',
            email='admin@civic.gov',
            mobile_number='9800000001',
            address='Municipal Headquarters, Secretariat',
            city='Central City',
            ward_number='HQ',
            is_active=True
        )
        admin.set_password('Admin@123')
        db.session.add(admin)

    # 5. Demo Citizen Account
    citizen = User.query.filter_by(email="citizen@civic.gov").first()
    if not citizen:
        citizen = User(
            role='citizen',
            full_name='Arun Kumar (Citizen)',
            email='citizen@civic.gov',
            mobile_number='9800000002',
            address='14 Anna Nagar West',
            city='Coimbatore',
            ward_number='3',
            is_active=True
        )
        citizen.set_password('Citizen@123')
        db.session.add(citizen)

    # 6. Default Department Officers for all civic departments
    officers_seed = [
        ("WATER", "Suresh Raman (Water Officer)", "officer.water@civic.gov", "9840123451"),
        ("ELEC", "Rajesh K (Electricity Officer)", "officer.elec@civic.gov", "9840123452"),
        ("ROADS", "Berline (Roads Officer)", "officer.roads@civic.gov", "9840123453"),
        ("SAN", "Murugan P (Sanitation Officer)", "officer.sanitation@civic.gov", "9840123454"),
        ("DRAIN", "Anbarasu S (Drainage Officer)", "officer.drainage@civic.gov", "9840123455"),
        ("LIGHT", "Karthik N (Lighting Officer)", "officer.lighting@civic.gov", "9840123456"),
        ("HEALTH", "Dr. Meenakshi S (Health Officer)", "officer.health@civic.gov", "9840123457"),
        ("PARKS", "Venkatesh L (Parks Officer)", "officer.parks@civic.gov", "9840123458"),
        ("CIVIC", "Priya R (Civic Officer)", "officer.civic@civic.gov", "9840123459"),
        ("4014", "Kavitha M (CS & BS Officer)", "officer.csbs@civic.gov", "9840123450")
    ]
    for dept_code, name, email, phone in officers_seed:
        dept_obj = dept_objs.get(dept_code) or Department.query.filter_by(code=dept_code).first()
        if dept_obj and not User.query.filter_by(email=email).first():
            off = User(
                role='officer',
                full_name=name,
                email=email,
                mobile_number=phone,
                department_id=dept_obj.id,
                is_active=True
            )
            off.set_password('Officer@123')
            db.session.add(off)

    # 7. Default Field Workers for civic departments
    workers_seed = [
        ("WATER", "Frank Senior Field Worker", "worker.water@civic.gov", "9840223451", "Senior Pipeline Technician"),
        ("ELEC", "Mani K (Power Technician)", "worker.elec@civic.gov", "9840223452", "High Voltage Line Worker"),
        ("ROADS", "Selvam R (Road Maintenance)", "worker.roads@civic.gov", "9840223453", "Asphalt Repair Crew Lead"),
        ("SAN", "Ramesh G (Sanitation Worker)", "worker.sanitation@civic.gov", "9840223454", "Waste Clearance Lead"),
        ("DRAIN", "Dinesh S (Drainage Tech)", "worker.drainage@civic.gov", "9840223455", "Stormwater Drainage Specialist"),
        ("LIGHT", "Kumar M (Lighting Electrician)", "worker.lighting@civic.gov", "9840223456", "Streetlight Electrician"),
        ("HEALTH", "Balu T (Vector Control Worker)", "worker.health@civic.gov", "9840223457", "Sanitation & Fogging Operator"),
        ("PARKS", "Siva V (Parks Groundskeeper)", "worker.parks@civic.gov", "9840223458", "Horticulture Maintenance Lead"),
        ("CIVIC", "Vijay K (Civic Field Crew)", "worker.civic@civic.gov", "9840223459", "General Public Works Worker"),
        ("4014", "Arun P (CS & BS Field Tech)", "worker.csbs@civic.gov", "9840223450", "Hardware & Infrastructure Tech")
    ]
    for dept_code, name, email, phone, skill in workers_seed:
        dept_obj = dept_objs.get(dept_code) or Department.query.filter_by(code=dept_code).first()
        if dept_obj and not User.query.filter_by(email=email).first():
            w_user = User(
                role='worker',
                full_name=name,
                email=email,
                mobile_number=phone,
                department_id=dept_obj.id,
                is_active=True
            )
            w_user.set_password('Worker@123')
            db.session.add(w_user)
            db.session.flush()
            worker_record = Worker(
                user_id=w_user.id,
                department_id=dept_obj.id,
                skills=skill,
                status='available',
                active_task_count=0
            )
            db.session.add(worker_record)

    db.session.commit()
