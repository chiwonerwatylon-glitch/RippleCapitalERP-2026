from main.app import create_app, db
from main.models import User, ROLE_AGENT, ROLE_ADMIN

app = create_app()

# Initialize database tables and seed test data on startup
with app.app_context():
    db.create_all()
    
    # Create test agent account if it doesn't exist
    if not User.query.filter_by(email="agent@insurance.com").first():
        agent = User(
            full_name="Agent User",
            email="agent@insurance.com",
            phone="555-0001",
            role=ROLE_AGENT,
            is_active=True,
        )
        agent.set_password("password123")
        db.session.add(agent)
        print("Created agent user: agent@insurance.com / password123")
    
    # Create test admin account if it doesn't exist
    if not User.query.filter_by(email="admin@insurance.com").first():
        admin = User(
            full_name="Admin User",
            email="admin@insurance.com",
            phone="555-0002",
            role=ROLE_ADMIN,
            is_active=True,
        )
        admin.set_password("admin123")
        db.session.add(admin)
        print("Created admin user: admin@insurance.com / admin123")
    
    db.session.commit()

if __name__ == "__main__":
    app.run()

