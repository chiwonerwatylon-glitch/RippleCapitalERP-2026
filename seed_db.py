#!/usr/bin/env python
"""
Seed script to create initial admin/owner users for testing.

Run this after database migrations. If no migrations have been generated yet,
the script creates any missing tables so the seed can still succeed.
"""
from main.app import create_app, db
from main.models import User, Company, InsuranceProduct, ROLE_OWNER, ROLE_ADMIN

DEFAULT_COMPANIES = [
    {
        "name": "Ripple Capital Insurance",
        "contact_email": "info@ripplecapitalinsurance.com",
        "phone": "555-1000",
        "address": "1 Ripple Plaza, Main Street",
        "website": "https://www.ripplecapitalinsurance.com",
        "description": "Default underwriting company.",
    },
    {
        "name": "Partner Insurance Company",
        "contact_email": "info@partnerinsurance.com",
        "phone": "555-2000",
        "address": "25 Partner Avenue, Central Business District",
        "website": "https://www.partnerinsurance.com",
        "description": "Default partner underwriting company.",
    },
]

DEFAULT_PRODUCTS = [
    {
        "name": "Motor Comprehensive",
        "coverage_type": "Motor",
        "description": "Covers loss or damage to the insured vehicle and liability to third parties.",
    },
    {
        "name": "Third Party",
        "coverage_type": "Motor",
        "description": "Covers legal liability for injury or damage to third parties caused by the insured vehicle.",
    },
    {
        "name": "Full Third Party",
        "coverage_type": "Motor",
        "description": "Third party liability plus fire and theft cover for the insured vehicle.",
    },
    {
        "name": "Homeowners",
        "coverage_type": "Property",
        "description": "Covers the home structure and permanent fixtures against insured perils.",
    },
    {
        "name": "Household",
        "coverage_type": "Property",
        "description": "Covers household contents and personal belongings against loss or damage.",
    },
    {
        "name": "Business Combined",
        "coverage_type": "General Insurance",
        "description": "Package cover for business property, contents, money and liability.",
    },
    {
        "name": "GIT (Goods in Transit)",
        "coverage_type": "Specialty",
        "description": "Covers goods against loss or damage while being transported.",
    },
    {
        "name": "Agriculture",
        "coverage_type": "Specialty",
        "description": "Covers crops, livestock and farm assets against insured risks.",
    },
    {
        "name": "Asset All Risk",
        "coverage_type": "Property",
        "description": "Broad cover for physical loss or damage to insured assets from any non-excluded cause.",
    },
]


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

        # Ensure the owner has an id before linking companies and products
        db.session.flush()

        for company_data in DEFAULT_COMPANIES:
            company = Company.query.filter_by(
                owner_id=owner.id, name=company_data["name"]
            ).first()
            if not company:
                company = Company(owner_id=owner.id, **company_data)
                db.session.add(company)
                db.session.flush()
                print(f"Created company: {company.name}")

            for product_data in DEFAULT_PRODUCTS:
                exists = InsuranceProduct.query.filter_by(
                    owner_id=owner.id,
                    company_id=company.id,
                    name=product_data["name"],
                ).first()
                if not exists:
                    db.session.add(
                        InsuranceProduct(
                            owner_id=owner.id,
                            company_id=company.id,
                            **product_data,
                        )
                    )
                    print(f"Created product: {product_data['name']} ({company.name})")

        db.session.commit()
        print("Database seeding complete!")


if __name__ == "__main__":
    seed_db()

