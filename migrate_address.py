from app import create_app, db

app = create_app()
with app.app_context():
    existing_cols = [c[0] for c in db.session.execute(db.text('DESCRIBE complaints')).fetchall()]
    cols_to_add = [
        ('state', 'VARCHAR(100) DEFAULT \'Tamil Nadu\''),
        ('district', 'VARCHAR(100) DEFAULT \'Chennai\''),
        ('street_name', 'VARCHAR(255) NULL'),
        ('locality', 'VARCHAR(150) NULL'),
        ('landmark', 'VARCHAR(150) NULL'),
        ('pincode', 'VARCHAR(20) NULL')
    ]
    for col_name, col_def in cols_to_add:
        if col_name not in existing_cols:
            db.session.execute(db.text(f'ALTER TABLE complaints ADD COLUMN {col_name} {col_def}'))
            print(f'Added column {col_name}')
        else:
            print(f'Column {col_name} already exists')
    db.session.commit()

    db.session.execute(db.text('UPDATE complaints SET street_name = address WHERE street_name IS NULL AND address IS NOT NULL'))
    db.session.execute(db.text("UPDATE complaints SET locality = 'Central Zone' WHERE locality IS NULL"))
    db.session.execute(db.text("UPDATE complaints SET pincode = '600001' WHERE pincode IS NULL"))
    db.session.commit()
    print('Schema migrated and existing complaint records updated successfully!')
