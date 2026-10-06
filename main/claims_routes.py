"""Claims management routes for the ERP system."""
from pathlib import Path
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .models import db, Claim, ClaimDocument, Policy, Client, ROLE_OWNER, ROLE_ADMIN
from .utils import role_required, get_account_owner_id, generate_policy_number

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"


def register_claims_routes(core_bp):
    """Register all claims-related routes with the core blueprint."""
    
    @core_bp.route("/claims")
    @login_required
    @role_required(ROLE_OWNER, ROLE_ADMIN)
    def claims():
        """Display all claims dashboard."""
        try:
            claims_list = Claim.query.filter_by(owner_id=get_account_owner_id()).all()
            status_filter = request.args.get('status')
            if status_filter:
                claims_list = [c for c in claims_list if c.status == status_filter]
        except Exception as e:
            flash(f"Error loading claims: {str(e)}", "danger")
            claims_list = []
        
        return render_template("claims.html", claims=claims_list)

    @core_bp.route("/claims/register", methods=["GET", "POST"])
    @login_required
    @role_required(ROLE_OWNER, ROLE_ADMIN)
    def register_claim():
        """Register a new claim."""
        if request.method == "POST":
            try:
                policy_id = request.form.get("policy_id", type=int)
                policy = Policy.query.filter_by(
                    id=policy_id, 
                    owner_id=get_account_owner_id()
                ).first()
                
                if not policy:
                    flash("Invalid policy selected.", "danger")
                    policies = Policy.query.filter_by(owner_id=get_account_owner_id()).all()
                    return render_template("register_claim.html", policies=policies)
                
                # Generate unique claim number
                claim_number = f"CLM-{datetime.utcnow().strftime('%Y%m%d')}-{generate_policy_number()[-6:]}"
                
                loss_date_str = request.form.get("loss_date")
                claim_date_str = request.form.get("claim_date")
                
                claim = Claim(
                    owner_id=get_account_owner_id(),
                    policy_id=policy_id,
                    client_id=policy.client_id,
                    claim_number=claim_number,
                    description=request.form.get("description", "").strip(),
                    loss_date=datetime.strptime(loss_date_str, "%Y-%m-%d").date() if loss_date_str else datetime.now().date(),
                    claim_date=datetime.strptime(claim_date_str, "%Y-%m-%d").date() if claim_date_str else datetime.now().date(),
                    claimed_amount=float(request.form.get("claimed_amount", 0)),
                    priority=request.form.get("priority", "normal"),
                    status="pending"
                )
                
                db.session.add(claim)
                db.session.flush()
                
                # Handle document uploads
                if "documents" in request.files:
                    files = request.files.getlist("documents")
                    for file in files:
                        if file and file.filename:
                            filename = secure_filename(file.filename)
                            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                            unique_filename = f"{timestamp}_{filename}"
                            upload_path = UPLOAD_FOLDER / "claims" / unique_filename
                            upload_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            file_content = file.read()
                            file.seek(0)
                            file.save(upload_path)
                            
                            file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"
                            
                            doc = ClaimDocument(
                                claim_id=claim.id,
                                owner_id=get_account_owner_id(),
                                file_name=filename,
                                file_path=str(upload_path.relative_to(BASE_DIR)),
                                file_size=len(file_content),
                                file_type=file_type,
                                description=request.form.get(f"doc_description_{file.filename}", ""),
                                uploaded_by_id=current_user.id
                            )
                            db.session.add(doc)
                
                db.session.commit()
                flash(f"Claim {claim_number} registered successfully.", "success")
                return redirect(url_for("core.claims"))
                
            except Exception as e:
                db.session.rollback()
                flash(f"Error registering claim: {str(e)}", "danger")
                policies = Policy.query.filter_by(owner_id=get_account_owner_id()).all()
                return render_template("register_claim.html", policies=policies)
        
        policies = Policy.query.filter_by(owner_id=get_account_owner_id()).all()
        return render_template("register_claim.html", policies=policies)

    @core_bp.route("/claims/<int:claim_id>/detail")
    @login_required
    @role_required(ROLE_OWNER, ROLE_ADMIN)
    def claim_detail(claim_id):
        """View claim details and tracking."""
        claim = Claim.query.filter_by(
            id=claim_id,
            owner_id=get_account_owner_id()
        ).first_or_404()
        
        documents = ClaimDocument.query.filter_by(claim_id=claim_id).all()
        return render_template("claim_detail.html", claim=claim, documents=documents)

    @core_bp.route("/claims/<int:claim_id>/update-status", methods=["POST"])
    @login_required
    @role_required(ROLE_OWNER, ROLE_ADMIN)
    def update_claim_status(claim_id):
        """Update claim status via AJAX."""
        claim = Claim.query.filter_by(
            id=claim_id,
            owner_id=get_account_owner_id()
        ).first_or_404()
        
        try:
            status = request.form.get("status", "").strip()
            approved_amount = request.form.get("approved_amount", "0")
            
            valid_statuses = ["pending", "under_review", "approved", "denied", "paid"]
            if status not in valid_statuses:
                return jsonify({"error": "Invalid status"}), 400
            
            claim.status = status
            if status == "approved":
                try:
                    claim.approved_amount = float(approved_amount)
                except ValueError:
                    claim.approved_amount = 0.0
            
            db.session.commit()
            flash("Claim status updated successfully.", "success")
            return jsonify({"success": True, "message": "Claim status updated"})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @core_bp.route("/claims/<int:claim_id>/document/add", methods=["POST"])
    @login_required
    @role_required(ROLE_OWNER, ROLE_ADMIN)
    def add_claim_document(claim_id):
        """Add document to claim via AJAX."""
        claim = Claim.query.filter_by(
            id=claim_id,
            owner_id=get_account_owner_id()
        ).first_or_404()
        
        try:
            if "document" not in request.files:
                return jsonify({"error": "No file provided"}), 400
            
            file = request.files["document"]
            if not file or not file.filename:
                return jsonify({"error": "No file selected"}), 400
            
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            upload_path = UPLOAD_FOLDER / "claims" / unique_filename
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_content = file.read()
            file.seek(0)
            file.save(upload_path)
            
            file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"
            
            doc = ClaimDocument(
                claim_id=claim_id,
                owner_id=get_account_owner_id(),
                file_name=filename,
                file_path=str(upload_path.relative_to(BASE_DIR)),
                file_size=len(file_content),
                file_type=file_type,
                description=request.form.get("description", ""),
                uploaded_by_id=current_user.id
            )
            
            db.session.add(doc)
            db.session.commit()
            return jsonify({"success": True, "message": "Document added successfully"})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @core_bp.route("/claims/documents/<int:doc_id>/download")
    @login_required
    def download_claim_document(doc_id):
        """Download claim document."""
        doc = ClaimDocument.query.get_or_404(doc_id)
        
        if doc.owner_id != get_account_owner_id():
            flash("Access denied", "danger")
            return redirect(url_for("core.claims"))
        
        try:
            file_path = BASE_DIR / doc.file_path
            if not file_path.exists():
                flash("File not found", "danger")
                return redirect(url_for("core.claim_detail", claim_id=doc.claim_id))
            return send_file(file_path, as_attachment=True, download_name=doc.file_name)
        except Exception as e:
            flash(f"Error downloading document: {str(e)}", "danger")
            return redirect(url_for("core.claim_detail", claim_id=doc.claim_id))

    @core_bp.route("/claims/documents/<int:doc_id>/delete", methods=["POST"])
    @login_required
    def delete_claim_document(doc_id):
        """Delete claim document."""
        doc = ClaimDocument.query.get_or_404(doc_id)
        claim = doc.claim_ref
        
        if claim.owner_id != get_account_owner_id():
            flash("Access denied", "danger")
            return redirect(url_for("core.claims"))
        
        try:
            import os
            file_path = BASE_DIR / doc.file_path
            if file_path.exists():
                os.remove(file_path)
            
            db.session.delete(doc)
            db.session.commit()
            flash("Document deleted successfully", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting document: {str(e)}", "danger")
        
        return redirect(url_for("core.claim_detail", claim_id=claim.id))

    @core_bp.route("/api/global-search")
    @login_required
    def global_search():
        """Global search API endpoint across clients, policies, and claims."""
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 2:
            return jsonify([])
        
        owner_id = get_account_owner_id()
        results = []
        
        try:
            # Search clients by name, email, phone
            clients = Client.query.filter_by(owner_id=owner_id).filter(
                db.or_(
                    Client.first_name.ilike(f"%{query}%"),
                    Client.last_name.ilike(f"%{query}%"),
                    Client.email.ilike(f"%{query}%"),
                    Client.phone.ilike(f"%{query}%")
                )
            ).limit(5).all()
            
            for client in clients:
                results.append({
                    "type": "client",
                    "id": client.id,
                    "title": f"{client.first_name} {client.last_name}",
                    "subtitle": client.email or client.phone or "No contact",
                    "icon": "fa-user",
                    "url": url_for("core.clients")
                })
            
            # Search policies by policy number
            policies = Policy.query.filter_by(owner_id=owner_id).filter(
                Policy.policy_number.ilike(f"%{query}%")
            ).limit(5).all()
            
            for policy in policies:
                client_name = f"{policy.client.first_name} {policy.client.last_name}" if policy.client else "Unknown"
                results.append({
                    "type": "policy",
                    "id": policy.id,
                    "title": f"Policy {policy.policy_number}",
                    "subtitle": client_name,
                    "icon": "fa-file-contract",
                    "url": url_for("core.policy_detail", policy_id=policy.id) if hasattr(url_for, '__call__') else "#"
                })
            
            # Search claims by claim number
            claims_list = Claim.query.filter_by(owner_id=owner_id).filter(
                Claim.claim_number.ilike(f"%{query}%")
            ).limit(5).all()
            
            for claim in claims_list:
                client_name = f"{claim.client_ref.first_name} {claim.client_ref.last_name}" if claim.client_ref else "Unknown"
                results.append({
                    "type": "claim",
                    "id": claim.id,
                    "title": f"Claim {claim.claim_number}",
                    "subtitle": client_name,
                    "icon": "fa-file-invoice",
                    "url": url_for("core.claim_detail", claim_id=claim.id) if hasattr(url_for, '__call__') else "#"
                })
        
        except Exception as e:
            pass
        
        return jsonify(results[:10])

