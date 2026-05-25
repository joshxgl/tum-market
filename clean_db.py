from app import app, db, User, Listing, Notification

with app.app_context():
    print("Starting database cleanup...")
    try:
        # Order is important to avoid foreign key constraint violations
        db.session.query(Notification).delete()
        db.session.query(Listing).delete()
        db.session.query(User).delete()
        
        db.session.commit()
        print("Database cleaned successfully! All test users, listings, and notifications have been removed.")
    except Exception as e:
        db.session.rollback()
        print(f"An error occurred during cleanup: {e}")