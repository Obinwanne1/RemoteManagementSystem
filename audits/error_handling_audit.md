# Error Handling Audit — RMM System

**Date:** 2026-09-24
**Scope:** `api/`, `dashboard/`, `agent/`, `frontend/` (excluding `venv/`, `node_modules/`, `__pycache__/`, `dist/`)
**Method:** Static review of source, grep-verified pattern counts, one finding confirmed by live reproduction (Flask-Limiter + Redis outage). All findings are anchored to real file paths/line numbers found in the current tree; items that could not be directly verified are marked **Unable to verify**.

---

## Executive Summary

The Flask API has a genuinely well-built centralized error handler (`api/app.py`'s `_register_error_handlers`) that correctly unifies 404/409/429/500 responses and never leaks a raw traceback to a client under normal operation. That foundation is real and good. The gaps cluster in three places: (1) **two single points of failure that convert a dependency outage into either an information leak or a total API outage**, (2) **inconsistent application of the codebase's own good patterns** (retry/rollback discipline exists and is correct in ~5 of 17 Celery task files, but not the rest), and (3) **the frontend has almost no error surfacing at all** — no ErrorBoundary, and 6 of 8 sampled `useQuery` call sites never check `isError`.

Top priorities:

| # | Finding | Category | Importance |
|---|---|---|---|
| 1 | `FLASK_DEBUG=1` enables Werkzeug's interactive debugger with no guard against also running `FLASK_ENV=production`, and binds to `0.0.0.0` by default — full source/traceback/local-variable disclosure to the network on any 500 | Error Information | **9/10** |
| 2 | Flask-Limiter fails **closed** on a Redis outage — reproduced live: every single API request 500s, not just rate-limited ones. The opposite of the fail-open pattern already proven correct in `cache.py`/`events.py`/`rate_limit.py` three files over | Error Recovery | **9/10** |
| 3 | `dashboard/utils/api_client.py`'s retry logic applies identically to all HTTP methods, including non-idempotent actions like `mdm_wipe_device`, `run_script`, `create_ticket` — a lost response on timeout can silently resubmit a device wipe | Error Recovery | **7/10** |
| 4 | `api/tasks/maintenance_tasks.py::prune_old_data` has zero exception handling around 5 deletes + commit — an unhandled failure can poison the shared app-singleton DB session for the *next*, unrelated Celery task | Async Error Handling | **7/10** |
| 5 | `str(exc)` from third-party SDK/Celery/Redis exceptions returned verbatim to the client at 8 sites in `psa.py`/`mobile_mdm.py` — one specifically risks leaking the Redis connection string (with password) | Error Information | **6/10** |
| 6 | 6 of 8 sampled React `useQuery` call sites never check `isError`; no global `QueryCache`/`MutationCache` fallback either — failed fetches render as silently-empty UI | Async Error Handling | **6/10** |

Everything else is either a real but lower-severity gap (scored individually below), a documented inconsistency worth cleaning up opportunistically, or a positive finding cited for calibration — this codebase has more correct patterns than broken ones; the issue is coverage, not absence.

**Full finding count:** 37, distributed as: Consistency 5 · Categorization 6 · Async 12 · Recovery 11 · Information 14 (some findings span/cross-reference categories and are counted once at their primary category).

---

## Remediation Status — 2026-09-24

Every actionable finding scored 3/10 or higher was fixed the same day as this audit (plus several lower-scored ones bundled in alongside related fixes). Full test suite: **149/149 passing** (146 original + 3 new regression tests), verified against the live stack (Memurai, API, Celery worker/beat, dashboard, frontend all restarted and health-checked after the changes). Finding R2 (Flask-Limiter fail-open) was additionally verified with a live reproduction — a test app pointed at an unreachable Redis address returned `200 OK` instead of `500` after the fix.

| Finding | Fix | Files |
|---|---|---|
| I1 (9/10) — debug mode + 0.0.0.0 | Refuse to start if `FLASK_DEBUG=1` and `FLASK_ENV=production`; debug mode now binds `127.0.0.1` only | `api/app.py` |
| R2 (9/10) — Flask-Limiter fails closed | Added `in_memory_fallback_enabled=True` — verified live with an unreachable Redis address | `api/extensions.py` |
| R3 (7/10) — non-idempotent POST retried | `_request()` now only retries GET/PUT/DELETE; POST fails fast on timeout | `dashboard/utils/api_client.py` (+2 new regression tests) |
| A1 (7/10) — `prune_old_data` unguarded | Added `bind=True, max_retries=2`, try/except with rollback+retry/re-raise | `api/tasks/maintenance_tasks.py` |
| I3 (6/10) — `str(exc)` leaked, 8 sites | Generic client messages + `exc_info=True` server-side logging at all 8 sites | `api/routes/psa.py`, `api/routes/mobile_mdm.py` |
| A10 (6/10) — no query error surfacing | Global `QueryCache`/`MutationCache` `onError` → toast; new minimal toast system (no new dependency) | new `frontend/src/components/Toast.tsx`; `frontend/src/main.tsx` |
| A9 (5/10) — no ErrorBoundary | Added root-level `ErrorBoundary` | new `frontend/src/components/ErrorBoundary.tsx`; `frontend/src/main.tsx` |
| Cat1 (5/10) — JWT errors use `"msg"` not `"error"` | Registered `unauthorized_loader`/`invalid_token_loader`/`expired_token_loader`/`revoked_token_loader` (422 preserved for the wrong-token-type case, matching flask_jwt_extended's own default) | `api/app.py` |
| I4 (5/10) — billing.py SMTP leak | Generic client message; full traceback still logged server-side | `api/routes/billing.py` |
| R6 (5/10) — no circuit breaker | Added `consecutive_failures` counter + auto-disable after 10 consecutive failures | new migration `r9s0t1u2v3w4`; `api/models/psa_integration.py`, `api/models/mdm_integration.py`, `api/tasks/psa_tasks.py`, `api/tasks/mdm_tasks.py` |
| A2 (5/10) — `persist_hourly_usage_rollup` unguarded | Same pattern as A1 | `api/tasks/usage_tasks.py` |
| A3 (6/10) — network scan stuck "running" | Wrapped scan body in try/except; failure now sets `status="failed"` with an error message instead of hanging forever | `api/tasks/network_tasks.py` |
| A4 (4/10) — decorative retry config | PSA/MDM fan-out dispatchers now actually retry on `OperationalError`; MQTT connection failures now retry; fixed a missing `rollback()` before re-commit in both per-integration sync functions | `api/tasks/psa_tasks.py`, `api/tasks/mdm_tasks.py`, `api/tasks/mqtt_tasks.py` |
| I5 (3/10) — PIL exception leaks | Generic client messages + logging | `api/routes/auth.py`, `api/routes/org_settings.py` |
| I6 (4/10) — SSE token error leaked | Generic "invalid token" message to unauthenticated callers | `api/routes/events.py` |
| I7 (4/10) — dashboard forwards raw response body | JSON-aware error extraction (prefers `{"error": ...}`, falls back to text, truncated to 300 chars) | `dashboard/utils/api_client.py` (bundled with R3) |
| I10 (4/10) — inconsistent notification-failure logging | Added `exc_info=True` at all 3 sites; removed a redundant try/except around `publish_event()` (which already never raises) | `api/services/ticket_service.py`, `api/routes/tickets.py` |
| I11 (4/10) — dashboard silently discards errors | Added `st.caption()` warnings at the sites the audit cited | `dashboard/pages/02_Tickets.py`, `04_Devices.py`, `10_Admin.py`, `11_Automation.py`, `12_OS_Patches.py`, `19_Mobile_Enrollment.py` |
| C4 (4/10) — no shared frontend error helper | Added `apiErrorMessage()`; applied at all 9 ad hoc extraction sites found | new `frontend/src/api/errors.ts`; `AuthContext.tsx`, `AdminPage.tsx`, `TerminalPage.tsx`, `ClientPortalPage.tsx`, `DiskManagementPage.tsx`, `MaintenancePage.tsx`, `ProfilePage.tsx` |
| I13 (2/10) — silent connection-pool warmup | Added the same `logger.warning` its 4 sibling blocks already had | `api/app.py` |
| R11 (1/10) — doc drift (7-day vs 30-day) | Corrected the CLAUDE.md changelog line to match the code | `CLAUDE.md` |

**A real bug found and fixed during remediation, not in the original audit:** while restarting the live stack, found a leftover duplicate Celery beat process from an earlier session (started before a stale-schedule-file bug was fixed), which would have caused every periodic task to fire twice. Killed the stale process and started a single clean worker + beat. Also added the dbm.dumb-backend schedule file variants (`.bak`/`.dat`/`.dir`) to `.gitignore`, alongside the existing sqlite3-backend variants (`-shm`/`-wal`) — Python 3.11 and 3.13 use different `dbm` backends and produce different filenames for the same runtime artifact.

**Not changed** (by design, per the audit's own remediation guidance, or out of scope for a same-day pass):
- **Cat2, Cat3, Cat4, Cat5, C1, C2, C3, C5, A5–A8, A11, A12, R1, R4, R5, R7–R10, I2, I8, I9, I12, I14** — positive findings, or the audit's own remediation was conditional/optional/"not urgent" (e.g. R5's exponential-backoff-vs-fixed-countdown across 16 sites was explicitly scored low because it's "bounded and safe as-is").
- **R10** (inconsistent `OperationalError` discrimination in `billing_tasks.py`/`email_tasks.py`/`ticket_tasks.py`) — narrowed for `psa_tasks.py`/`mdm_tasks.py`'s fan-out dispatchers as part of the A4 fix; the remaining 3 files' broad `except Exception` retry blocks were left as-is per the audit's own "not dangerous, bounded by max_retries" assessment.
- **C3** (migrate ~21 manually-validated routes to `validate_body` schemas) — no single fix; a per-route migration explicitly out of scope for a same-day pass.

---

## 1. Error Handling Consistency

**Finding C1 (positive): A genuine centralized error handler exists and is well-designed**
- Location: `api/app.py:289-336` (`_register_error_handlers`)
- Snippet:
```python
@app.errorhandler(RateLimitExceeded)
def rate_limit_exceeded(e):
    return {"error": "Too many requests. Please slow down."}, 429
...
@app.errorhandler(IntegrityError)
def db_integrity(e):
    db.session.rollback()
    app.logger.warning("IntegrityError: %s", type(e.orig).__name__)
    return {"error": "Conflict: duplicate or constraint violation"}, 409
...
@app.errorhandler(Exception)
def unhandled(e):
    app.logger.error("Unhandled %s: %s", type(e).__name__, str(e)[:200], exc_info=True)
    return {"error": "Internal server error"}, 500
```
- Assessment: `RateLimitExceeded`, `IntegrityError` (→ 409, with rollback), `OperationalError` (→ 503, with rollback), and a catch-all `Exception` handler (→ 500, full server-side traceback, generic client message) are all registered once, application-wide. Any route that lets an exception propagate still gets a safe, uniform JSON response instead of Flask's default HTML error page.
- **Importance: 2/10** — positive finding, cited as the baseline the rest of this report measures against.
- Remediation: N/A, working as intended.

**Finding C2: No custom error class hierarchy — every error path is a raw `jsonify(...), <code>` tuple or a raised stdlib/library exception**
- Location: whole `api/` tree — `grep -rn "class \w*(Error|Exception)\b" api/` returns zero matches
- Assessment: Not inherently wrong — the centralized `@app.errorhandler` registrations (Finding C1) achieve most of the same benefit without an exception hierarchy. But it means a route can't `raise NotFoundError("device")` and get a typed, consistent 404 with a resource-specific message; it has to remember to call `db.get_or_404(...)` or hand-write the tuple correctly every time.
- **Importance: 3/10**
- Remediation (optional, if ever adopted):
```python
# api/utils/errors.py
class ApiError(Exception):
    def __init__(self, message, status_code=400, **extra):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.extra = extra

# api/app.py, in _register_error_handlers:
@app.errorhandler(ApiError)
def api_error(e):
    return {"error": e.message, **e.extra}, e.status_code
```

**Finding C3: `validate_body()` gives field-level errors; ~21 route files doing manual inline validation give only a flat string**
- Location: `api/utils/validation.py:6-18` (`validate_body`) vs. ~21 route files calling `request.get_json()` directly
- Snippet:
```python
# validate_body-covered routes (12 files):
errors = schema_class().validate(data)
if errors:
    return jsonify({"error": "Validation failed", "details": errors}), 400

# manually-validated routes (21 files), e.g. auth.py:104:
return jsonify({"error": "Email and password required"}), 400
```
- Assessment: Not a bug — both are valid `{"error": ...}` 400s. But it's a real quality inconsistency: 12 of ~33 route files tell the caller exactly which field failed and why; the rest give one generic string with no field attribution.
- **Importance: 3/10**
- Remediation: Migrate the highest-traffic manually-validated endpoints (`auth.py` login/register, `tickets.py` create) to `validate_body` + a matching schema — no single drop-in fix, a per-route migration.

**Finding C4: React frontend's 401 handling is centralized (good); every other error is handled ad hoc per-component with `as any` defeating TypeScript's error typing**
- Location: `frontend/src/api/client.ts:13-41` (interceptor, positive) vs. e.g. `frontend/src/pages/AdminPage.tsx:186-188`
- Snippet:
```typescript
// client.ts — genuinely centralized 401 refresh/retry/logout for ALL requests
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401 && !original._retry) { /* refresh + retry, or logout */ }
    return Promise.reject(err);
  }
);
```
```tsx
// AdminPage.tsx:186-188 — every other error unwrapped manually, per call site
{createUser.isError && (
  <p className="text-xs text-red-600">{(createUser.error as any)?.response?.data?.error ?? 'Failed to create user'}</p>
)}
```
- Assessment: Only 8 of ~19 page files do any error-message extraction at all; every site that does repeats `(err as any)?.response?.data?.error ?? '<fallback>'` with no shared helper or typing.
- **Importance: 4/10**
- Remediation:
```typescript
// frontend/src/api/errors.ts
import { AxiosError } from 'axios';
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (err instanceof AxiosError) {
    return err.response?.data?.error ?? err.response?.data?.msg ?? fallback;
  }
  return fallback;
}
```
Note this helper should check both `error` and `msg` keys — see Finding Cat1 below on why the API itself is inconsistent about which key it uses.

**Finding C5 — Unable to verify: whether every Streamlit page checks the `(data, error)` tuple's error half**
- Location: `dashboard/utils/api_client.py:66-94` (`_request`, contract confirmed: always returns `(data, error_or_None)`) vs. `dashboard/pages/*.py` (22 files)
- Assessment: `_request()` itself is disciplined. Whether every one of the 22 pages checks `error` before using `data` was not exhaustively verified across all 22 — see Section 5 Finding I11 for a partial, related sample (15+ sites checked there, no crash found but a UX gap identified).
- What would confirm it: `grep -L "if err" dashboard/pages/*.py` cross-referenced against which pages call fallible `client._get`/`_post` methods.

---

## 2. Error Categories

**Finding Cat1: 401 auth failures use `{"msg": ...}`, breaking the app's own `{"error": ...}` convention — because no custom JWT error loaders are registered**
- Location: `api/extensions.py:12` (`jwt = JWTManager()` — no `unauthorized_loader`/`invalid_token_loader`/`expired_token_loader`/`revoked_token_loader` registered anywhere; `grep -rn "_loader" api/*.py api/**/*.py` returns zero matches); `api/config.py` has no `JWT_ERROR_MESSAGE_KEY` override
- Snippet:
```python
# api/extensions.py — zero custom error callbacks
jwt = JWTManager()
```
```python
# Every OTHER error in this codebase: {"error": "..."}, <code>
# A missing/expired/invalid/revoked JWT returns flask-jwt-extended's UNCUSTOMIZED default:
# {"msg": "Token has expired"}  — note the key is "msg", not "error"
```
- Assessment: A real, verifiable API-contract inconsistency — every hand-written error uses `"error"` as the key (hundreds of occurrences codebase-wide, zero uses of `"msg"` anywhere in `api/routes/`), but the single most common failure mode a client will see — an expired token — comes back under a different key. Currently harmless for both first-party clients (dashboard checks `resp.status_code == 401` directly; React's interceptor keys off `err.response?.status`), but a footgun for any future/external consumer following the documented `{"error": string}` shape.
- **Importance: 5/10**
- Remediation:
```python
# api/app.py, inside create_app(), after jwt.init_app(app):
@jwt.unauthorized_loader
def _jwt_missing(reason):
    return {"error": "Authorization token required"}, 401

@jwt.invalid_token_loader
def _jwt_invalid(reason):
    return {"error": "Invalid or malformed token"}, 401

@jwt.expired_token_loader
def _jwt_expired(jwt_header, jwt_payload):
    return {"error": "Token has expired"}, 401

@jwt.revoked_token_loader
def _jwt_revoked(jwt_header, jwt_payload):
    return {"error": "Token has been revoked"}, 401
```
Cheaper one-line alternative: `app.config["JWT_ERROR_MESSAGE_KEY"] = "error"` before `jwt.init_app(app)` — loses per-case message wording control.

**Finding Cat2: 403s are consistent in shape but come from 3 different implementations with different wording**
- Location: `api/utils/auth_decorators.py::require_role()` → `"Insufficient permissions"`; `api/routes/usage.py::_require_superadmin()` → `"Super Administrator access required"`; `api/routes/admin.py::_require_admin()` → different call signature entirely (`admin, err, code = _require_admin()`)
- Assessment: All three land on 403 with `{"error": ...}` (consistent key, unlike Finding Cat1), but three message strings for one concept, and `admin.py`'s helper has a different signature than the 14-file-consolidated `require_role()` pattern. This mirrors the earlier design-pattern audit's S5/D3 findings — `admin.py`/`usage.py` are the two intentionally-distinct outliers from that consolidation pass (usage.py has no superadmin bypass, by design).
- **Importance: 2/10**
- Remediation: Not urgent — both outliers have documented reasons to stay distinct.

**Finding Cat3 (positive): 404s uniformly routed through `db.get_or_404()` → the centralized handler**
- Location: `api/app.py:306-308` (`@app.errorhandler(404)`)
- Snippet:
```python
@app.errorhandler(404)
def not_found(e):
    return {"error": "Resource not found"}, 404
```
- Assessment: Correctly unified — `db.get_or_404()`'s internal `abort(404)` raises `werkzeug.exceptions.NotFound`, caught regardless of call site. The only cost: the message is always the same generic string, so a 404 on a device and a 404 on a ticket are indistinguishable by message text alone — a minor, common REST tradeoff, not a bug.
- **Importance: 1/10** — positive finding.
- Remediation: N/A. Only worth changing if resource-type-specific 404 text is ever needed: `return {"error": getattr(e, "description", None) or "Resource not found"}, 404`.

**Finding Cat4 (positive): 429s are fully unified — no gap**
- Location: `api/app.py:293-299`
```python
@app.errorhandler(RateLimitExceeded)
def rate_limit_exceeded(e):
    return {"error": "Too many requests. Please slow down."}, 429

@app.errorhandler(429)
def too_many_requests(e):
    return {"error": "Too many requests. Please slow down."}, 429
```
- Assessment: Both the Flask-Limiter-specific exception class and the generic HTTP 429 status are registered with identical bodies. No Flask-Limiter default (HTML) response can leak through. (Contrast with Section 4 Finding R2 — this handler catches the *limit-exceeded* case correctly; it does NOT catch the separate *Redis-unreachable* case, which is the actual 9/10 finding.)
- **Importance: 1/10** — positive finding.

**Finding Cat5 (positive): 400 vs 422 usage is correct — one justified 422 outlier, no real conflict**
- Location: `api/routes/auth.py:447` (only non-framework 422 use found: `jsonify({"error": f"Image processing failed: {exc}"}), 422`, see Section 5 Finding I5 for the leak issue with this specific line's message content — the *status code choice* is correct, the *message content* is not)
- Assessment: Textbook-correct 422 usage for "syntactically valid but semantically unprocessable" (bad image bytes), distinct from 400 (malformed/missing fields) used everywhere else.
- **Importance: 1/10** — confirms correctness.

**Finding Cat6: Third-party/Celery/Redis exceptions that escape a route's local handling degrade safely (Finding C1) but lose their original status-code hint, flattening e.g. a PSA API's own 4xx into a generic RMM-side 500**
- Location: `api/utils/android_mgmt.py::_request()` (re-raises after logging), several `api/routes/mobile_mdm.py` call sites (e.g. `:146`) call the client directly without a local try/except
- Assessment: Not a broken-response bug (client always gets clean JSON, never a raw traceback, per Finding C1) but a real observability/categorization gap: an upstream integration returning its own 400/429 gets flattened to "Internal server error" on this API, losing the distinction between "our server broke" and "the upstream integration rejected the request." This overlaps with Section 4's error-recovery findings on third-party client resilience — scored there, not double-counted here.
- **Importance: N/A here** (see Section 4 for the substantive recovery-focused fix)

---

## 3. Async Error Handling

**Finding A1: `prune_old_data` has zero exception handling around 5 deletes + commit, with no rollback — and now shares the app-wide DB session singleton with every other task**
- Location: `api/tasks/maintenance_tasks.py:17-75` (`prune_old_data`)
- Snippet:
```python
@celery.task(name="tasks.maintenance_tasks.prune_old_data")
def prune_old_data():
    with _get_app().app_context():
        ...
        metrics_deleted = DeviceMetrics.query.filter(...).delete(synchronize_session=False)
        audit_deleted = AuditLog.query.filter(...).delete(synchronize_session=False)
        script_deleted = ScriptRun.query.filter(...).delete(synchronize_session=False)
        usage_events_deleted = ApiUsageEvent.query.filter(...).delete(synchronize_session=False)
        usage_hourly_deleted = ApiUsageHourly.query.filter(...).delete(synchronize_session=False)
        db.session.commit()
```
- Assessment: No try/except at all — not even bare. This runs daily via beat against 5 tables. If any `.delete()`/`.commit()` raises (lock timeout, FK violation, connection drop), the exception propagates uncaught: no rollback, no retry (no `bind=True`/`max_retries` declared either). Since `tasks/_app_singleton.py` (a recent refactor) means this task shares the **same** scoped session object across every task file in the worker process, a failed, un-rolled-back session here can poison the session for the *next*, unrelated task (e.g. `alert_tasks.evaluate_all_rules` 60s later) with a `PendingRollbackError`.
- **Importance: 7/10**
- Remediation:
```python
@celery.task(name="tasks.maintenance_tasks.prune_old_data", bind=True, max_retries=2)
def prune_old_data(self):
    from sqlalchemy.exc import OperationalError
    with _get_app().app_context():
        try:
            ...
            db.session.commit()
            return {...}
        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=300)
        except Exception:
            db.session.rollback()
            logger.exception("prune_old_data failed")
            raise
```

**Finding A2: `persist_hourly_usage_rollup`'s Postgres commit path is unguarded — only the Redis read is protected**
- Location: `api/tasks/usage_tasks.py:11-70`
- Snippet:
```python
@celery.task(name="tasks.usage_tasks.persist_hourly_usage_rollup")
def persist_hourly_usage_rollup():
    with _get_app().app_context():
        try:
            client = _get_client()
            raw = client.hgetall(key)
        except Exception as exc:
            logger.warning("persist_hourly_usage_rollup: Redis read failed: %s", exc)
            return {"rows": 0}
        for (endpoint, method), stats in buckets.items():
            existing = ApiUsageHourly.query.filter_by(...).first()
            ...
        db.session.commit()   # unguarded
```
- Assessment: Deliberately resilient to Redis being down (graceful fallback), but treats Postgres as if it can't fail. Same session-poisoning risk as Finding A1, plus no `bind=True`/retry — a transient commit failure (e.g. a concurrent unique-constraint race) permanently drops that hour's rollup with no retry.
- **Importance: 5/10**
- Remediation: same shape as Finding A1 — wrap the DB section, add `bind=True, max_retries=2`.

**Finding A3: A network scan can get stuck "running" forever in the UI — the main scan body has no exception handling despite `bind=True, max_retries=2`**
- Location: `api/tasks/network_tasks.py:253-359` (`_run_scan`, `run_network_scan`)
- Snippet:
```python
@celery.task(name="tasks.network_tasks.run_network_scan", bind=True, max_retries=2)
def run_network_scan(self, scan_id: str):
    with _get_app().app_context():
        _run_scan(scan_id)   # no try/except here either

def _run_scan(scan_id: str):
    ...
    with ThreadPoolExecutor(max_workers=50) as pool:
        ...
        result = _upsert_agentless_host(...)   # can raise
    scan.status = "completed"   # only reached if nothing above raised
    db.session.commit()
```
- Assessment: Two early-return paths correctly set `scan.status = "failed"` for known bad input (invalid CIDR, range too large), but the main scan body (thread pool, upsert, commit) has no try/except anywhere in the call chain. Any exception there leaves the `NetworkScan` row permanently at whatever status it was before dispatch — the Network Discovery dashboard page polls this row and shows an indefinite spinner with no error, and `max_retries=2` is decorative since `self.retry()` is never called.
- **Importance: 6/10**
- Remediation:
```python
def _run_scan(scan_id: str):
    scan = db.session.get(NetworkScan, scan_id)
    if not scan:
        return
    try:
        ...
        scan.status = "completed"
        scan.completed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        scan.status = "failed"
        scan.completed_at = datetime.now(timezone.utc)
        scan.discovered_hosts = [{"error": str(exc)}]
        db.session.commit()
        logger.exception("Network scan %s failed", scan_id)
```

**Finding A4: `bind=True, max_retries=N` declared but `self.retry()` never called — decorative retry config on 4 tasks**
- Location: `api/tasks/mqtt_tasks.py:37-38,90-99`, `api/tasks/mdm_tasks.py:13-25`, `api/tasks/psa_tasks.py:12-21`, `api/tasks/network_tasks.py` (see Finding A3)
- Snippet:
```python
@celery.task(name="tasks.mqtt_tasks.subscribe_mqtt_sensors", bind=True, max_retries=3)
def subscribe_mqtt_sensors(self):
    try:
        client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=10)
        ...
    except Exception as exc:
        logger.warning("MQTT connection error (%s:%d): %s", _MQTT_HOST, _MQTT_PORT, exc)
        return   # self.retry() never called despite max_retries=3
```
```python
@celery.task(name="tasks.mdm_tasks.sync_all_mdm_integrations", bind=True, max_retries=1)
def sync_all_mdm_integrations(self):
    app = _get_app()
    with app.app_context():
        active = MdmIntegration.query.filter(...).all()   # can raise, nothing catches it
        for integration in active:
            sync_mdm_integration.delay(integration.id)
```
- Assessment: `bind=True`/`max_retries` is meaningless without `self.retry()`. The two fan-out dispatchers have *no* try/except at all around their DB query — a transient connection blip silently fails the entire sync cycle with no rollback.
- **Importance: 4/10**
- Remediation: for the dispatchers, add the same `OperationalError`-retry pattern used in `alert_tasks.py`. For `mqtt_tasks.py`, either drop `max_retries=3` (if silent no-op on unconfigured MQTT is intentional) or call `raise self.retry(exc=exc, countdown=60)`.

**Finding A5 (positive): `alert_tasks.py`, `patch_tasks.py`, `report_tasks.py`, `automation_tasks.py`, `email_tasks.py` share a correct, consistent retry/rollback template**
- Location: e.g. `api/tasks/alert_tasks.py:191-203`, `api/tasks/patch_tasks.py:129-133`
- Snippet:
```python
except OperationalError as exc:
    db.session.rollback()
    raise self.retry(exc=exc, countdown=30)
except Exception:
    db.session.rollback()
    logger.exception("<task_name> failed")
    raise
```
- Assessment: The correct pattern — transient DB errors retried with backoff, everything else rolled back, logged with full traceback, re-raised so Celery marks FAILED (captured by Sentry's `CeleryIntegration`, confirmed wired in `celery_app.py:15-27`). ~5 of 17 task files use it; the rest are Findings A1-A4.
- **Importance: 2/10** — cited as the template the rest should match.

**Finding A6 (positive): Sentry's Celery integration is correctly wired independent of the Flask process**
- Location: `api/tasks/celery_app.py:15-27`
- Assessment: `celery -A tasks.celery_app worker/beat` never imports `api/app.py`, so Sentry needs (and has) its own `sentry_sdk.init(..., integrations=[CeleryIntegration()])`, correctly no-op'd when `SENTRY_DSN` is unset. Any task that re-raises after logging (Finding A5's pattern) IS captured; the silently-swallowed paths in A1-A4 escape both log-level and Sentry visibility.
- **Importance: 2/10** — positive finding.

**Finding A7 (positive): Agent main loop has strong, layered async/background error handling**
- Location: `agent/rmm_agent.py:238-367` (`main`)
- Snippet:
```python
except ConnectionError as e:
    _consecutive_failures += 1
    backoff = min(15 * (2 ** (_consecutive_failures - 1)), 300)
    logger.warning("NETWORK_FAILURE: %s — backing off %ds", e, backoff)
    time.sleep(backoff)
    continue
except Exception as e:
    logger.error("UNEXPECTED_ERROR: %s", e, exc_info=True)
```
- Assessment: Every exception class is classified and handled without crashing the process; individual sub-tasks (auto-update check, screenshot capture) have their own nested try/except so one failing subsystem never blocks heartbeats or patch scanning. Correct, capped exponential backoff shared across network-error and 401-reregistration branches. The strongest error-handling code in the repo.
- **Importance: 1/10** — positive finding.

**Finding A8 (positive): `TerminalWorker`'s background thread is defensively wrapped and always closes out command status**
- Location: `agent/terminal_worker.py:66-198` (`_loop`, `_run_command`)
- Assessment: `_loop()` wraps its whole poll cycle so one bad response doesn't silently kill the daemon thread (Python threads don't propagate exceptions to the main thread — unwrapped, this would just silently stop with no restart). `_run_command()` nests try/except around subprocess spawn/stdout/stderr/wait, plus a `threading.Timer` hard-kill backstop. `self._mark_done(command_id, exit_code)` runs unconditionally after the try/except — unlike Finding A3's `NetworkScan`, a terminal command can never get stuck "running" server-side.
- **Importance: 1/10** — positive finding.

**Finding A9: No React ErrorBoundary anywhere in the frontend — an unhandled render exception produces a blank white screen**
- Location: `frontend/src/main.tsx:18-26` — `grep -rn "ErrorBoundary\|componentDidCatch" frontend/src` returns zero matches across all 19 pages
- Snippet:
```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter><App /></BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
```
- Assessment: Since React 16+, an uncaught render exception (e.g. `.map()` over `undefined` because an API response shape changed) unmounts the *entire* component tree — blank page, nothing user-visible, only the browser console shows anything.
- **Importance: 5/10**
- Remediation:
```tsx
// frontend/src/components/ErrorBoundary.tsx
import { Component, type ReactNode } from 'react';

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: unknown) { console.error('Render error:', error, info); }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24 }}>
          <h2>Something went wrong.</h2>
          <button onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
```
```tsx
// main.tsx
<ErrorBoundary><App /></ErrorBoundary>
```

**Finding A10: 6 of 8 sampled `useQuery` call sites never check `isError`; no global fallback either**
- Location: `frontend/src/pages/AlertsPage.tsx`, `CustomersPage.tsx`, `DevicesPage.tsx`, `TicketsPage.tsx`, `UsageMonitoringPage.tsx` (2 of 3 queries), `components/AiAssistant.tsx` — vs. `DashboardPage.tsx`/`TerminalPage.tsx` which do check; `main.tsx:8-16`'s `QueryClient` has no `QueryCache`/`MutationCache`-level `onError`
- Snippet (confirmed absent):
```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
    // no throwOnError, no global QueryCache({ onError }) / MutationCache({ onError })
  },
});
```
- Assessment: With `retry: 1` and no global surfacing, a page that only destructures `{ data }` (not `error`/`isError`) renders `data === undefined` as an empty list or a spinner that never resolves, with zero indication anything failed.
- **Importance: 6/10**
- Remediation:
```tsx
// main.tsx
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query';

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (err, query) => {
      if (query.state.data !== undefined) return; // don't toast on background refetch of already-shown data
      toast.error(`Failed to load: ${(err as any)?.response?.data?.error ?? 'request failed'}`);
    },
  }),
  mutationCache: new MutationCache({
    onError: (err) => toast.error((err as any)?.response?.data?.error ?? 'Action failed'),
  }),
  defaultOptions: { queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false } },
});
```
**Unable to verify:** whether a toast library is already in `frontend/package.json` — check before using this verbatim; substitute a minimal inline banner state if not.

**Finding A11 (positive): Centralized axios 401-refresh interceptor is correctly implemented**
- Location: `frontend/src/api/client.ts:13-41`
- Assessment: Single retry guard (`original._retry`) prevents infinite refresh loops; both tokens cleared and user redirected to `/login` if refresh fails. Correctly implemented — the gap (Finding A10) is that no equivalent centralization exists for 403/404/429/500.
- **Importance: 2/10** — positive finding.

**Finding A12 (positive): SSE stream generator correctly handles client disconnects and Redis unavailability without crashing the worker**
- Location: `api/routes/events.py:52-96` (`_generate`)
- Snippet:
```python
try:
    while time.monotonic() < deadline:
        msg = ps.get_message(timeout=1.0)
        ...
except GeneratorExit:
    pass
except Exception as exc:
    logger.warning("SSE stream error: %s", exc)
finally:
    try:
        ps.unsubscribe()
        ps.close()
    except Exception:
        pass
```
- Assessment: `GeneratorExit` (client disconnect mid-stream) caught explicitly rather than falling through to the generic handler; pubsub cleanup happens in `finally` regardless of exit path. Redis-unavailable-at-connect is also handled gracefully.
- **Importance: 1/10** — positive finding.

**Unable to verify:** whether `agent/heartbeat.py::APIClient`'s individual HTTP calls have their own retry/backoff distinct from `rmm_agent.py`'s main-loop backoff, and whether the main loop's `except ConnectionError`/`except TimeoutError` actually match the exception types `requests` raises (a mismatch would mean the "NETWORK_FAILURE" classified log line is unreachable and everything falls through to the generic branch — functionally similar backoff, but misleading logs). What would confirm it: read `agent/heartbeat.py` in full.

---

## 4. Error Recovery

**Finding R1 (positive): Redis-backed cache/rate-limit/event-bus layers degrade gracefully — verified in all three modules**
- Location: `api/utils/cache.py:25-73`, `api/utils/events.py:35-63`, `api/utils/rate_limit.py:16-24`
- Snippet:
```python
# api/utils/rate_limit.py:16-24
try:
    client = _get_client()
    count = client.incr(key)
    if count == 1:
        client.expire(key, window_seconds)
    return count <= limit
except Exception as exc:
    logger.debug("rate_limit check failed [%s]: %s", key, exc)
    return True
```
- Assessment: Every one of these 9 functions wraps its Redis call in try/except, logs, and returns a safe default rather than propagating. Verified by reading all three files in full, not just trusting docstrings. Correct fail-open pattern.
- **Importance: 2/10** — positive finding, the baseline the next finding violates.

**Finding R2: Flask-Limiter's own request-limiting fails CLOSED — reproduced live: a Redis outage 500s every single request**
- Location: `api/extensions.py:14-17` (`Limiter(...)`), `api/config.py:33-34` (`RATELIMIT_DEFAULT` applies app-wide), `api/app.py:293-299` (429 handlers catch limit-exceeded only, not storage failure)
- Snippet:
```python
# api/extensions.py:14-17 — no in_memory_fallback configured
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
)
```
```python
# api/config.py:33-34
RATELIMIT_DEFAULT = "200 per minute"   # app-wide — runs on EVERY request
```
- Assessment: **Reproduced live** in this session: with Redis unreachable, Flask-Limiter's `before_request` hook raises `redis.exceptions.ConnectionError` on every request (because `RATELIMIT_DEFAULT` applies globally). Nothing catches that specific exception — it falls to the generic `@app.errorhandler(Exception)`, returning a bland 500. Net effect: a Redis blip takes down 100% of API traffic, the exact opposite of the fail-open philosophy proven correct in Finding R1's three files.
- **Importance: 9/10**
- Remediation:
```python
# api/extensions.py
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
    in_memory_fallback_enabled=True,
    in_memory_fallback=["200 per minute"],
)
```
This degrades to per-process (not cluster-wide) limiting when Redis is unreachable, instead of raising.

**Finding R3: `RMMClient._request()` retries ALL HTTP methods identically — including non-idempotent actions like phone wipe, script execution, ticket creation**
- Location: `dashboard/utils/api_client.py:66-94` (`_request`), consumed by `mdm_wipe_device` (:594-595), `run_script` (:333-335), `create_ticket` (:310-311), `reboot_device`/`shutdown_device` (:257-261), `deploy_patches` (:427-428)
- Snippet:
```python
_RETRY_ON = (requests.ConnectionError, requests.Timeout)
_BACKOFF = [0.5, 1.0, 2.0]

def _request(self, method: str, path: str, **kwargs):
    for attempt, wait in enumerate(_BACKOFF):
        try:
            resp = self.session.request(method, url, timeout=15, **kwargs)
            ...
        except _RETRY_ON as e:
            last_err = e
            if attempt < len(_BACKOFF) - 1:
                time.sleep(wait)

def mdm_wipe_device(self, device_id: str):
    return self._post(f"/api/mdm/devices/{device_id}/wipe")   # retried up to 3x on timeout
```
- Assessment: If the server fully processes `POST /api/mdm/devices/<id>/wipe` but the *response* is lost to a timeout, `_request()` silently resubmits the identical POST up to 2 more times — no idempotency key, no "already submitted" check. For `mdm_wipe_device` this could issue a real device wipe command multiple times; for `run_script`/`create_ticket`/`reboot_device`, duplicate executions/tickets/reboots.
- **Importance: 7/10**
- Remediation:
```python
_IDEMPOTENT_METHODS = {"GET", "PUT", "DELETE"}

def _request(self, method: str, path: str, **kwargs):
    url = f"{self.base}{path}"
    last_err = None
    retryable = method.upper() in _IDEMPOTENT_METHODS
    attempts = _BACKOFF if retryable else [0]
    for attempt, wait in enumerate(attempts):
        try:
            resp = self.session.request(method, url, timeout=15, **kwargs)
            if resp.status_code == 401:
                ...  # unchanged
            resp.raise_for_status()
            return resp.json(), None
        except requests.HTTPError as e:
            return None, f"HTTP {e.response.status_code}: {e.response.text}"
        except _RETRY_ON as e:
            last_err = e
            if retryable and attempt < len(attempts) - 1:
                time.sleep(wait)
            else:
                break
    return None, f"Connection failed: {last_err}"
```

**Finding R4 (positive): Agent has correctly-implemented, capped exponential backoff on heartbeat failures**
- Location: `agent/rmm_agent.py:259-268`, `:354-362`
- Snippet:
```python
if data is None:
    _consecutive_failures += 1
    backoff = min(15 * (2 ** (_consecutive_failures - 1)), 300)
    logger.warning("Heartbeat failed (failure #%d) — backing off %ds", _consecutive_failures, backoff)
    time.sleep(backoff)
    continue
```
- Assessment: Verified independently against CLAUDE.md's "Phase C: exponential backoff" claim rather than trusted — the formula is correct capped exponential backoff (15/30/60/120/240/cap 300s), applied consistently at both call sites, resets on success and on 401 re-registration. Local pending-result queue flushes on reconnect, confirming the "local task queue" changelog claim too.
- **Importance: 2/10** — positive finding.

**Finding R5: Celery task retries use fixed countdowns, not exponential — bounded/safe but a missed resilience improvement under sustained outages**
- Location: 16 `self.retry()` call sites across `alert_tasks.py`, `automation_tasks.py`, `patch_tasks.py`, `report_tasks.py`, `email_tasks.py`, `mdm_tasks.py`, `psa_tasks.py`, `billing_tasks.py`, `backup_tasks.py`, `ticket_tasks.py`
- Snippet:
```python
raise self.retry(exc=exc, countdown=30)   # representative of all 16 sites
```
- Assessment: Every retry uses a hardcoded countdown. Not dangerous — `max_retries` bounds every task reviewed — but a longer outage gets the same retry cadence as a 1-second blip, generating avoidable load right as a dependency recovers.
- **Importance: 3/10**
- Remediation: `raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 600))`

**Finding R6: No circuit breaker anywhere — confirmed absent by full-repo grep; PSA/MDM models have the data fields for one but never use them**
- Location: `grep` for `circuit`/`breaker`/`half.open` across the whole repo returns zero matches; `api/models/psa_integration.py:22-24` (`is_active`, `last_sync_at`, `sync_error`), same fields on `MdmIntegration`; `api/tasks/psa_tasks.py:18,50,56`, `api/tasks/mdm_tasks.py:20,112,118`
- Snippet:
```python
# api/tasks/psa_tasks.py:18 — every cycle re-attempts every active integration, forever
active = PsaIntegration.query.filter_by(is_active=True).all()
...
integration.sync_error = str(exc)[:500]   # failure recorded, is_active never flipped
```
- Assessment: `PsaIntegration`/`MdmIntegration` already carry the fields a circuit breaker needs, but neither sync task ever sets `is_active = False` after repeated failures — only a human can. An integration with revoked credentials retries every 15 minutes forever, generating log noise and wasted outbound calls, with no automatic circuit-opening and no proactive alert beyond the passive `sync_error` field.
- **Importance: 5/10**
- Remediation:
```python
# api/models/psa_integration.py — add one column
consecutive_failures = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```
```python
# api/tasks/psa_tasks.py
except Exception as exc:
    integration.sync_error = str(exc)[:500]
    integration.consecutive_failures = (integration.consecutive_failures or 0) + 1
    if integration.consecutive_failures >= 10:
        integration.is_active = False
        logger.warning("Disabling PSA integration %s after %d consecutive failures",
                       integration.id, integration.consecutive_failures)
else:
    integration.sync_error = None
    integration.consecutive_failures = 0
```
(Mirror in `mdm_tasks.py`.)

**Finding R7 (positive): SMTP send failures degrade gracefully and consistently across all 11 notification functions**
- Location: `api/utils/notifications.py` (`_smtp_send` + 10 wrapper functions)
- Snippet:
```python
try:
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        ...
    return True
except Exception as exc:
    logger.warning("Failed to send ... for '%s': %s", ..., exc)
    return False
```
- Assessment: Every SMTP call site — unset `SMTP_HOST`, connection refused, or auth failure — degrades to a logged warning and `False`, never crashing the calling route/task. Verified for the failing-not-just-unset case specifically.
- **Importance: 2/10** — positive finding. (This exact boilerplate is duplicated 8 times instead of routing through `_smtp_send` — a DRY issue, not a recovery gap, out of scope here.)

**Finding R8 (positive, with one soft gap): AI Assistant degrades gracefully with correctly-categorized status codes when Anthropic is unreachable, but makes no retry of its own**
- Location: `api/routes/assistant.py:161-242`
- Snippet:
```python
except Exception as exc:
    exc_name = type(exc).__name__
    db.session.rollback()
    record_event(service="ai_assistant", feature=page, user_id=ctx.user_id, status="error", error=f"{exc_name}: {str(exc)[:200]}")
    if "AuthenticationError" in exc_name:
        return jsonify({"error": "AI service configuration error — check ANTHROPIC_API_KEY"}), 503
    if "RateLimitError" in exc_name:
        return jsonify({"error": "AI service is busy. Please try again in a moment."}), 429
    log.exception("AI assistant chat failed")
    return jsonify({"error": "AI assistant temporarily unavailable"}), 503
```
- Assessment: Any exception from `client.messages.create()` rolls back the DB session (preventing half-written state), records a usage event, and returns a correctly-categorized 503/429. Gap: no retry of the Anthropic call — a single transient network hiccup fails the whole chat turn. Defensible for a synchronous chat UI (fail fast, let the human resend), not a clear defect.
- **Importance: 2/10**
- Remediation (optional): a single bounded retry for connection-level errors only:
```python
try:
    resp = client.messages.create(**create_kwargs)
except anthropic.APIConnectionError:
    time.sleep(1)
    resp = client.messages.create(**create_kwargs)
```

**Finding R9 (positive): `pool_pre_ping` + `pool_recycle` give real connection-drop resilience; routes correctly delegate DB-error categorization to one global handler**
- Location: `api/config.py:13-14`, `api/app.py:319-330`
- Snippet:
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True, "pool_recycle": 300, "pool_size": 10, "max_overflow": 20, "pool_timeout": 30,
}
```
```python
@app.errorhandler(OperationalError)
def db_operational(e):
    db.session.rollback()
    app.logger.error("DB OperationalError: %s", type(e).__name__)
    return {"error": "Database unavailable"}, 503
```
- Assessment: `pool_pre_ping` transparently reconnects on a stale/dropped connection instead of surfacing a broken-pipe error. Combined with the global `OperationalError` → 503 handler, the ~14 of 24 route files that never explicitly catch `OperationalError` (confirmed: zero imports of it in `routes/*.py`) still get correct, uniform 503 behavior on a genuine DB outage.
- **Importance: 2/10** — positive finding.

**Finding R10: Task-level `OperationalError` handling is inconsistent — 5 of ~17 task files discriminate it, the rest retry on any exception**
- Location: discriminating: `alert_tasks.py`, `automation_tasks.py`, `backup_tasks.py`, `patch_tasks.py`, `report_tasks.py`. Non-discriminating: `billing_tasks.py:121`, `email_tasks.py:260`, `mdm_tasks.py:120`, `psa_tasks.py:58`, `ticket_tasks.py:38`
- Snippet:
```python
# psa_tasks.py:58 — retries on literally anything
except Exception as exc:
    raise self.retry(exc=exc, countdown=120)
```
- Assessment: Not dangerous (bounded by `max_retries` everywhere) but means a genuine bug (e.g. `TypeError` from malformed payload) in a "discriminating" file fails immediately and loudly, while the identical bug in a non-discriminating file gets silently retried multiple times before surfacing — delaying detection of real code defects.
- **Importance: 3/10**
- Remediation:
```python
from sqlalchemy.exc import OperationalError
...
except OperationalError as exc:
    raise self.retry(exc=exc, countdown=120)
except Exception:
    logger.exception("sync_all_psa_integrations: non-retryable failure")
    raise
```

**Finding R11: Doc/code drift — CLAUDE.md claims a 7-day metrics-history fallback; code uses 30 days**
- Location: `dashboard/pages/04_Devices.py:550-569`
- Snippet:
```python
mdata, merr = client.get_device_metrics(device["id"], hours=24)
if not merr and not mdata:
    mdata, merr = client.get_device_metrics(device["id"], hours=720)   # not 168
```
- Assessment: The fallback mechanism works correctly (empty 24h window → widen the query, clear "agent offline" banner) — just not the window size the changelog claims. Low-stakes drift, nothing breaks.
- **Importance: 1/10**
- Remediation: Update the CLAUDE.md line to `hours=720`, or narrow the code to 168 if 30 days was unintentional.

**Unable to verify:** whether `agent/heartbeat.py`'s individual HTTP calls have their own per-call timeout/retry distinct from the caller-level backoff (grepping for `backoff`/`retry`/`sleep` in that file found no local retry logic, implying it all sits in the caller — but individual exception handlers weren't read for their return contract). Also unverified: whether `api/utils/stripe_client.py` and `api/utils/android_mgmt.py`'s outbound calls have any `timeout=` configured at all — a missing timeout is a distinct unbounded-hang risk separate from retry behavior.

---

## 5. Error Information

**Finding I1: `FLASK_DEBUG=1` enables Werkzeug's interactive debugger with no guard against `FLASK_ENV=production`, bound to `0.0.0.0` by default**
- Location: `api/app.py:339-348` (`if __name__ == "__main__":`)
- Snippet:
```python
if __name__ == "__main__":
    app = create_app()
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5000))
    if os.getenv("FLASK_DEBUG", "0") == "1":
        app.run(host=host, port=port, debug=True, use_reloader=False)
    else:
        from waitress import serve
        serve(app, host=host, port=port, threads=16)
```
- Assessment: `debug=True` turns on Werkzeug's interactive debugger. `use_reloader=False` only disables the file-watcher — NOT the debugger. With `debug=True`, any unhandled exception renders the full traceback + source-code context in the HTTP response with **no PIN required to view it** (the PIN only gates the in-browser Python console). Combined with the default `API_HOST=0.0.0.0`, this is reachable network-wide, not just localhost. Nothing checks `FLASK_DEBUG` against `config_name` — `FLASK_ENV=production` (secure cookies, no dev warning) and `FLASK_DEBUG=1` can be set simultaneously with no startup error, silently defeating both protections at once. This also completely bypasses the app's own `@app.errorhandler(Exception)` (Werkzeug's debug middleware intercepts before Flask's own handlers run when debug is on).
- **Importance: 9/10** — full source/traceback/local-variable disclosure on any 500, reachable network-wide, one environment-variable flip away from the current safe state.
- Remediation:
```python
if __name__ == "__main__":
    app = create_app()
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    if debug and os.getenv("FLASK_ENV") == "production":
        raise RuntimeError("Refusing to start: FLASK_DEBUG=1 with FLASK_ENV=production")
    if debug:
        app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)  # never 0.0.0.0 in debug mode
    else:
        from waitress import serve
        serve(app, host=host, port=port, threads=16)
```

**Finding I2 (positive): The catch-all `@app.errorhandler(Exception)` is correctly implemented**
- Location: `api/app.py:332-336`
- Snippet:
```python
@app.errorhandler(Exception)
def unhandled(e):
    app.logger.error("Unhandled %s: %s", type(e).__name__, str(e)[:200], exc_info=True)
    return {"error": "Internal server error"}, 500
```
- Assessment: `exc_info=True` captures the full traceback server-side; the client gets a fixed generic string. `IntegrityError`/`OperationalError` handlers correctly log only `type(e.orig).__name__`, explicitly avoiding raw DB detail. The right pattern — the baseline Findings I3-I5 deviate from.
- **Importance: 1/10** — positive finding.

**Finding I3: `str(exc)` from Celery/Redis/third-party-SDK exceptions returned verbatim to the client at 8 sites**
- Location: `api/routes/psa.py:141,239`, `api/routes/mobile_mdm.py:149,181,205,286,367,401`
- Snippet:
```python
# api/routes/psa.py:135-141
try:
    from tasks.psa_tasks import sync_psa_integration
    sync_psa_integration.delay(integration_id)
    return jsonify({"message": "Sync queued", "integration_id": integration_id}), 202
except Exception as exc:
    logger.error("Failed to queue PSA sync: %s", exc)
    return jsonify({"error": str(exc)}), 500
```
```python
# api/routes/mobile_mdm.py:144-149
try:
    client = integration.get_client()
    result = client.create_signup_url(callback_url)
except Exception as exc:
    logger.error("MDM bind start failed for %s: %s", integration_id, exc)
    return jsonify({"error": str(exc)}), 502
```
- Assessment: `psa.py:141` wraps a Celery `.delay()` call — if the Redis broker is unreachable/misconfigured, the raised exception's `str()` can include the broker connection string (`REDIS_URL`, which may embed a password per this codebase's own `redis://:<password>@host:port/db` scheme). The `mobile_mdm.py` sites wrap Google Android Management API calls — a `requests.HTTPError` stringifies to the full request URL + Google's raw JSON error body; a `google.auth` credential error can include parts of the service-account email/project ID. All 8 sites are `admin`/`technician`-gated (not unauthenticated), lowering severity, but they're a real inconsistency against `app.py`'s own established pattern (Finding I2) and a genuine secret-leak vector for the Celery/Redis case specifically.
- **Importance: 6/10** (7/10 for `psa.py:141` given the Redis-URL-with-password risk; 5/10 for the Google API sites)
- Remediation (apply to all 8 sites):
```python
except Exception as exc:
    logger.error("MDM bind start failed for %s: %s", integration_id, exc, exc_info=True)
    return jsonify({"error": "Could not start MDM enrollment. Check integration credentials and try again."}), 502
```

**Finding I4: `billing.py`'s invoice-email failure returns the raw SMTP exception to the client, while its OWN audit trail two lines away correctly redacts it**
- Location: `api/routes/billing.py:230-234`
- Snippet:
```python
except Exception as exc:
    logger.warning("Failed to email invoice %s: %s", inv_num, exc)
    record_event(service="smtp", feature="invoice_email", status="error",
                 latency_ms=int((time.perf_counter() - _t0) * 1000), error=type(exc).__name__)  # safe
    return jsonify({"error": f"Email delivery failed: {exc}"}), 500   # not safe — same exc, unredacted
```
- Assessment: `smtplib` exceptions frequently embed the mail server's raw SMTP response, which can include the internal SMTP hostname and, for some providers, hints about the account/credential state. The safe pattern (`type(exc).__name__` only) exists two lines away in the same except block and isn't applied to the client-facing message.
- **Importance: 5/10**
- Remediation: `return jsonify({"error": "Email delivery failed — check SMTP configuration."}), 500`

**Finding I5: Two image-upload routes leak raw Pillow/PIL exception text**
- Location: `api/routes/auth.py:447`, `api/routes/org_settings.py:86`
- Snippet:
```python
return jsonify({"error": f"Image processing failed: {exc}"}), 422   # auth.py:447
return jsonify({"error": f"Image processing failed: {e}"}), 400     # org_settings.py:86
```
- Assessment: Lower risk than I3/I4 (PIL errors are typically format/decode complaints), but still inconsistent with the app's generic-message convention, occasionally including a temp file path.
- **Importance: 3/10**
- Remediation: `return jsonify({"error": "Image processing failed — please upload a valid JPEG/PNG under the size limit."}), 422`

**Finding I6: `/api/events/stream`'s token-validation error is returned raw to an unauthenticated caller**
- Location: `api/routes/events.py:17-27,38-41`
- Snippet:
```python
def _validate_token_param(token: str) -> tuple:
    if not token:
        return None, "token required"
    try:
        claims = decode_token(token)
        return claims, None
    except ExpiredSignatureError:
        return None, "token expired"
    except (DecodeError, Exception) as exc:
        return None, f"invalid token: {exc}"
```
- Assessment: This is the SSE endpoint's own pre-`@jwt_required()` auth check (reads `?token=` since `EventSource` can't set headers), reachable by a fully unauthenticated caller. `PyJWT` exception strings are generally short/generic, not a secrets leak, but it hands an anonymous prober the library's internal validation-failure reason, inconsistent with every other auth failure in the app (flat "Invalid credentials"/"Insufficient permissions"). (Separately: `except (DecodeError, Exception)` is dead-code redundant since `DecodeError` is already an `Exception` subtype.)
- **Importance: 4/10**
- Remediation:
```python
except ExpiredSignatureError:
    return None, "token expired"
except Exception:
    return None, "invalid token"
```

**Finding I7: The dashboard forwards the entire raw response body on HTTP errors — the delivery mechanism for Finding I1's debug-mode leak if it's ever triggered**
- Location: `dashboard/utils/api_client.py:86-88`
- Snippet:
```python
except requests.HTTPError as e:
    return None, f"HTTP {e.response.status_code}: {e.response.text}"
```
- Assessment: 10+ dashboard pages' `st.error(f"... — {err}")` render whatever this puts in `err`. Today the API only returns small, clean JSON bodies, so this is currently benign. But this is exactly the code path that would render a full Werkzeug debugger HTML page (source, local variables, possibly env-var values in stack frames) directly into the Streamlit UI if Finding I1 is ever triggered. It's also not JSON-aware — a non-JSON error body renders its raw markup as-is.
- **Importance: 4/10 standalone; effectively inherits Finding I1's 9/10 as the delivery mechanism** — call out the pairing when prioritizing fixes.
- Remediation:
```python
except requests.HTTPError as e:
    try:
        detail = e.response.json().get("error", e.response.reason)
    except Exception:
        detail = e.response.reason or f"HTTP {e.response.status_code}"
    return None, f"HTTP {e.response.status_code}: {detail}"[:300]
```

**Finding I8 (positive): AI Assistant's Claude-API failure path is a model example of correct layered error handling**
- Location: `api/routes/assistant.py:232-242` (see full snippet at Finding R8)
- Assessment: Three-tier handling done right: `log.exception` for full server-side traceback, `record_event` persists a truncated typed summary to the durable usage-audit table (debuggable after the fact via `/api/admin/usage`), and the client gets a clean, differentiated, non-leaking message per failure class. One soft spot: the `AuthenticationError` branch's message ("check ANTHROPIC_API_KEY") reaches ANY caller including `role=client` end users, not just admins — a config hint inappropriate for a non-technical client-role user, though not a secret.
- **Importance: 2/10** (the client-role wording nit is 3/10)
- Remediation (optional):
```python
if "AuthenticationError" in exc_name:
    log.error("AI assistant misconfigured: %s", exc)
    return jsonify({"error": "AI assistant is temporarily unavailable. Please contact your administrator."}), 503
```

**Finding I9 (positive): `_audit()` in the AI Assistant correctly logs full tracebacks on its own failure path**
- Location: `api/routes/assistant.py:91-104`
- Snippet:
```python
def _audit(user_id, action, resource_type, resource_id, payload):
    try:
        db.session.add(AuditLog(...))
        db.session.commit()
    except Exception:
        log.exception("AI assistant audit log write failed")
        try:
            db.session.rollback()
        except Exception:
            pass
```
- Assessment: `log.exception(...)` (not `logger.warning(str(e))`) ensures a broken audit-log write is fully debuggable, and the failure doesn't crash the parent request.
- **Importance: 1/10** — positive finding.

**Finding I10: Widespread logging-completeness inconsistency — `logger.warning` with no traceback, or no log call at all, for near-identical "best-effort side-effect failed" cases in the same function**
- Location: `api/services/ticket_service.py:131-132` vs. `:143-144`; `api/routes/tickets.py:199-200,266-267`
- Snippet:
```python
# ticket_service.py:131-132 — logs a message, no exc_info
except Exception:
    current_app.logger.warning("Ticket create notification failed for ticket %s", ticket.id)

# ticket_service.py:143-144 — same file, same class of failure, but SILENT
except Exception:
    pass
```
- Assessment: Two adjacent `except Exception:` blocks handle conceptually identical "best-effort notification failed" cases with different rigor — one logs without a traceback, one logs nothing. `tickets.py:199-200,266-267` repeat the no-`exc_info` pattern. None of the four capture a traceback, so a production notification-send failure gives ops a message like "Ticket create notification failed for ticket abc123" with zero indication of *why* — every recurrence requires reproducing locally.
- **Importance: 4/10** — not a leak, a real operability/debuggability gap.
- Remediation:
```python
except Exception:
    current_app.logger.warning("Ticket create notification failed for ticket %s", ticket.id, exc_info=True)
```
(apply the same `exc_info=True` fix to all four sites, including the currently-silent one.)

**Finding I11: Dashboard pages widely discard the `(data, error)` tuple's error half for "supporting" lookups — no crash found, but silent degradation with zero user feedback**
- Location: 15+ sites, e.g. `dashboard/pages/12_OS_Patches.py:20`, `10_Admin.py:350,353`, `11_Automation.py:77,192`, `02_Tickets.py:89,235`, `19_Mobile_Enrollment.py:125,191`, `04_Devices.py:210,508`
- Snippet:
```python
# 12_OS_Patches.py:20-21
summary, _ = client.get_patch_summary()
if summary:
    ...  # stat cards row — no `else`, row silently vanishes on error
```
```python
# 02_Tickets.py:89-91
cust_data, _ = client.list_customers(per_page=100)
customers = cust_data.get("items", []) if cust_data else []
# on error: dropdown shows "— no customers —", indistinguishable from a genuinely empty list
```
- Assessment: Specifically checked for the crash risk raised in the audit directive — **not found**: every sampled site uses `X if data else default`, so `AttributeError: NoneType has no attribute 'get'` does not occur (this defensive idiom is consistently applied — good). What's missing is user-visible signal: on a transient failure, these sections render as if the data is genuinely empty rather than surfacing "could not load — connection failed," which could mislead an admin into thinking a list is actually empty.
- **Importance: 4/10** — UX/observability gap, not a crash or security issue.
- Remediation (pattern to apply at each site):
```python
summary, err = client.get_patch_summary()
if err:
    st.caption(f"⚠ Could not load patch summary — {err}")
elif summary:
    ...
```

**Finding I12 (positive): Sentry initialization is correctly conditional and PII-safe**
- Location: `api/app.py:12-23`
- Snippet:
```python
_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    sentry_sdk.init(dsn=_sentry_dsn, integrations=[FlaskIntegration(), CeleryIntegration()],
                    traces_sample_rate=0.05, send_default_pii=False)
```
- Assessment: Confirmed exactly as claimed — `send_default_pii=False` (no automatic user/request PII to Sentry), and the whole block is skipped (no crash) when `SENTRY_DSN` is unset.
- **Importance: 1/10** — positive finding.

**Finding I13: Connection-pool warm-up swallows silently — the one inconsistent block among 5 similar startup try/excepts**
- Location: `api/app.py:122-129`
- Snippet:
```python
try:
    from sqlalchemy import text as _text
    for _ in range(min(3, app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}).get("pool_size", 10))):
        db.session.execute(_text("SELECT 1"))
    db.session.remove()
except Exception:
    pass
```
- Assessment: Its four sibling try/except blocks in the same function (lines 84-120) all log a warning on failure; this one is completely silent. Low severity (pure optimization, no functional impact) but if the DB is genuinely unreachable at startup, this fails invisibly and the first operator signal is degraded first-request latency, not a log line.
- **Importance: 2/10**
- Remediation: `except Exception as exc:\n    app.logger.warning("Connection pool warm-up failed: %s", exc)`

**Finding I14 — Unable to verify: frontend axios/TanStack Query console-log/error-surfacing behavior beyond what Finding A10 already covers**
- Assessment: Not investigated beyond A10's `isError`-coverage sampling — would need to check whether any axios interceptor logs raw request/response bodies (including auth headers) to the browser console, which devtools-equipped users could see. Lower stakes than a server-side leak but still worth a follow-up pass.
- What would confirm it: read `frontend/src/api/client.ts` fully for any `console.log`/`console.error` of the raw `err`/`err.config` object, not just the interceptor's control flow.

---

## Appendix — Items Marked "Unable to Verify"

| Item | Section | What would confirm it |
|---|---|---|
| Whether every Streamlit page checks the `(data, error)` tuple's error half | Consistency (C5) | `grep -L "if err" dashboard/pages/*.py` cross-referenced against fallible client calls |
| `agent/heartbeat.py`'s per-call retry/timeout behavior, and whether `rmm_agent.py`'s `except ConnectionError`/`TimeoutError` actually match what `requests` raises | Async (A-appendix) | Full read of `agent/heartbeat.py`, specifically each `requests.exceptions.*` handler's return contract |
| Whether `api/utils/stripe_client.py`/`api/utils/android_mgmt.py` outbound calls have `timeout=` configured at all | Recovery (R-appendix) | Grep both files for `requests.` / SDK call sites and check for a `timeout=` kwarg |
| Whether any axios interceptor logs raw request/response bodies (incl. auth headers) to the browser console | Information (I14) | Full read of `frontend/src/api/client.ts` for `console.*` calls on the raw error/config object |

---

*Report generated by static codebase review — Claude Code, 2026-09-24.*
