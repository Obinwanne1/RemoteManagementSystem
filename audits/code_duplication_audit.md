# Code Duplication Audit — RMM System

**Date:** 2026-09-24
**Scope:** `api/`, `dashboard/`, `frontend/` (excluding `venv/`, `node_modules/`, `__pycache__/`, `dist/`). `agent/` was spot-checked; no findings worth reporting there.
**Method:** Static review of source, grep-verified occurrence counts, byte-level comparison of the actual duplicated snippets (not just "looks similar"). All findings are anchored to real file paths/line numbers found in the current tree. Items that could not be fully confirmed are marked **Unable to verify**.
**Relationship to prior audits:** `audits/design_patterns_audit.md` (2026-09-24) already found and *fixed* the largest duplication items in `api/` — `_require_role` (16 files → `utils/auth_decorators.py`), tenant-scope checks (`devices.py`/`mobile_mdm.py` → `utils/scope.py`), the Celery app singleton (16 files → `tasks/_app_singleton.py`), and the `online_devices()` query. Those are **not re-reported here**. This audit specifically hunts for what that pass didn't cover — two `require_role`-shaped checks it missed, `dashboard/` and `frontend/` (neither was in its remediation list), and DRY categories outside the Gang-of-Four lens that audit used (pagination boilerplate, schema duplication, frontend component duplication).

---

## Executive Summary

Ten findings, four of them backed by an actual observed inconsistency (not just "this could drift" — it already has). The standout: **`frontend/src/pages/TicketsPage.tsx` and `ClientPortalPage.tsx` both hardcode a `STATUS_BADGE` map for the same `Ticket.status` field, and they disagree** — `open` renders sky-blue to staff and red to the client viewing the identical ticket. That's not a style nit, it's a duplication bug a user can see.

| # | Finding | Category | Importance |
|---|---|---|---|
| 1 | `STATUS_BADGE.open` color differs between `TicketsPage.tsx` and `ClientPortalPage.tsx` — same field, same value, different UI meaning | Near Duplicate | **6/10** |
| 2 | Pagination parse/clamp/response-shape hand-rolled 12× across 9 route files, with 3 observable shape inconsistencies | Near Duplicate | **6/10** |
| 3 | `_require_admin()` independently reimplemented in `admin.py` and `org_settings.py`, missed by the sibling audit's `require_role()` consolidation | Near Duplicate | 5/10 |
| 4 | Frontend table skeleton-loading row is byte-identical JSX in 12 page files | Exact Duplicate | 5/10 |
| 5 | Marshmallow `*CreateSchema`/`*UpdateSchema` pairs hand-duplicate every field across 7 files instead of using `partial=True` | Near Duplicate | 4/10 |
| 6 | `"admin","technician","viewer","client"` role tuple hand-maintained under 2 different names in 3 files | Data Duplication | 4/10 |
| 7 | Frontend empty-state JSX shell duplicated across the same 12 pages as #4 | Exact Duplicate | 3/10 |
| 8 | `PLATFORM_ICON_HTML`-shaped dict independently defined in `04_Devices.py` and `07_Network_Discovery.py` | Exact Duplicate | 3/10 |
| 9 | `X.isoformat() if X else None` guard repeated 80× across 18 model files | Structural Duplicate | 3/10 |
| 10 | Dashboard page bootstrap (`set_page_config`+`inject_css`+`require_auth`+`render_sidebar`) repeated in 26 page files | Structural Duplicate | 2/10 |

A brand-color palette is also independently maintained in `dashboard/utils/styles.py` (Python dict) and `frontend/tailwind.config.js` (Tailwind scale) — flagged in the appendix, not scored, because it's cross-language config with no realistic single-source fix short of a design-token build step, and the two are not observed to have drifted.

---

## Remediation Status — 2026-09-24

Finding N2 was fixed and wired in the same day as this audit. Full API test suite: **149/149 passing**, plus a live smoke test against the running stack (real Postgres, a minted JWT per role) confirming every changed endpoint's actual HTTP response shape.

| Endpoint | Fix applied |
|---|---|
| `alerts.py::list_rules`, `automation.py::list_profiles`/`list_runs`, `customers.py::list_customers`/`list_groups`, `patches.py::list_patches`, `scripts.py::list_runs`, `tickets.py::list_tickets`, `admin.py::list_users` | Swapped to `paginated_response()` (new `api/utils/pagination.py`) — all 9 now return `items`/`total`/`page`/`pages` consistently. `customers.py::list_customers` keeps its distinct `default_per_page=20, max_per_page=100`. |
| `alerts.py::list_alerts`, `usage.py::events` | Left as hand-written (custom Redis raw-JSON caching / device-hostname enrichment doesn't fit the generic helper) — added the missing `"pages"` key inline instead. `usage.py` also kept its `"per_page"` field, which `frontend/src/api/usage.ts`'s response type expects and the generic helper doesn't produce. |
| `devices.py::list_devices` | No change — already included `"pages"`; the original grep that flagged 12 call sites without it missed this one because its response is built as a raw dict, not `jsonify({...})` immediately after `.paginate(`. |

**A real bug found and fixed during remediation, not in the original audit:** `admin.py::list_users`'s response key was `"users"`, but `frontend/src/pages/AdminPage.tsx:65` already reads `data?.items` — the React Admin page's user list has been silently rendering empty (and its pagination controls broken, since it also expects a `pages` field) since that page was written. Fixing N2 to use `"items"` consistently fixes this for free; also updated the 4 Streamlit call sites that read the old `"users"` key (`dashboard/pages/10_Admin.py:415,628`, `02_Tickets.py:241`, `_ticket_detail.py:140`) to read `"items"` instead. Verified no test or other consumer depended on the `"users"` key name (`grep` across `api/tests/`, `dashboard/`, `frontend/src/` before changing it).

**Not changed:** Findings E1-E3, N1, N3, N4, S1, S2, DD1 — each documented above with a ready-to-apply snippet, left for individual follow-up passes per CLAUDE.md's "one bug fix at a time, verified before moving on" (several need a product decision — e.g. N1's correct ticket-status color — that isn't this report's call to make).

---

## 1. Exact Duplicates

### Finding E1 — Frontend table skeleton-loading row, byte-identical across 12 files
- **Location:** `frontend/src/pages/AlertsPage.tsx:89-97`, `CustomersPage.tsx:77-85`, `AdminPage.tsx:206-211`, `DevicesPage.tsx:97-102`, `TicketsPage.tsx:111-116`, and identically in `AutomationPage.tsx`, `BillingPage.tsx`, `ClientPortalPage.tsx`, `NetworkPage.tsx`, `OSPatchesPage.tsx`, `ReportsPage.tsx`, `SoftwarePatchesPage.tsx` (12 files total, confirmed via `grep -c "bg-gray-100 rounded animate-pulse"`)
- **Snippet** (identical in all 12, only the two `length:` numbers vary per table's column/row count):
```tsx
{isLoading
  ? Array.from({ length: 6 }).map((_, i) => (
      <tr key={i}>
        {Array.from({ length: 6 }).map((_, j) => (
          <td key={j} className="px-4 py-3">
            <div className="h-4 bg-gray-100 rounded animate-pulse" />
          </td>
        ))}
      </tr>
    ))
  : /* real rows */}
```
- **Duplication:** ~9 lines × 12 sites = ~108 lines, ~95% identical (only 2 integer literals differ per site).
- **Extraction method:** shared component.
- **DRY solution:**
```tsx
// frontend/src/components/TableStates.tsx
export function SkeletonRows({ rows = 6, columns }: { rows?: number; columns: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i}>
          {Array.from({ length: columns }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 bg-gray-100 rounded animate-pulse" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
```
Call site becomes `{isLoading ? <SkeletonRows columns={7} /> : /* real rows */}`.
- **Effort:** Low — new ~15-line file + one-line swap at 12 call sites (find each table's current column count from its `<thead>` first). ~30-45 min including a visual smoke-test of a couple of pages.
- **Importance: 5/10** — no bug today, but 12 copies means a future design change (e.g. dark-mode skeleton color) needs 12 edits, and it's the kind of file a diff tool will show as "12 files changed" for one visual tweak.

### Finding E2 — Frontend empty-state shell duplicated across the same page set
- **Location:** `frontend/src/pages/AlertsPage.tsx:132-136`, `CustomersPage.tsx:105-109`, `DevicesPage.tsx:141-145`, `TicketsPage.tsx:149-153` (confirmed directly; the same `grep` list from E1 is a strong signal the other 8 files match the shape too — **unable to fully verify all 12** without reading each file)
- **Snippet:**
```tsx
{!isLoading && items.length === 0 && (
  <div className="py-16 text-center text-gray-400">
    <SomeIcon size={32} className="mx-auto mb-3 text-gray-200" />
    <p className="text-sm">No {thing} found.</p>
  </div>
)}
```
- **Duplication:** ~5 lines × 4+ confirmed sites, structure ~90% identical (icon component + message text vary; `DevicesPage.tsx` also has a conditional clause on the message).
- **Extraction method:** shared component (bundle with E1 in the same new file — they're always adjacent in the JSX and always co-occur).
- **DRY solution:**
```tsx
// frontend/src/components/TableStates.tsx
export function EmptyState({ icon: Icon, message }: { icon: LucideIcon; message: string }) {
  return (
    <div className="py-16 text-center text-gray-400">
      <Icon size={32} className="mx-auto mb-3 text-gray-200" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
```
- **Effort:** Low — folds into the same change as E1 (~20 extra minutes, mostly per-page message-string extraction for the ones with conditional text like `DevicesPage.tsx`'s search-aware message).
- **Importance: 3/10** — pure cosmetic/DRY, zero observed drift (all sampled sites use the same visual shape).

### Finding E3 — `PLATFORM_ICON_HTML`-shaped dict duplicated in two dashboard pages
- **Location:** `dashboard/pages/04_Devices.py:31-38` (`PLATFORM_ICON_HTML`) and `dashboard/pages/07_Network_Discovery.py:32-39` (named `PLATFORM_ICON` there — a different name for the same data)
- **Snippet (both, reordered but value-identical for the 6 shared keys):**
```python
{
    "windows": '<i class="fa-brands fa-windows"></i>',
    "mac":     '<i class="fa-brands fa-apple"></i>',
    "linux":   '<i class="fa-brands fa-linux"></i>',
    "android": '<i class="fa-brands fa-android"></i>',
    "ios":     '<i class="fa-brands fa-apple"></i>',
    "unknown": '<i class="fa-solid fa-question"></i>',
}
```
(`04_Devices.py` also has a second, differently-shaped `PLATFORM_ICON` dict at lines 26-29 with short text codes (`Win`/`Mac`/`Lin`/...) — that one is not duplicated elsewhere and doesn't need to move.)
- **Duplication:** 6-8 lines, 100% identical values, only the variable name and key order differ.
- **Extraction method:** shared constant.
- **DRY solution:**
```python
# dashboard/utils/styles.py — alongside the existing BRAND/STATUS_COLORS tokens
PLATFORM_ICON_HTML = {
    "windows": '<i class="fa-brands fa-windows"></i>',
    "mac":     '<i class="fa-brands fa-apple"></i>',
    "linux":   '<i class="fa-brands fa-linux"></i>',
    "android": '<i class="fa-brands fa-android"></i>',
    "ios":     '<i class="fa-brands fa-apple"></i>',
    "unknown": '<i class="fa-solid fa-question"></i>',
}
```
Then in both pages: `from utils.styles import PLATFORM_ICON_HTML` and delete the local copy (`Network_Discovery.py` currently imports `PLATFORM_ICON` under that name — update its 1 call site at line 253 to the new import name, or `import ... as PLATFORM_ICON` to avoid touching the call site).
- **Effort:** Low — ~15 minutes, 2 files touched.
- **Importance: 3/10** — cosmetic, but a real one-line-fix-becomes-two-edits risk if a platform icon ever needs to change (e.g. swapping the FontAwesome kit version).

---

## 2. Near Duplicates

### Finding N1 — Ticket status color disagrees between two pages that render the same field
- **Location:** `frontend/src/pages/TicketsPage.tsx:7-13` vs `frontend/src/pages/ClientPortalPage.tsx:9-15`
- **Snippet (side by side):**
```tsx
// TicketsPage.tsx (staff view)
const STATUS_BADGE: Record<string, string> = {
  open:        'bg-sky-100 text-sky-700',   // ← calm blue
  in_progress: 'bg-amber-100 text-amber-700',
  waiting:     'bg-purple-100 text-purple-700',
  resolved:    'bg-green-100 text-green-700',
  closed:      'bg-gray-100 text-gray-500',
};

// ClientPortalPage.tsx (client-facing view of the SAME ticket)
const STATUS_BADGE: Record<string, string> = {
  open:        'bg-red-100 text-red-600',   // ← alarming red, same key
  in_progress: 'bg-amber-100 text-amber-700',
  waiting:     'bg-purple-100 text-purple-700',
  resolved:    'bg-green-100 text-green-700',
  closed:      'bg-gray-100 text-gray-500',
};
```
`PRIORITY_BADGE` in the same two files (lines 15-20 / 17-22) is byte-identical — only `STATUS_BADGE.open` has drifted.
- **Duplication:** 2 five-key maps, 90% identical (4 of 5 values match exactly; `open` diverges), plus a fully-identical 4-key `PRIORITY_BADGE` map alongside each.
- **Assessment:** This is the concrete proof-of-harm for this whole audit category — two files independently hand-copied the same status→color mapping, and one value has already drifted without anyone noticing, because there's no single source that would have made the second edit (or the omission of it) visible. A client whose ticket is `open` sees it flagged in a color that reads as "something's wrong," while staff see the identical status in a neutral blue.
- **Extraction method:** shared constant module.
- **DRY solution:**
```tsx
// frontend/src/constants/ticketColors.ts
export const TICKET_STATUS_BADGE: Record<string, string> = {
  open:        'bg-sky-100 text-sky-700',
  in_progress: 'bg-amber-100 text-amber-700',
  waiting:     'bg-purple-100 text-purple-700',
  resolved:    'bg-green-100 text-green-700',
  closed:      'bg-gray-100 text-gray-500',
};

export const TICKET_PRIORITY_BADGE: Record<string, string> = {
  critical: 'bg-red-100 text-red-600',
  high:     'bg-orange-100 text-orange-600',
  medium:   'bg-amber-100 text-amber-700',
  low:      'bg-gray-100 text-gray-500',
};
```
Both pages `import { TICKET_STATUS_BADGE, TICKET_PRIORITY_BADGE } from '../constants/ticketColors'` and delete their local copies. **Someone with product context needs to pick which color is correct for `open` before this merges** — this report doesn't decide that.
- **Effort:** Low (mechanical) + a product decision (which color is right). ~20 minutes of code once the color is decided.
- **Importance: 6/10** — the only finding in this report that is an active, user-visible inconsistency rather than a latent risk.

### Finding N2 — Pagination boilerplate hand-rolled 12× with 3 observable shape inconsistencies
- **Location:** `api/routes/alerts.py:23-34,106-...`, `automation.py:20-31,134-...`, `customers.py:23-37,143-...`, `devices.py:55-...`, `patches.py:14-32`, `scripts.py:127-145`, `tickets.py:53-86`, `admin.py:52-58`, `usage.py:215-230` — 12 call sites total (`grep -n '\.paginate(page=page' api/routes/*.py`)
- **Snippet (the repeated shape, from `alerts.py:23-34`):**
```python
page = request.args.get("page", 1, type=int)
per_page = min(request.args.get("per_page", 50, type=int), 200)
...
paginated = query.order_by(AlertRule.name).paginate(page=page, per_page=per_page)
return jsonify({
    "items": [r.to_dict() for r in paginated.items],
    "total": paginated.total,
    "page": page,
}), 200
```
- **Observed inconsistencies** (proof this is already drifting, not hypothetical):
  1. Response shape: `customers.py`'s two endpoints (lines 34-37, 152-153) include `"pages": paginated.pages`; the other **10** call sites omit it, forcing every other frontend/dashboard consumer to compute `Math.ceil(total / per_page)` itself (and none of the sampled frontend pages do — see appendix).
  2. Key naming: `admin.py:58` returns `{"users": [...], "total": ..., "page": ...}` — `"users"` instead of `"items"`, the only one of the 12 that doesn't use `"items"`.
  3. Defaults: `customers.py`'s `list_customers` (line 24) uses `per_page` default 20 / cap 100; **all 11 other call sites** use default 50 / cap 200 (`grep -n 'per_page.*request.args.get' api/routes/*.py`).
- **Duplication:** ~10 lines × 12 sites ≈ 120 lines, ~80% identical logic.
- **Extraction method:** function.
- **DRY solution:**
```python
# api/utils/pagination.py (new — see "Utilities module" section below; this one is included as a working file in this pass)
from flask import request, jsonify

def paginated_response(query, serialize, *, order_by=None, default_per_page=50, max_per_page=200, items_key="items"):
    """Parse ?page/?per_page from the current request, paginate `query`,
    and return a ready-to-return (body, 200) tuple. `serialize` maps one
    row to a dict (e.g. `lambda r: r.to_dict()`)."""
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
```
Call site becomes:
```python
return paginated_response(query, lambda r: r.to_dict(), order_by=AlertRule.name)
```
- **Effort:** Medium — ~1 hour actual (helper + 9 call sites + 4 dashboard consumer updates + live smoke test). **Fixed** — see "Remediation Status" below.
- **Importance: 6/10** — real API inconsistency today (not just future risk); turned out to include an actual live bug (`admin.py`'s `"users"` key vs. the React Admin page's `data.items` read — see Remediation Status).

### Finding N3 — `_require_admin()` independently reimplemented twice, missed by the sibling audit's `require_role()` rollout
- **Location:** `api/routes/admin.py:22-27` vs `api/routes/org_settings.py:13-17`, compared against `api/utils/auth_decorators.py:19-28` (`require_role`, added by `design_patterns_audit.md`'s Finding S5 fix — rolled out to 14 route files, but **not these two**, because neither used the `_require_role(*roles)` name/shape that fix searched for)
- **Snippet:**
```python
# api/routes/admin.py — needs the User row (for admin.id in audit logs), so re-derives the check
def _require_admin():
    uid = get_jwt_identity()
    user = db.session.get(User, uid)
    if not user or user.role not in ("admin", "superadmin"):
        return None, jsonify({"error": "Admin access required"}), 403
    return user, None, None

# api/routes/org_settings.py — claims-only, functionally IDENTICAL to require_role("admin")
def _require_admin():
    claims = get_jwt()
    if claims.get("role") in ("admin", "superadmin"):
        return None
    return jsonify({"error": "Admin access required"}), 403
```
- **Assessment:** `org_settings.py`'s version is a pure duplicate of `require_role("admin")` (same claims-based check, same superadmin-inclusive logic) — it can be deleted outright. `admin.py`'s version is not a pure duplicate (it needs the `User` object for `admin.id`/audit-log attribution, which `require_role()` doesn't return), so it needs a small refactor rather than a delete, but its *role-check condition* is still the same logic living a third place. Both also return a different error string (`"Admin access required"`) than `require_role`'s (`"Insufficient permissions"`) — a minor response-body inconsistency for API clients that isn't part of any documented contract change.
- **Duplication:** ~5-6 lines × 2 sites, ~90% logically identical to code that already exists centrally.
- **Extraction method:** delete + reuse (org_settings.py), partial refactor (admin.py).
- **DRY solution:**
```python
# api/routes/org_settings.py — delete _require_admin(), replace both call sites with:
from utils.auth_decorators import require_role
...
err = require_role("admin")
if err:
    return err
```
```python
# api/routes/admin.py — keep the User fetch (still needed for audit_log(admin_id=...)),
# but delegate the role check itself:
from utils.auth_decorators import require_role

def _require_admin():
    err = require_role("admin")
    if err:
        return None, err[0], err[1]
    user = db.session.get(User, get_jwt_identity())
    return user, None, None
```
- **Effort:** Low — ~20 minutes, 2 files, no schema/migration involved. Verify against `api/tests/` (both files likely have route tests exercising the 403 path).
- **Importance: 5/10** — same class of security-drift risk the sibling audit rated 6/10 for the 16-file version (Finding S5); scored slightly lower here only because it's 2 files, not 16.

### Finding N4 — Marshmallow `*CreateSchema`/`*UpdateSchema` pairs hand-duplicate every field
- **Location:** `api/schemas/admin.py` (`CreateUserSchema`/`UpdateUserSchema` lines 6-29, `DepartmentCreateSchema`/`DepartmentUpdateSchema` lines 32-47), `alerts.py` (`AlertRuleCreateSchema`/`AlertRuleUpdateSchema`, full file, lines 7-36), and the same `*CreateSchema`/`*UpdateSchema` shape confirmed present (by `grep -l UpdateSchema`) in `automation.py`, `customers.py`, `devices.py`, `scripts.py`, `tickets.py` — 7 files, at least 8 pairs
- **Snippet** (`schemas/alerts.py`, both classes shown earlier in full — the Update class is the Create class with every field's `required=True`/`load_default=...` stripped to make it optional):
```python
class AlertRuleCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    operator = fields.String(required=True, validate=validate.OneOf(_OPERATORS))
    severity = fields.String(load_default="warning", validate=validate.OneOf(_SEVERITIES))
    # ...

class AlertRuleUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=255))
    operator = fields.String(validate=validate.OneOf(_OPERATORS))
    severity = fields.String(validate=validate.OneOf(_SEVERITIES))
    # ... same 9 fields, same validators, just non-required
```
- **Assessment:** This is exactly what marshmallow's built-in `partial=True` load option exists for — `AlertRuleCreateSchema().load(data, partial=True)` validates the same field types/choices but doesn't require every field to be present, with zero duplicated class body. The current pattern means every validator tweak (e.g. widening `_SEVERITIES`) has to be made in both classes, in every one of the 7 files, or Create and Update silently diverge on what's a valid value.
- **Duplication:** ~10-15 lines per pair × 8 pairs ≈ 90-120 lines, ~85% field-for-field identical (differs only in `required=`/`load_default=` presence).
- **Extraction method:** eliminate the second class; parameterize the existing decorator.
- **DRY solution:**
```python
# api/utils/validation.py
def validate_body(schema_class, partial=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            errors = schema_class(partial=partial).validate(data)
            if errors:
                return jsonify({"error": "Validation failed", "details": errors}), 400
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```
```python
# api/routes/alerts.py — update_rule route:
@validate_body(AlertRuleCreateSchema, partial=True)   # delete AlertRuleUpdateSchema entirely
def update_rule(rule_id):
    ...
```
- **Effort:** Medium — the `validate_body` change is trivial (~5 min), but each of the 8 pairs needs its Update-route decorator swapped and the now-dead `*UpdateSchema` class deleted, then the route's *test* re-run to confirm behavior didn't change (a field that was previously silently ignored on update because it was missing from the hand-written `UpdateSchema` would now validate if present — need to diff old-Update-class-fields vs Create-class-fields per pair before deleting, in case that was ever intentional). ~1-1.5 hours across 7 files, done incrementally.
- **Importance: 4/10** — no observed bug (all sampled Update schemas are a faithful subset of their Create schema), but real ongoing maintenance tax and a plausible future drift vector.

---

## 3. Structural Duplicates

### Finding S1 — Dashboard page bootstrap sequence repeated in 26 files
- **Location:** every file in `dashboard/pages/*.py` (26 files, confirmed via `grep -l st.set_page_config`), e.g. `04_Devices.py:14-18`:
```python
st.set_page_config(page_title="Devices — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()
```
- **Duplication:** 4 lines × 26 files = 104 lines, structurally identical (only the `page_title=` string varies).
- **Assessment:** `inject_css`/`require_auth`/`render_sidebar` are already correctly centralized in `dashboard/utils/` — this isn't a case of nothing being extracted, it's that the *call sequence itself* is still copy-pasted. `st.set_page_config` must be the first Streamlit command a page script runs, which is why this can't be fully hidden — but it doesn't have to be literally the first *line*, only the first `st.*` call, so it can move inside a helper as long as that helper is invoked before any other `st.*` call (true at all 26 sites today).
- **Extraction method:** function.
- **DRY solution:**
```python
# dashboard/utils/page.py (new)
import streamlit as st
from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css

def bootstrap_page(title: str, layout: str = "wide"):
    """Call as the first statement in every dashboard/pages/*.py file."""
    st.set_page_config(page_title=f"{title} — RMM", layout=layout)
    inject_css()
    client = require_auth()
    render_sidebar()
    return client
```
```python
# dashboard/pages/04_Devices.py
from utils.page import bootstrap_page
client = bootstrap_page("Devices")
```
- **Effort:** Low-medium — new 15-line file (~10 min) + a 4-line→1-line swap at 26 call sites (~1 line each, but 26 files to touch and smoke-test that `require_auth()`'s redirect-on-logged-out behavior still fires correctly on at least one page).
- **Importance: 2/10** — real DRY debt, but zero observed drift or bugs; the current repetition is easy to read and doesn't currently hide any inconsistency (every page's four lines are already identical). Lowest-urgency structural finding in this report.

### Finding S2 — `X.isoformat() if X else None` guard repeated 80× across 18 model files
- **Location:** 80 occurrences across 18 files in `api/models/*.py` (`grep -rn "isoformat() if self\." api/models/*.py | wc -l`), e.g. `api/models/alert.py:39,62-63,67`, `api/models/ai_conversation.py:27-28,56,88-90`, `api/models/audit.py:21-22,24,53,76`
- **Snippet (representative, `alert.py:62-63`):**
```python
"triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
"resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
```
- **Duplication:** one-line pattern, but 80 occurrences is real volume; each is trivial in isolation but the aggregate is a lot of repeated ceremony inside every `to_dict()` in the codebase, and a missed `if X else None` guard is a plausible `AttributeError: NoneType has no attribute 'isoformat'` waiting to happen on the 81st one.
- **Extraction method:** function.
- **DRY solution:**
```python
# api/utils/serializers.py (new)
def iso(dt):
    """dt.isoformat() if dt is set, else None — for use inside to_dict() bodies."""
    return dt.isoformat() if dt else None
```
```python
# api/models/alert.py
from utils.serializers import iso
"triggered_at": iso(self.triggered_at),
"resolved_at": iso(self.resolved_at),
```
- **Effort:** Medium — the helper is trivial, but touching 80 call sites across 18 files (even as a mechanical find-replace, `X.isoformat() if X else None` → `iso(X)`, with a regex) needs a careful review pass since a couple of sites may format non-`self.` locals or use a slightly different guard (`if self.x is not None` vs `if self.x`) that a blind regex would mis-transform. Do this as its own isolated commit with the full test suite run before/after, not bundled with other changes. ~45-60 min.
- **Importance: 3/10** — no observed bug (all 80 sampled sites use the correct guard), pure boilerplate-reduction.

---

## 4. Data Duplication

### Finding DD1 — Staff-role tuple hand-maintained in 3 files under 2 names
- **Location:** `api/routes/admin.py:19` (`_VALID_STAFF_ROLES`), `api/schemas/admin.py:3` (`_ROLES`), `api/swagger_spec.py:767` (inlined again as a JSON-schema `enum`)
- **Snippet (all three, same 4 values):**
```python
# api/routes/admin.py
_VALID_STAFF_ROLES = ("admin", "technician", "viewer", "client")

# api/schemas/admin.py
_ROLES = ("admin", "technician", "viewer", "client")
```
```python
# api/swagger_spec.py:767
"role": {"type": "string", "enum": ["admin", "technician", "viewer", "client"]},
```
- **Assessment:** `admin.py` doesn't import from `schemas/admin.py` even though it already imports `CreateUserSchema`/`UpdateUserSchema` from that exact module — the tuple was independently retyped instead of imported. If a 5th staff role is ever added (or `client` stops being staff-assignable), it needs a coordinated edit in 3 files with 2 different names, none of which reference each other.
- **Duplication:** 1 line × 3 sites, values 100% identical.
- **Extraction method:** shared constant.
- **DRY solution:**
```python
# api/schemas/admin.py — keep as the source of truth (it's the validation layer)
_ROLES = ("admin", "technician", "viewer", "client")
```
```python
# api/routes/admin.py
from schemas.admin import _ROLES as _VALID_STAFF_ROLES
```
The `swagger_spec.py` enum is a static OpenAPI doc string, not importable Python at doc-build time in the same way — leave it as a literal but add a comment pointing back to the source of truth so a future edit knows to check both:
```python
# api/swagger_spec.py:767
"role": {"type": "string", "enum": ["admin", "technician", "viewer", "client"]},  # keep in sync with schemas/admin.py::_ROLES
```
- **Effort:** Low — ~10 minutes.
- **Importance: 4/10** — no observed drift yet (all 3 currently agree), but 3 independent copies of an access-control-adjacent constant is exactly the shape of finding that turns into a real bug the day someone updates 2 of the 3.

---

## Appendix — Not scored / Unable to verify

**Brand color palette duplicated across Python and JS build tooling** — `dashboard/utils/styles.py:20-34` (`BRAND` dict, hex strings) vs `frontend/tailwind.config.js:7-17` (`brand` Tailwind scale, same `#407E3C` family, different shade-numbering scheme). Not scored: this is duplication across two different languages/build systems (Streamlit has no access to a Tailwind config, and Tailwind's `theme.extend.colors` can't import a `.py` file), so a genuine single-source fix would mean introducing a design-token generator (e.g. a shared `design-tokens.json` that a small script expands into both `styles.py` and `tailwind.config.js` at build time) — real infrastructure for a palette that, as sampled, has **not** drifted (both anchor on `#407E3C`/`#2D5C29`/`#5DB85A`, matching CLAUDE.md's documented brand line). Worth a follow-up only if a third UI surface is added or the two are ever caught disagreeing.

**Whether all 12 of E1's files also match E2's empty-state shape exactly** — confirmed directly for `AlertsPage.tsx`, `CustomersPage.tsx`, `DevicesPage.tsx`, `TicketsPage.tsx`; the remaining 8 (`AdminPage.tsx`, `AutomationPage.tsx`, `BillingPage.tsx`, `ClientPortalPage.tsx`, `NetworkPage.tsx`, `OSPatchesPage.tsx`, `ReportsPage.tsx`, `SoftwarePatchesPage.tsx`) were not individually read for this pattern. What would confirm it: `grep -n -A4 "!isLoading && .*length === 0"` on each of those 8 files.

**Whether frontend pages compute `Math.ceil(total/per_page)` themselves to work around N2's missing `"pages"` key, or simply don't paginate past page 1** — `grep -rn "Math.ceil" frontend/src/pages/*.tsx` returned no matches, suggesting the latter (a real, separate product gap — most list pages may have no "next page" control at all — but outside this audit's scope to confirm without reading each page's pagination UI).

---

## Utilities module

One new module was written and wired in as part of this pass:

- **`api/utils/pagination.py`** — `paginated_response()`, the Finding N2 fix. Wired into 9 of its 12 target call sites (see Remediation Status above); the other 3 either didn't need it (`devices.py`) or don't fit its shape (`alerts.py::list_alerts`, `usage.py::events` — both got a smaller inline fix instead).

The remaining recommended modules (Finding E1/E2's `frontend/src/components/TableStates.tsx`, Finding N1's `frontend/src/constants/ticketColors.ts`, Finding S1's `dashboard/utils/page.py`, Finding S2's `api/utils/serializers.py`) are specified above with working code but intentionally **not created as files** in this pass — each needs either a product decision (N1: which color is correct) or touches enough call sites (10-26 files) that bundling them into an audit commit would violate the project's own "one bug fix at a time, verified" convention. Recommend actioning them as separate, individually-tested follow-ups, in the priority order of the summary table.

---

*Report generated by static codebase review — Claude Code, 2026-09-24.*
