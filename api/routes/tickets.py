from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from extensions import db
from models.ticket import Ticket, TicketComment

tickets_bp = Blueprint("tickets", __name__)


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") == "superadmin":
        return None  # superadmin bypasses all role checks
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


@tickets_bp.route("/", methods=["GET"])
@jwt_required()
def list_tickets():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    status = request.args.get("status")
    priority = request.args.get("priority")
    customer_id = request.args.get("customer_id")
    assignee_id = request.args.get("assignee_id")

    query = Ticket.query
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    if assignee_id:
        query = query.filter_by(assignee_id=assignee_id)

    paginated = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        "items": [t.to_dict() for t in paginated.items],
        "total": paginated.total,
        "page": page,
    }), 200


@tickets_bp.route("/", methods=["POST"])
@jwt_required()
def create_ticket():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("customer_id"):
        return jsonify({"error": "title and customer_id required"}), 400
    ticket = Ticket(
        title=data["title"],
        description=data.get("description"),
        customer_id=data["customer_id"],
        device_id=data.get("device_id"),
        assignee_id=data.get("assignee_id"),
        priority=data.get("priority", "medium"),
        status=data.get("status", "open"),
        source=data.get("source", "manual"),
        alert_id=data.get("alert_id"),
        tags=data.get("tags", []),
    )
    db.session.add(ticket)
    db.session.commit()
    return jsonify(ticket.to_dict()), 201


@tickets_bp.route("/<ticket_id>", methods=["GET"])
@jwt_required()
def get_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    return jsonify(ticket.to_dict(include_comments=True)), 200


@tickets_bp.route("/<ticket_id>", methods=["PUT"])
@jwt_required()
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json(silent=True) or {}
    for field in ["title", "description", "assignee_id", "priority", "status", "tags"]:
        if field in data:
            setattr(ticket, field, data[field])
    if data.get("status") in ("resolved", "closed") and not ticket.resolved_at:
        ticket.resolved_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(ticket.to_dict()), 200


@tickets_bp.route("/<ticket_id>", methods=["DELETE"])
@jwt_required()
def delete_ticket(ticket_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    ticket = Ticket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({"message": "Ticket deleted"}), 200


@tickets_bp.route("/<ticket_id>/comments", methods=["POST"])
@jwt_required()
def add_comment(ticket_id):
    Ticket.query.get_or_404(ticket_id)
    data = request.get_json(silent=True) or {}
    if not data.get("body"):
        return jsonify({"error": "body required"}), 400
    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=get_jwt_identity(),
        body=data["body"],
        is_internal=data.get("is_internal", False),
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_dict()), 201


@tickets_bp.route("/<ticket_id>/comments/<comment_id>", methods=["DELETE"])
@jwt_required()
def delete_comment(ticket_id, comment_id):
    comment = TicketComment.query.filter_by(
        id=comment_id, ticket_id=ticket_id
    ).first_or_404()
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Comment deleted"}), 200
