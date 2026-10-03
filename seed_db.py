#!/usr/bin/env python
"""
Seed script to create initial admin/owner users for testing.

Run this after database migrations. If no migrations have been generated yet,
the script creates any missing tables so the seed can still succeed.
"""
from main.app import create_app, db
from main.models import User, ROLE_OWNER, ROLE_ADMIN


def seed_db():
    app = create_app("default")
    with app.app_context():
        # Create any missing tables (no-op for tables created by migrations)
        db.create_all()

        # Check if owner user already exists
        owner = User.query.filter_by(email="owner@insurance.com").first()
        if not owner:
            owner = User(
                full_name="Owner User",
                email="owner@insurance.com",
                phone="555-0001",
                role=ROLE_OWNER,
                is_active=True,
            )
            owner.set_password("password123")
            db.session.add(owner)
            print("Created owner user: owner@insurance.com / password123")

        # Check if admin user already exists
        admin = User.query.filter_by(email="admin@insurance.com").first()
        if not admin:
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
        print("Database seeding complete!")


if __name__ == "__main__":
    seed_db()

