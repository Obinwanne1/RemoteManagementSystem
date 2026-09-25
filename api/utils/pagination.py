"""Shared pagination helper for list endpoints.

Centralizes the page/per_page parse-clamp-paginate-serialize sequence that
was previously hand-rolled at 12 call sites across 9 route files (alerts.py,
automation.py, customers.py, devices.py, patches.py, scripts.py, tickets.py,
admin.py, usage.py) — see audits/code_duplication_audit.md Finding N2 for the
3 observed inconsistencies this was causing (a "pages" key present in only
2 of 12 responses, admin.py using "users" instead of "items", and
customers.py using different per_page default/cap than everywhere else).

Not yet wired into any route — apply to one file at a time per CLAUDE.md's
"one bug fix at a time, verified before moving on" convention. Swapping a
call site in changes its response to always include "pages" (additive for
the 10 sites that currently omit it); renaming admin.py's "users" key to
"items" is a separate, deliberate breaking change — don't bundle it with
the additive rollout.
"""
from flask import request, jsonify


def paginated_response(query, serialize, *, order_by=None,
                        default_per_page=50, max_per_page=200, items_key="items"):
    """Parse ?page/?per_page from the current request, paginate `query`,
    and return a ready-to-return (body, 200) tuple.

    `serialize` maps one row to a dict, e.g. `lambda r: r.to_dict()`.
    `order_by` is optional — pass a model column/expression if the caller
    hasn't already ordered the query itself.
    """
    if order_by is not None:
        query = query.order_by(order_by)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", default_per_page, type=int), max_per_page)
    paginated = query.paginate(page=page, per_page=per_page)
    return jsonify({
        items_key: [serialize(r) for r in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200
