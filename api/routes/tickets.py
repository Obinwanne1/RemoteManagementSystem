from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from extensions import db, limiter
from models.ticket import Ticket, TicketComment
from models.user import User
from models.audit import AuditLog
from utils.validation import validate_body
from utils.auth_decorators import require_role as _require_role
from utils.scope import require_customer_scope
from utils.pagination import paginated_response
from services.ticket_service import _customer_name
from schemas.tickets import TicketCreateSchema, TicketUpdateSchema, CommentCreateSchema
from utils.notifications import (
    send_ticket_assigned,
    send_ticket_resolved_client,
    send_ticket_comment_to_client,
    send_ticket_comment_to_assignee,
)

tickets_bp = Blueprint("tickets", __name__)


def _current_claims():
    return get_jwt()


def _get_client_emails(customer_id: str) -> list:
    """Return emails of active client-role users linked to this customer."""
    clients = User.query.filter_by(role="client", customer_id=customer_id, is_active=True).all()
    return [u.email for u in clients if u.email]


def _ticket_audit(action: str, user_id: str, ticket_id: str, payload: dict = None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type="ticket",
        resource_id=ticket_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
        payload=payload,
    )
    db.session.add(log)


@tickets_bp.route("/", methods=["GET"])
@jwt_required()
def list_tickets():
    claims = _current_claims()
    role = claims.get("role")
    uid = get_jwt_identity()

    page = request.args.get("page", 1, type=int)
    status = request.args.get("status")
    priority = request.args.get("priority")
    customer_id = request.args.get("customer_id")
    assignee_id = request.args.get("assignee_id")
    department_id = request.args.get("department_id")

    query = Ticket.query

    # Client users see only their own customer's tickets
    if role == "client":
        user = db.session.get(User, uid)
        if not user or not user.customer_id:
            return jsonify({"items": [], "total": 0, "page": page, "pages": 0}), 200
        query = query.filter_by(customer_id=user.customer_id)
    else:
        if customer_id:
            query = query.filter_by(customer_id=customer_id)

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if assignee_id:
        query = query.filter_by(assignee_id=assignee_id)
    if department_id:
        query = query.filter_by(department_id=department_id)

    return paginated_response(query, lambda t: t.to_dict(), order_by=Ticket.created_at.desc())


@tickets_bp.route("/", methods=["POST"])
@jwt_required()
@limiter.limit("20 per minute")
@validate_body(TicketCreateSchema)
def create_ticket():
    from services.ticket_service import create_ticket_service
    claims = _current_claims()
    role = claims.get("role")
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    actor_customer_id = None
    if role == "client":
        user = db.session.get(User, uid)
        actor_customer_id = user.customer_id if user else None

    result, err = create_ticket_service(
        uid, role, actor_customer_id,
        title=data.get("title"), description=data.get("description"),
        customer_id=data.get("customer_id"), device_id=data.get("device_id"),
        assignee_id=data.get("assignee_id"), priority=data.get("priority", "medium"),
        status=data.get("status", "open"), alert_id=data.get("alert_id"),
        department_id=data.get("department_id"), tags=data.get("tags", []),
        due_date=data.get("due_date"), source=data.get("source", "manual"),
    )
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(result), 201


@tickets_bp.route("/<ticket_id>", methods=["GET"])
@jwt_required()
def get_ticket(ticket_id):
    ticket = db.get_or_404(Ticket, ticket_id)

    err = require_customer_scope(ticket.customer_id)
    if err:
        return err

    return jsonify(ticket.to_dict(include_comments=True)), 200


@tickets_bp.route("/<ticket_id>", methods=["PUT"])
@jwt_required()
@validate_body(TicketUpdateSchema)
def update_ticket(ticket_id):
    claims = _current_claims()
    role = claims.get("role")
    uid = get_jwt_identity()

    ticket = db.get_or_404(Ticket, ticket_id)

    # Clients cannot update tickets (read + create + comment only)
    if role == "client":
        return jsonify({"error": "Insufficient permissions"}), 403

    data = request.get_json(silent=True) or {}
    old_assignee_id = ticket.assignee_id
    old_status = ticket.status

    # Require a comment whenever the status is being changed
    new_status = data.get("status")
    if new_status and new_status != old_status:
        status_comment = (data.get("status_comment") or "").strip()
        if not status_comment:
            return jsonify({
                "error": f"A comment is required when changing status from '{old_status}' to '{new_status}'."
            }), 400

    tracked = ["title", "description", "assignee_id", "department_id", "priority", "status", "due_date", "tags"]
    changes = {f: {"from": getattr(ticket, f), "to": data[f]} for f in tracked if f in data and data[f] != getattr(ticket, f)}

    for field in tracked:
        if field in data:
            setattr(ticket, field, data[field])
    if data.get("status") in ("resolved", "closed") and not ticket.resolved_at:
        ticket.resolved_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    _ticket_audit("UPDATE", uid, ticket_id, {"changes": changes})

    # Auto-post the status change comment so the thread stays conversational
    if new_status and new_status != old_status:
        status_comment_body = (
            f"[Status changed: {old_status.replace('_', ' ')} → {new_status.replace('_', ' ')}]\n\n"
            + status_comment
        )
        auto_comment = TicketComment(
            ticket_id=ticket_id,
            author_id=uid,
            body=status_comment_body,
            is_internal=False,
        )
        db.session.add(auto_comment)
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

    db.session.commit()

    try:
        new_assignee_id = data.get("assignee_id")
        if new_assignee_id and new_assignee_id != old_assignee_id:
            assignee = db.session.get(User, new_assignee_id)
            if assignee and assignee.email:
                send_ticket_assigned(ticket.title, ticket.id, _customer_name(ticket.customer_id),
                                     ticket.priority, assignee.email)
        new_status = data.get("status")
        if new_status in ("resolved", "closed") and old_status not in ("resolved", "closed"):
            client_emails = _get_client_emails(ticket.customer_id)
            send_ticket_resolved_client(ticket.title, ticket.id, client_emails, ticket.requester_email)
    except Exception:
        current_app.logger.warning("Ticket update notification failed for ticket %s", ticket.id, exc_info=True)

    return jsonify(ticket.to_dict()), 200


@tickets_bp.route("/<ticket_id>", methods=["DELETE"])
@jwt_required()
def delete_ticket(ticket_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    uid = get_jwt_identity()
    ticket = db.get_or_404(Ticket, ticket_id)
    _ticket_audit("DELETE", uid, ticket_id, {"title": ticket.title})
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({"message": "Ticket deleted"}), 200


@tickets_bp.route("/<ticket_id>/comments", methods=["POST"])
@jwt_required()
@validate_body(CommentCreateSchema)
def add_comment(ticket_id):
    claims = _current_claims()
    role = claims.get("role")
    uid = get_jwt_identity()

    ticket = db.get_or_404(Ticket, ticket_id)

    err = require_customer_scope(ticket.customer_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    if not data.get("body"):
        return jsonify({"error": "body required"}), 400

    # Clients cannot post internal notes
    is_internal = data.get("is_internal", False) if role != "client" else False

    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=uid,
        body=data["body"],
        is_internal=is_internal,
    )
    db.session.add(comment)
    # Record first staff response time (non-client, non-internal)
    if role != "client" and not is_internal and not ticket.first_response_at:
        ticket.first_response_at = datetime.now(timezone.utc)
    _ticket_audit("COMMENT", uid, ticket_id, {"is_internal": is_internal, "preview": data["body"][:120]})
    db.session.commit()

    try:
        if not is_internal:
            if role == "client":
                if ticket.assignee_id:
                    assignee = db.session.get(User, ticket.assignee_id)
                    if assignee and assignee.email:
                        send_ticket_comment_to_assignee(ticket.title, ticket.id, data["body"], assignee.email)
            else:
                client_emails = _get_client_emails(ticket.customer_id)
                send_ticket_comment_to_client(
                    ticket.title, ticket.id, data["body"],
                    client_emails, ticket.requester_email,
                )
    except Exception:
        current_app.logger.warning("Comment notification failed for ticket %s", ticket.id, exc_info=True)

    return jsonify(comment.to_dict()), 201


@tickets_bp.route("/<ticket_id>/comments/<comment_id>", methods=["DELETE"])
@jwt_required()
def delete_comment(ticket_id, comment_id):
    uid = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")
    comment = TicketComment.query.filter_by(
        id=comment_id, ticket_id=ticket_id
    ).first_or_404()
    if role not in ("admin", "superadmin") and comment.author_id != uid:
        return jsonify({"error": "Cannot delete another user's comment"}), 403
    _ticket_audit("DELETE_COMMENT", uid, ticket_id, {"comment_id": comment_id})
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"message": "Comment deleted"}), 200
