from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from extensions import db
from models.report import Report

reports_bp = Blueprint("reports", __name__)

# Superadmin-only report type — same restriction as /api/admin/usage/*, since it
# surfaces the same API/token usage data that regular admins must not see.
_SUPERADMIN_ONLY_TEMPLATES = ("api_usage",)


@reports_bp.route("/templates", methods=["GET"])
@jwt_required()
def list_templates():
    templates = [
        {"type": "patch_summary", "name": "Patch Summary Report"},
        {"type": "device_health", "name": "Device Health Report"},
        {"type": "ticket_summary", "name": "Ticket Summary Report"},
        {"type": "software_inventory", "name": "Software Inventory Report"},
        {"type": "billing", "name": "Billing Report"},
    ]
    if get_jwt().get("role") == "superadmin":
        templates.append({"type": "api_usage", "name": "API & Token Usage Report"})
    return jsonify(templates), 200


@reports_bp.route("/", methods=["GET"])
@jwt_required()
def list_reports():
    is_superadmin = get_jwt().get("role") == "superadmin"
    q = Report.query
    if not is_superadmin:
        q = q.filter(Report.template_type.notin_(_SUPERADMIN_ONLY_TEMPLATES))
    reports = q.order_by(Report.generated_at.desc()).limit(100).all()
    return jsonify([r.to_dict() for r in reports]), 200


@reports_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate_report():
    data = request.get_json(silent=True) or {}
    template_type = data.get("template_type")
    if not template_type:
        return jsonify({"error": "template_type required"}), 400
    if template_type in _SUPERADMIN_ONLY_TEMPLATES and get_jwt().get("role") != "superadmin":
        return jsonify({"error": "Super Administrator access required"}), 403

    report = Report(
        name=data.get("name", f"{template_type} report"),
        template_type=template_type,
        customer_id=data.get("customer_id"),
        format=data.get("format", "pdf"),
        parameters=data.get("parameters", {}),
        generated_by=get_jwt_identity(),
    )
    db.session.add(report)
    db.session.commit()
    from tasks.report_tasks import generate_report as gen_task
    gen_task.delay(report.id)
    return jsonify({"message": "Report queued", "report_id": report.id}), 202


@reports_bp.route("/<report_id>", methods=["GET"])
@jwt_required()
def get_report(report_id):
    report = db.get_or_404(Report, report_id)
    if report.template_type in _SUPERADMIN_ONLY_TEMPLATES and get_jwt().get("role") != "superadmin":
        return jsonify({"error": "Super Administrator access required"}), 403
    return jsonify(report.to_dict()), 200
