from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from extensions import db
from models.billing import Invoice
from models.device import Device

billing_bp = Blueprint("billing", __name__)


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


@billing_bp.route("/invoices", methods=["GET"])
@jwt_required()
def list_invoices():
    customer_id = request.args.get("customer_id")
    query = Invoice.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    invoices = query.order_by(Invoice.created_at.desc()).limit(100).all()
    return jsonify([i.to_dict() for i in invoices]), 200


@billing_bp.route("/invoices/generate", methods=["POST"])
@jwt_required()
def generate_invoice():
    err = _require_role("admin")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400

    device_count = Device.query.filter_by(customer_id=customer_id).count()
    per_device_rate = float(data.get("per_device_rate", 15.00))
    subtotal = device_count * per_device_rate
    tax_rate = float(data.get("tax_rate", 0.0))
    tax = subtotal * tax_rate
    total = subtotal + tax

    invoice = Invoice(
        customer_id=customer_id,
        period_start=datetime.fromisoformat(data["period_start"]) if data.get("period_start") else datetime.now(timezone.utc),
        period_end=datetime.fromisoformat(data["period_end"]) if data.get("period_end") else datetime.now(timezone.utc),
        device_count=device_count,
        per_device_rate=per_device_rate,
        subtotal=subtotal,
        tax=tax,
        total=total,
        line_items=[
            {"description": f"Managed devices ({device_count} devices)", "amount": subtotal},
        ],
    )
    db.session.add(invoice)
    db.session.commit()
    return jsonify(invoice.to_dict()), 201


@billing_bp.route("/invoices/<invoice_id>", methods=["GET"])
@jwt_required()
def get_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return jsonify(invoice.to_dict()), 200


@billing_bp.route("/invoices/<invoice_id>/send", methods=["POST"])
@jwt_required()
def send_invoice(invoice_id):
    err = _require_role("admin")
    if err:
        return err
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.status = "sent"
    invoice.sent_at = datetime.now(timezone.utc)
    db.session.commit()
    # Phase 9: actual email sending
    return jsonify({"message": "Invoice marked as sent"}), 200
