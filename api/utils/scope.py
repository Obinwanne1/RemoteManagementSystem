"""Shared tenant-isolation (cross-customer scope) check.

Centralizes the client-role ownership check that was previously duplicated
as devices.py::_client_scope_check and mobile_mdm.py::_mdm_scope_check (the
latter's own docstring notes it was hand-copied "after the cross-tenant leak
fixed in 4d4362a" — i.e. this exact duplication is what caused a real prior
security incident). One function to audit for the next cross-tenant fix,
instead of N drifting copies.
"""
from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity

from extensions import db
from models.user import User


def require_customer_scope(customer_id, not_found_message="Not found"):
    """Returns a (body, 404) tuple if the caller is a client-role JWT that does
    not own `customer_id`, else None. Non-client roles are unrestricted here
    (their access is governed by require_role() instead)."""
    claims = get_jwt()
    if claims.get("role") != "client":
        return None
    uid = get_jwt_identity()
    user = db.session.get(User, uid)
    if not user or customer_id != user.customer_id:
        return jsonify({"error": not_found_message}), 404
    return None
