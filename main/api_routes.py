"""
API routes for Owner/User dashboard features:
- Profile management
- Client management
- Company management
- Product management
- Commission rules
- Policy management
- Premium remittance tracking
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
from pathlib import Path

from .models import db, Client, Company, InsuranceProduct, CommissionRule, Policy, PremiumRemittance

api_bp = Blueprint("api", __name__, url_prefix="/api")

# ==================== PROFILE MANAGEMENT ====================

@api_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    """Get current user profile"""
    user = current_user
    return jsonify({
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "profile_picture_url": user.profile_picture_url,
        "created_at": user.created_at.isoformat()
    }), 200


@api_bp.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    """Update user profile"""
    data = request.get_json()
    
    user = current_user
    user.full_name = data.get("full_name", user.full_name)
    user.phone = data.get("phone", user.phone)
    user.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Profile updated successfully"}), 200


@api_bp.route("/profile/picture", methods=["POST"])
@login_required
def upload_profile_picture():
    """Upload profile picture"""
    if "picture" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["picture"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    # Validate file type
    allowed_extensions = {"png", "jpg", "jpeg", "gif"}
    if not ("." in file.filename and file.filename.rsplit(".", 1)[1].lower() in allowed_extensions):
        return jsonify({"error": "Invalid file type"}), 400
    
    # Create uploads directory if it doesn't exist
    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "profile_pictures"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file with secure filename
    filename = secure_filename(f"{current_user.id}_{datetime.utcnow().timestamp()}_{file.filename}")
    filepath = upload_dir / filename
    file.save(filepath)
    
    # Update user's profile picture URL
    current_user.profile_picture_url = f"/static/uploads/profile_pictures/{filename}"
    current_user.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "message": "Profile picture uploaded successfully",
        "profile_picture_url": current_user.profile_picture_url
    }), 200


# ==================== CLIENT MANAGEMENT ====================

@api_bp.route("/clients", methods=["GET"])
@login_required
def get_clients():
    """Get all clients for current user"""
    clients = Client.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "clients": [{
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "identification_type": c.identification_type,
            "identification_number": c.identification_number,
            "created_at": c.created_at.isoformat()
        } for c in clients]
    }), 200


@api_bp.route("/clients", methods=["POST"])
@login_required
def add_client():
    """Add a single client"""
    data = request.get_json()
    
    client = Client(
        user_id=current_user.id,
        name=data.get("name"),
        email=data.get("email"),
        phone=data.get("phone"),
        address=data.get("address"),
        identification_type=data.get("identification_type"),
        identification_number=data.get("identification_number")
    )
    
    db.session.add(client)
    db.session.commit()
    
    return jsonify({
        "message": "Client added successfully",
        "client_id": client.id
    }), 201


@api_bp.route("/clients/<int:client_id>", methods=["PUT"])
@login_required
def update_client(client_id):
    """Update a client"""
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    data = request.get_json()
    client.name = data.get("name", client.name)
    client.email = data.get("email", client.email)
    client.phone = data.get("phone", client.phone)
    client.address = data.get("address", client.address)
    client.identification_type = data.get("identification_type", client.identification_type)
    client.identification_number = data.get("identification_number", client.identification_number)
    client.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Client updated successfully"}), 200


@api_bp.route("/clients/<int:client_id>", methods=["DELETE"])
@login_required
def delete_client(client_id):
    """Delete a client"""
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first()
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    db.session.delete(client)
    db.session.commit()
    return jsonify({"message": "Client deleted successfully"}), 200


@api_bp.route("/clients/bulk-upload", methods=["POST"])
@login_required
def bulk_upload_clients():
    """Bulk upload clients from Excel file"""
    try:
        import pandas as pd
        
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        
        # Read Excel file
        df = pd.read_excel(file)
        
        # Expected columns: name, email, phone, address, identification_type, identification_number
        required_columns = ["name"]
        if not all(col in df.columns for col in required_columns):
            return jsonify({"error": f"Missing required columns: {required_columns}"}), 400
        
        added_count = 0
        for _, row in df.iterrows():
            client = Client(
                user_id=current_user.id,
                name=row.get("name"),
                email=row.get("email"),
                phone=row.get("phone"),
                address=row.get("address"),
                identification_type=row.get("identification_type"),
                identification_number=row.get("identification_number")
            )
            db.session.add(client)
            added_count += 1
        
        db.session.commit()
        return jsonify({
            "message": f"Successfully added {added_count} clients",
            "count": added_count
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ==================== COMPANY MANAGEMENT ====================

@api_bp.route("/companies", methods=["GET"])
@login_required
def get_companies():
    """Get all companies for current user"""
    companies = Company.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "companies": [{
            "id": c.id,
            "name": c.name,
            "contact_person": c.contact_person,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "created_at": c.created_at.isoformat()
        } for c in companies]
    }), 200


@api_bp.route("/companies", methods=["POST"])
@login_required
def add_company():
    """Add a company"""
    data = request.get_json()
    
    company = Company(
        user_id=current_user.id,
        name=data.get("name"),
        contact_person=data.get("contact_person"),
        email=data.get("email"),
        phone=data.get("phone"),
        address=data.get("address")
    )
    
    db.session.add(company)
    db.session.commit()
    
    return jsonify({
        "message": "Company added successfully",
        "company_id": company.id
    }), 201


@api_bp.route("/companies/<int:company_id>", methods=["PUT"])
@login_required
def update_company(company_id):
    """Update a company"""
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    data = request.get_json()
    company.name = data.get("name", company.name)
    company.contact_person = data.get("contact_person", company.contact_person)
    company.email = data.get("email", company.email)
    company.phone = data.get("phone", company.phone)
    company.address = data.get("address", company.address)
    company.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Company updated successfully"}), 200


@api_bp.route("/companies/<int:company_id>", methods=["DELETE"])
@login_required
def delete_company(company_id):
    """Delete a company"""
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        return jsonify({"error": "Company not found"}), 404
    
    db.session.delete(company)
    db.session.commit()
    return jsonify({"message": "Company deleted successfully"}), 200


# ==================== PRODUCT MANAGEMENT ====================

@api_bp.route("/products", methods=["GET"])
@login_required
def get_products():
    """Get all products for current user"""
    company_id = request.args.get("company_id")
    
    query = InsuranceProduct.query.filter_by(user_id=current_user.id)
    if company_id:
        query = query.filter_by(company_id=company_id)
    
    products = query.all()
    return jsonify({
        "products": [{
            "id": p.id,
            "company_id": p.company_id,
            "company_name": p.company.name,
            "product_name": p.product_name,
            "description": p.description,
            "base_commission_rate": p.base_commission_rate,
            "created_at": p.created_at.isoformat()
        } for p in products]
    }), 200


@api_bp.route("/products", methods=["POST"])
@login_required
def add_product():
    """Add a product"""
    data = request.get_json()
    
    product = InsuranceProduct(
        user_id=current_user.id,
        company_id=data.get("company_id"),
        product_name=data.get("product_name"),
        description=data.get("description"),
        base_commission_rate=data.get("base_commission_rate", 10.0)
    )
    
    db.session.add(product)
    db.session.commit()
    
    return jsonify({
        "message": "Product added successfully",
        "product_id": product.id
    }), 201


@api_bp.route("/products/<int:product_id>", methods=["PUT"])
@login_required
def update_product(product_id):
    """Update a product"""
    product = InsuranceProduct.query.filter_by(id=product_id, user_id=current_user.id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404
    
    data = request.get_json()
    product.product_name = data.get("product_name", product.product_name)
    product.description = data.get("description", product.description)
    product.base_commission_rate = data.get("base_commission_rate", product.base_commission_rate)
    product.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Product updated successfully"}), 200


@api_bp.route("/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(product_id):
    """Delete a product"""
    product = InsuranceProduct.query.filter_by(id=product_id, user_id=current_user.id).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404
    
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted successfully"}), 200


# ==================== COMMISSION RULES ====================

@api_bp.route("/commission-rules", methods=["GET"])
@login_required
def get_commission_rules():
    """Get all commission rules for current user"""
    company_id = request.args.get("company_id")
    product_id = request.args.get("product_id")
    
    query = CommissionRule.query.filter_by(user_id=current_user.id)
    if company_id:
        query = query.filter_by(company_id=company_id)
    if product_id:
        query = query.filter_by(product_id=product_id)
    
    rules = query.all()
    return jsonify({
        "rules": [{
            "id": r.id,
            "company_id": r.company_id,
            "company_name": r.company.name,
            "product_id": r.product_id,
            "product_name": r.product.product_name,
            "commission_percentage": r.commission_percentage,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat()
        } for r in rules]
    }), 200


@api_bp.route("/commission-rules", methods=["POST"])
@login_required
def add_commission_rule():
    """Add commission rule for company + product combination"""
    data = request.get_json()
    
    # Check if rule already exists
    existing = CommissionRule.query.filter_by(
        user_id=current_user.id,
        company_id=data.get("company_id"),
        product_id=data.get("product_id")
    ).first()
    
    if existing:
        return jsonify({"error": "Commission rule already exists for this company + product"}), 400
    
    rule = CommissionRule(
        user_id=current_user.id,
        company_id=data.get("company_id"),
        product_id=data.get("product_id"),
        commission_percentage=data.get("commission_percentage")
    )
    
    db.session.add(rule)
    db.session.commit()
    
    return jsonify({
        "message": "Commission rule added successfully",
        "rule_id": rule.id
    }), 201


@api_bp.route("/commission-rules/<int:rule_id>", methods=["PUT"])
@login_required
def update_commission_rule(rule_id):
    """Update a commission rule"""
    rule = CommissionRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if not rule:
        return jsonify({"error": "Commission rule not found"}), 404
    
    data = request.get_json()
    rule.commission_percentage = data.get("commission_percentage", rule.commission_percentage)
    rule.is_active = data.get("is_active", rule.is_active)
    rule.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Commission rule updated successfully"}), 200


@api_bp.route("/commission-rules/<int:rule_id>", methods=["DELETE"])
@login_required
def delete_commission_rule(rule_id):
    """Delete a commission rule"""
    rule = CommissionRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if not rule:
        return jsonify({"error": "Commission rule not found"}), 404
    
    db.session.delete(rule)
    db.session.commit()
    return jsonify({"message": "Commission rule deleted successfully"}), 200


# ==================== POLICY MANAGEMENT ====================

@api_bp.route("/policies", methods=["GET"])
@login_required
def get_policies():
    """Get all policies for current user"""
    policies = Policy.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "policies": [{
            "id": p.id,
            "policy_number": p.policy_number,
            "client_id": p.client_id,
            "client_name": p.client.name,
            "company_id": p.company_id,
            "company_name": p.company.name,
            "product_id": p.product_id,
            "product_name": p.product.product_name,
            "premium_amount": p.premium_amount,
            "premium_frequency": p.premium_frequency,
            "start_date": p.start_date.isoformat(),
            "end_date": p.end_date.isoformat(),
            "status": p.status,
            "created_at": p.created_at.isoformat()
        } for p in policies]
    }), 200


@api_bp.route("/policies", methods=["POST"])
@login_required
def add_policy():
    """Add a policy"""
    data = request.get_json()
    
    policy = Policy(
        user_id=current_user.id,
        client_id=data.get("client_id"),
        company_id=data.get("company_id"),
        product_id=data.get("product_id"),
        policy_number=data.get("policy_number"),
        premium_amount=data.get("premium_amount"),
        premium_frequency=data.get("premium_frequency", "annual"),
        start_date=datetime.fromisoformat(data.get("start_date")).date(),
        end_date=datetime.fromisoformat(data.get("end_date")).date(),
        status=data.get("status", "active")
    )
    
    db.session.add(policy)
    db.session.commit()
    
    return jsonify({
        "message": "Policy added successfully",
        "policy_id": policy.id
    }), 201


@api_bp.route("/policies/<int:policy_id>", methods=["PUT"])
@login_required
def update_policy(policy_id):
    """Update a policy"""
    policy = Policy.query.filter_by(id=policy_id, user_id=current_user.id).first()
    if not policy:
        return jsonify({"error": "Policy not found"}), 404
    
    data = request.get_json()
    policy.policy_number = data.get("policy_number", policy.policy_number)
    policy.premium_amount = data.get("premium_amount", policy.premium_amount)
    policy.premium_frequency = data.get("premium_frequency", policy.premium_frequency)
    if "start_date" in data:
        policy.start_date = datetime.fromisoformat(data.get("start_date")).date()
    if "end_date" in data:
        policy.end_date = datetime.fromisoformat(data.get("end_date")).date()
    policy.status = data.get("status", policy.status)
    policy.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Policy updated successfully"}), 200


@api_bp.route("/policies/<int:policy_id>", methods=["DELETE"])
@login_required
def delete_policy(policy_id):
    """Delete a policy"""
    policy = Policy.query.filter_by(id=policy_id, user_id=current_user.id).first()
    if not policy:
        return jsonify({"error": "Policy not found"}), 404
    
    db.session.delete(policy)
    db.session.commit()
    return jsonify({"message": "Policy deleted successfully"}), 200


@api_bp.route("/policies/bulk-upload", methods=["POST"])
@login_required
def bulk_upload_policies():
    """Bulk upload policies from Excel file"""
    try:
        import pandas as pd
        
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        
        # Read Excel file
        df = pd.read_excel(file)
        
        # Expected columns: policy_number, client_id, company_id, product_id, premium_amount, start_date, end_date
        required_columns = ["policy_number", "client_id", "company_id", "product_id", "premium_amount", "start_date", "end_date"]
        if not all(col in df.columns for col in required_columns):
            return jsonify({"error": f"Missing required columns: {required_columns}"}), 400
        
        added_count = 0
        for _, row in df.iterrows():
            policy = Policy(
                user_id=current_user.id,
                policy_number=row.get("policy_number"),
                client_id=int(row.get("client_id")),
                company_id=int(row.get("company_id")),
                product_id=int(row.get("product_id")),
                premium_amount=float(row.get("premium_amount")),
                start_date=pd.to_datetime(row.get("start_date")).date(),
                end_date=pd.to_datetime(row.get("end_date")).date(),
                premium_frequency=row.get("premium_frequency", "annual"),
                status=row.get("status", "active")
            )
            db.session.add(policy)
            added_count += 1
        
        db.session.commit()
        return jsonify({
            "message": f"Successfully added {added_count} policies",
            "count": added_count
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ==================== PREMIUM REMITTANCE ====================

@api_bp.route("/remittance", methods=["GET"])
@login_required
def get_remittances():
    """Get all premium remittance records for current user"""
    remittances = PremiumRemittance.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "remittances": [{
            "id": r.id,
            "client_id": r.client_id,
            "client_name": r.client.name,
            "policy_id": r.policy_id,
            "policy_number": r.policy.policy_number,
            "amount": r.amount,
            "payment_method": r.payment_method,
            "reference_number": r.reference_number,
            "payment_date": r.payment_date.isoformat(),
            "status": r.status,
            "commission_calculated": r.commission_calculated,
            "created_at": r.created_at.isoformat()
        } for r in remittances]
    }), 200


@api_bp.route("/remittance", methods=["POST"])
@login_required
def add_remittance():
    """Record a premium payment (remittance)"""
    data = request.get_json()
    
    policy = Policy.query.filter_by(id=data.get("policy_id"), user_id=current_user.id).first()
    if not policy:
        return jsonify({"error": "Policy not found"}), 404
    
    # Calculate commission
    commission = policy.calculate_commission(float(data.get("amount")))
    
    remittance = PremiumRemittance(
        user_id=current_user.id,
        client_id=data.get("client_id"),
        policy_id=data.get("policy_id"),
        payment_method=data.get("payment_method"),  # bank_transfer, cash, mobile_money
        amount=float(data.get("amount")),
        reference_number=data.get("reference_number"),
        payment_date=datetime.fromisoformat(data.get("payment_date")).date(),
        status=data.get("status", "pending"),
        commission_calculated=commission
    )
    
    db.session.add(remittance)
    db.session.commit()
    
    return jsonify({
        "message": "Remittance recorded successfully",
        "remittance_id": remittance.id,
        "commission_calculated": commission
    }), 201


@api_bp.route("/remittance/<int:remittance_id>", methods=["PUT"])
@login_required
def update_remittance(remittance_id):
    """Update a remittance record"""
    remittance = PremiumRemittance.query.filter_by(id=remittance_id, user_id=current_user.id).first()
    if not remittance:
        return jsonify({"error": "Remittance not found"}), 404
    
    data = request.get_json()
    remittance.amount = data.get("amount", remittance.amount)
    remittance.payment_method = data.get("payment_method", remittance.payment_method)
    remittance.reference_number = data.get("reference_number", remittance.reference_number)
    remittance.status = data.get("status", remittance.status)
    
    # Recalculate commission if amount changed
    if "amount" in data:
        remittance.commission_calculated = remittance.policy.calculate_commission(float(data.get("amount")))
    
    remittance.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({"message": "Remittance updated successfully"}), 200


@api_bp.route("/remittance/<int:remittance_id>", methods=["DELETE"])
@login_required
def delete_remittance(remittance_id):
    """Delete a remittance record"""
    remittance = PremiumRemittance.query.filter_by(id=remittance_id, user_id=current_user.id).first()
    if not remittance:
        return jsonify({"error": "Remittance not found"}), 404
    
    db.session.delete(remittance)
    db.session.commit()
    return jsonify({"message": "Remittance deleted successfully"}), 200


# ==================== EXPORT/IMPORT ====================

@api_bp.route("/export/clients", methods=["GET"])
@login_required
def export_clients():
    """Export clients in various formats"""
    try:
        import pandas as pd
        from io import BytesIO
        
        format_type = request.args.get("format", "excel")  # excel, csv, json
        
        clients = Client.query.filter_by(user_id=current_user.id).all()
        
        data = [{
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "address": c.address,
            "identification_type": c.identification_type,
            "identification_number": c.identification_number,
            "created_at": c.created_at.isoformat()
        } for c in clients]
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        if format_type == "excel":
            df.to_excel(output, index=False, sheet_name="Clients")
            output.seek(0)
            return output.getvalue()
        elif format_type == "csv":
            output.write(df.to_csv(index=False).encode())
            output.seek(0)
            return output.getvalue()
        else:
            return jsonify(data), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@api_bp.route("/export/policies", methods=["GET"])
@login_required
def export_policies():
    """Export policies in various formats"""
    try:
        import pandas as pd
        from io import BytesIO
        
        format_type = request.args.get("format", "excel")  # excel, csv, json
        
        policies = Policy.query.filter_by(user_id=current_user.id).all()
        
        data = [{
            "policy_number": p.policy_number,
            "client_name": p.client.name,
            "company_name": p.company.name,
            "product_name": p.product.product_name,
            "premium_amount": p.premium_amount,
            "premium_frequency": p.premium_frequency,
            "start_date": p.start_date.isoformat(),
            "end_date": p.end_date.isoformat(),
            "status": p.status,
            "created_at": p.created_at.isoformat()
        } for p in policies]
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        if format_type == "excel":
            df.to_excel(output, index=False, sheet_name="Policies")
            output.seek(0)
            return output.getvalue()
        elif format_type == "csv":
            output.write(df.to_csv(index=False).encode())
            output.seek(0)
            return output.getvalue()
        else:
            return jsonify(data), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@api_bp.route("/export/remittance", methods=["GET"])
@login_required
def export_remittance():
    """Export remittance records in various formats"""
    try:
        import pandas as pd
        from io import BytesIO
        
        format_type = request.args.get("format", "excel")  # excel, csv, json
        
        remittances = PremiumRemittance.query.filter_by(user_id=current_user.id).all()
        
        data = [{
            "client_name": r.client.name,
            "policy_number": r.policy.policy_number,
            "amount": r.amount,
            "payment_method": r.payment_method,
            "reference_number": r.reference_number,
            "payment_date": r.payment_date.isoformat(),
            "status": r.status,
            "commission_calculated": r.commission_calculated,
            "created_at": r.created_at.isoformat()
        } for r in remittances]
        
        df = pd.DataFrame(data)
        
        output = BytesIO()
        if format_type == "excel":
            df.to_excel(output, index=False, sheet_name="Remittances")
            output.seek(0)
            return output.getvalue()
        elif format_type == "csv":
            output.write(df.to_csv(index=False).encode())
            output.seek(0)
            return output.getvalue()
        else:
            return jsonify(data), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

