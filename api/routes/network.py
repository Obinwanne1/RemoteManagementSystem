from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from extensions import db
from models.audit import NetworkScan

network_bp = Blueprint("network", __name__)


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


@network_bp.route("/scan", methods=["POST"])
@jwt_required()
def trigger_scan():
    err = _require_role("admin", "technician")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not data.get("customer_id") or not data.get("scan_range"):
        return jsonify({"error": "customer_id and scan_range required"}), 400

    scan = NetworkScan(
        customer_id=data["customer_id"],
        initiated_by=get_jwt_identity(),
        scan_range=data["scan_range"],
        status="running",
    )
    db.session.add(scan)
    db.session.commit()
    # Phase 9: actual scan via Celery
    return jsonify({"message": "Scan started", "scan_id": scan.id}), 202


@network_bp.route("/scans", methods=["GET"])
@jwt_required()
def list_scans():
    customer_id = request.args.get("customer_id")
    query = NetworkScan.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    scans = query.order_by(NetworkScan.started_at.desc()).limit(50).all()
    return jsonify([s.to_dict() for s in scans]), 200


@network_bp.route("/scans/<scan_id>", methods=["GET"])
@jwt_required()
def get_scan(scan_id):
    scan = NetworkScan.query.get_or_404(scan_id)
    return jsonify({
        **scan.to_dict(),
        "discovered_hosts": scan.discovered_hosts,
    }), 200
