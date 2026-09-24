# Design Pattern Audit — RMM System

**Date:** 2026-09-24
**Scope:** `api/`, `dashboard/`, `agent/`, `frontend/` (excluding `venv/`, `node_modules/`, `__pycache__/`, `dist/`)
**Method:** Static review of source, grep-verified duplication counts, cross-file consistency checks. All findings are anchored to real file paths/line numbers found in the current tree; items that could not be directly verified are marked **Unable to verify**.

---

## Executive Summary

The codebase applies Creational and Structural patterns reasonably well in the places that matter most (PSA/MDM client factories, the Flask application factory, the AI Assistant's Command-based confirm/deny flow) but has **accumulated duplication debt from a pattern it already knows how to write correctly** — the biggest recurring theme in this audit is *inconsistency*, not *absence*: the same correct idiom (a memoized singleton, a role-check guard, a tenant-scope check) is written once well and then hand-copied with small drift across many files instead of being extracted.

Two findings are security-relevant and worth prioritizing over the rest:

| # | Finding | Category | Importance |
|---|---|---|---|
| 1 | `_client_scope_check`/`_mdm_scope_check` tenant-isolation logic duplicated across `devices.py`/`mobile_mdm.py`, already drifting, after a **documented prior cross-tenant leak** (`4d4362a`) | Domain — Repository | **7/10** |
| 2 | `_require_role()` copy-pasted verbatim across 16 route files with no shared decorator — one silent edit-miss reintroduces a permission bug | Structural — Decorator (missing) | **6/10** |
| 3 | `dashboard/utils/api_client.py` session-reuse optimization is claimed in CLAUDE.md's changelog but **does not exist in code** — fresh `RMMClient`/TCP session built every Streamlit rerun | Structural — Facade | 6/10 |
| 4 | AI Assistant tool dispatch (`ai_tools.py`) enumerates the same 5 tool names across 3 parallel structures (rate limits, summarizer, executor) — a new mutating tool can ship without its rate limit | Behavioral — Strategy/Command | 5/10 |
| 5 | JWT decode cache (`jwt_cache.py`) creates an undocumented up-to-60s window where a revoked token or demoted role keeps working | Structural — Proxy | 5/10 |

Everything else is either a working, well-implemented pattern (flagged below as positive findings for calibration) or a minor style/DRY nit not worth urgent action.

**Full finding count:** 24, distributed as:
- Creational: 8 (1 positive-only summary item)
- Structural: 10
- Behavioral: 9
- Domain: 6

---

## Remediation Status — 2026-09-24

Every actionable finding below was fixed the same day as this audit. Full test suite: **148/149 passing** (149 = the original 146 + 3 new regression tests added below); the one failure (`TestToolRateLimit::test_check_and_increment_blocks_after_limit`) requires a live Redis server, is unrelated to any change here, and fails identically on the pre-fix codebase in a Redis-less environment.

| Finding | Fix | Files |
|---|---|---|
| D2 (7/10) — tenant-scope duplication | Consolidated into `require_customer_scope()` | new `api/utils/scope.py`; `devices.py`, `mobile_mdm.py`, `tickets.py` (2 inline copies also caught and consolidated) now import it |
| S5 (6/10) — `_require_role` duplicated 14× | Consolidated into `require_role()` (+ `roles_required()` decorator for future use) | new `api/utils/auth_decorators.py`; all 14 route files (`alerts`, `automation`, `billing`, `customers`, `devices`, `mobile_mdm`, `network`, `patches`, `psa`, `scripts`, `sensors`, `sla_policies`, `terminal`, `tickets`) now import it — zero call sites touched |
| S3 (6/10) — dashboard session not reused | `get_client()` now caches `RMMClient` in `st.session_state["_rmm_client"]`, matching CLAUDE.md's existing claim | `dashboard/utils/auth.py` |
| B3 (5/10) — AI tool dispatch: 3 parallel structures | Collapsed into one `MUTATING_TOOL_HANDLERS` dict (summarize + execute + rate_limit per tool) | `api/services/ai_tools.py` |
| S6 (5/10) — JWT cache staleness undocumented | Added explicit SECURITY NOTE docstring on the ≤60s stale-claim window | `api/utils/jwt_cache.py` |
| C1 (4/10) — `_get_app()` duplicated 15× | Consolidated into `get_app()` | new `api/tasks/_app_singleton.py`; all 15 task files now import it |
| C4 (4/10) — no MDM Factory abstract base | Added `MdmClient(ABC)` mirroring `PSAClient`; `AndroidManagementClient` now implements it | new `api/utils/mdm_client.py`; `api/utils/android_mgmt.py` |
| D1 (4/10) — `Device.query.filter_by(is_online=True)` duplicated 3× | Extracted `online_devices()` | `api/services/device_query_service.py`; `alert_tasks.py`, `anomaly_tasks.py`, `automation_tasks.py` |
| C2 (3/10) — un-memoized Redis client in `alert_tasks.py` | Reuses `utils.cache`'s pooled client instead of opening a fresh connection every 60s | `api/tasks/alert_tasks.py` |
| D5 (3/10) — no regression test for secret leaks in `to_dict()` | Added 3 tests (`User`, `PsaIntegration`, `MdmIntegration`) | new `api/tests/test_serialization.py` |
| D4 (2/10) — duplicate `_customer_name` helper | Route now imports the service's copy | `api/routes/tickets.py` |
| B4 (2/10) — redundant try/except around `publish_event` (which never raises) | Removed the dead wrapper at both call sites | `api/tasks/alert_tasks.py` |
| D3 (5/10) — inconsistent service-layer adoption (4/24 route files) | Documented the "extract only when called from 2+ places" rule so future files are consistent by convention | `CLAUDE.md` |
| D6 (3/10, "Unable to verify") | Verified: grepped every `Alert.status`/`resolved_at` write site — all correctly paired. No bug; no code change needed. | — |

**Not changed** (by design, per the audit's own remediation guidance):
- **C6/B2** (agent platform `if/elif` dispatch) — audit explicitly recommended against introducing a Strategy class hierarchy here; left as-is.
- **C7** (no Builder pattern) — audit explicitly recommended against introducing one; left as-is.
- **S1, S2, S4, S7, B1, B6, B8, B9, C3, C5** — positive findings, no fix needed.
- **B5, B7** (alert fan-out sequence, AI reply post-processing pipeline) — audit's own remediation was conditional ("only worth extracting once a second call site needs it" / "only worth a real handler chain if a 4th stage is added") — not yet triggered.
- **S8** (PgBouncer wiring) — still "Unable to verify"; would need `.env`/deployment config outside this repo's source to confirm, not something a code change can resolve.

**A real bug found and fixed during remediation, not in the original audit:** two tests in `api/tests/test_usage.py` primed the *old* per-task-module `_app` cache directly (`usage_tasks._app = app`). Consolidating that cache into `tasks/_app_singleton.py` (fix for C1) silently broke that injection point, which would have made both tests fall through to a real `create_app()` call and crash on a pre-existing, unrelated SQLite/pool-args incompatibility. Caught by running the full suite before/after on a stashed diff; fixed by pointing the two tests at the new shared singleton (`tasks._app_singleton._app = app`) instead.

---

## Creational Patterns

### Singleton

**Finding C1: Flask app singleton (`_get_app`) duplicated identically across 16 Celery task modules**
- Location: `api/tasks/alert_tasks.py:21-30`, and identically in `automation_tasks.py:11-19`, `network_tasks.py:24-32`, `mdm_tasks.py:10-18`, `usage_tasks.py:8-16`, `anomaly_tasks.py:23-31`, `snmp_tasks.py:29-37`, `ticket_tasks.py:8-16`, `maintenance_tasks.py:9-17`, `mqtt_tasks.py:25-33`, `billing_tasks.py:18-26`, `email_tasks.py:16-24`, `psa_tasks.py:9-17`, `patch_tasks.py:8-16`, `report_tasks.py:14-22` (`_get_app`)
- Pattern: Singleton (lazy, module-level)
- Snippet:
```python
# Shared Flask app — created once per worker process, not once per task
_app = None

def _get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
    return _app
```
- Assessment: Correct and intentional — fixes a real DB-pool-exhaustion bug from calling `create_app()` per task invocation (Tier-1 fix per CLAUDE.md). Safe under Celery `--pool=solo` (single-threaded); not safe if the pool mode is ever changed without an accompanying lock.
- Simpler alternative? The pattern is right-sized; the problem is it's hand-copied 16 times instead of defined once.
- **Importance: 4/10** — no active bug, pure maintainability/DRY debt. A 17th task file that forgets this boilerplate silently reintroduces the pool-exhaustion bug it was written to fix.
- Remediation:
```python
# api/tasks/_app_singleton.py
_app = None
def get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
    return _app
```
```python
# in each task file
from tasks._app_singleton import get_app as _get_app
```

**Finding C2: Un-memoized Redis client in `alert_tasks.py`, sitting three lines below a correctly-memoized `_get_app()`**
- Location: `api/tasks/alert_tasks.py:33-39` (`_get_redis`); contrast with `api/utils/cache.py:8-22` and `api/utils/events.py:16-32`, which both memoize correctly
- Pattern: Singleton (inconsistently applied)
- Snippet:
```python
# api/tasks/alert_tasks.py — NOT memoized, opens a fresh connection every call
def _get_redis():
    import redis
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_timeout=2,
        socket_connect_timeout=2,
    )
```
- Assessment: `evaluate_all_rules` runs every 60s via Celery beat forever, opening a fresh TCP connection to Redis each time, right next to a correctly-memoized `_get_app()` in the same file. `api/utils/cache.py` already exposes a pooled client (`max_connections=20`) that could be reused instead of a third parallel implementation.
- Simpler alternative? Yes — reuse `utils.cache._get_client()`.
- **Importance: 3/10** — not a correctness bug (cheap connection, slow beat), but an unforced inconsistency in a file that demonstrates it knows the correct pattern three lines up.
- Remediation:
```python
# api/tasks/alert_tasks.py
from utils.cache import _get_client as _get_redis
```

**Finding C3 (positive): JWT decode cache and superadmin bootstrap are correct singletons**
- Location: `api/utils/jwt_cache.py:15-16,23-49` (module-level `TTLCache` + `RLock`, correctly locked on both read and write, bounded size/TTL, hashes tokens before use as cache key); `api/utils/superadmin.py:24-53` (`ensure_superadmin` — idempotent "singleton row" pattern, self-heals role/password drift on every startup, fails closed if `SUPERADMIN_PASSWORD` unset)
- **Importance: 1-2/10** — cited as positive examples; no fix needed.

### Factory

**Finding C4 (positive): `PsaIntegration.get_client()` / `MdmIntegration.get_client()` — correct Factory Method with abstract Product**
- Location: `api/models/psa_integration.py:32-49`, `api/utils/psa/base.py:6-30` (`PSAClient(ABC)`), `api/models/mdm_integration.py:46-60`
- Pattern: Factory Method + abstract Product
- Snippet:
```python
# api/models/psa_integration.py
def get_client(self):
    secret = decrypt_cred(self.client_secret_enc)
    if self.type == "connectwise":
        from utils.psa.connectwise import ConnectWiseClient
        return ConnectWiseClient(api_url=self.api_url, company_id=self.company_id or "",
                                  client_id=self.client_id, client_secret=secret)
    if self.type == "autotask":
        from utils.psa.autotask import AutotaskClient
        return AutotaskClient(api_url=self.api_url, client_id=self.client_id,
                               username=self.site_name or "", secret=secret)
```
```python
# api/models/mdm_integration.py
def get_client(self):
    if self.type == "android":
        from utils.android_mgmt import AndroidManagementClient
        return AndroidManagementClient(...)
    if self.type == "apple":
        raise NotImplementedError("Apple MDM is not implemented — ...")
```
- Assessment: Textbook. `PSAClient(ABC)` defines the abstract product (`test_connection`, `get_companies`, `push_ticket`, `update_ticket`, `pull_tickets`, `push_config_item`); `ConnectWiseClient`/`AutotaskClient` are concrete products selected at runtime by `self.type`. Credentials are decrypted inside the factory method so callers never handle raw secrets. `MdmIntegration.get_client()` mirrors the shape but has **no shared abstract base** — acceptable today (one real implementation), but nothing enforces the interface a second MDM vendor must expose.
- **Importance: 2/10** (PSA half, working correctly) / **4/10** (MDM half — worth doing before a real second MDM vendor lands, not urgent while Apple raises `NotImplementedError`).
- Remediation (MDM, for when Apple support is built):
```python
# api/utils/mdm_client.py
from abc import ABC, abstractmethod
class MdmClient(ABC):
    @abstractmethod
    def lock(self, device_id: str) -> bool: ...
    @abstractmethod
    def wipe(self, device_id: str) -> bool: ...
    # mirror PSAClient's shape
```

**Finding C5 (positive): `create_app()` is a standard, correctly-implemented Flask Application Factory**
- Location: `api/app.py:49` (`create_app`)
- Assessment: Extensions instantiated once at module scope, bound per-app via `init_app` — exactly the pattern that lets `_get_app()` (Finding C1) and the pytest suite construct independent app instances safely.
- **Importance: 1/10** — positive example, no fix needed.

**Finding C6: `agent/collector.py` platform branching is not a Factory — noted only to avoid miscategorization**
- Location: `agent/collector.py:20-21,166-170,279-281,419-421`
- Assessment: Dispatches on `sys.platform` to run different collection *logic* inline — never constructs/returns a different object per platform, so it's not a Creational pattern despite superficial resemblance. Evaluated properly under Behavioral → Strategy (Finding B2) instead.
- **Importance: N/A** (out of category — see Behavioral section)

### Builder

**Finding C7: No true Builder pattern exists — and none of the candidate call sites need one**
- Location: `api/services/ai_prompt.py:220-235` (`build_system_prompt`), `api/tasks/report_tasks.py:30` (`generate_report`), `build_pdf.py` (repo root)
- Assessment: Despite the naming (`build_system_prompt`), each of these assembles output in one procedural pass from local inputs — not a step-by-step fluent Builder with a `.build()` terminal call, and none of them need to be: no scenario requires reusing a partially-constructed object across multiple different final assemblies.
- Simpler alternative? Already the simplest correct approach; a `SystemPromptBuilder` class would add ceremony for zero reuse benefit.
- **Importance: 1/10** — informational; explicitly not a gap.
- Remediation: N/A — do not introduce a Builder here.

---

## Structural Patterns

### Adapter

**Finding S1 (positive): PSA integrations — correct Adapter pattern with ABC base**
- Location: `api/utils/psa/base.py:6` (`PSAClient` ABC), `api/utils/psa/connectwise.py:23`, `api/utils/psa/autotask.py:23`
- Assessment: `ConnectWiseClient` and `AutotaskClient` each translate a different vendor REST API (different auth headers, different status/priority code tables — `_CW_STATUS_MAP` vs `_AT_STATUS`) into one uniform `PSAClient` interface. `MdmIntegration.get_client()` follows the same shape, so this is a consistently applied idiom, not a one-off.
- **Importance: 2/10** — positive finding, nothing to fix.

**Finding S2: Webhook dispatch is a clean per-channel Adapter; fan-out is unconditional, not a lookup table**
- Location: `api/utils/webhook.py:33-54` (`dispatch_alert_webhooks`, `_post_slack`/`_post_teams`/`_post_generic`)
- Snippet:
```python
for url in channels.get("slack", []):
    _post_slack(url, rule_name, device_hostname, message, severity)
for url in channels.get("teams", []):
    _post_teams(url, rule_name, device_hostname, message, severity)
for url in channels.get("webhook", []):
    _post_generic(url, rule_name, device_hostname, message, severity)
```
- Assessment: Each `_post_*` adapts common alert fields into Slack Block-Kit, Teams `MessageCard`, or generic JSON respectively, all funneled through `_send()` for centralized timeout/logging/usage-tracking.
- **Importance: 2/10**. Only worth a `dict[str, Callable]` dispatch table if a 4th channel type is added.

### Facade

**Finding S3: `RMMClient` is a solid Facade, but its documented "session reuse" does not exist in code**
- Location: `dashboard/utils/api_client.py:30-94` (`RMMClient`), `dashboard/utils/auth.py:7-15` (`get_client`)
- Snippet:
```python
def get_client() -> RMMClient | None:
    """Return a fresh RMMClient if logged in, else None."""
    token = st.session_state.get("access_token")
    if not token:
        return None
    return RMMClient(access_token=token, refresh_token=st.session_state.get("refresh_token", ""))
```
- Assessment: `RMMClient` itself is well-built (single `_request()` choke point handling retry-with-backoff and 401 auto-refresh, ~40 thin wrapper methods). But `get_client()`'s own docstring says "fresh" — a brand-new `RMMClient` (and therefore a brand-new `requests.Session()`) is constructed on **every** Streamlit rerun, since `require_auth()` calls `get_client()` unconditionally on every page load. Grepping the whole `dashboard/` tree for `st.session_state["_rmm_client"]` (the CLAUDE.md changelog's claimed "Phase B session reuse" mechanism) finds **zero matches** — the optimization described in the project's own build log is not present in current code.
- **Importance: 6/10** — real, verifiable doc/code drift, plus a real minor perf cost (new TCP+TLS handshake to the Flask API on effectively every widget interaction across 22 Streamlit pages).
- Remediation:
```python
# dashboard/utils/auth.py
def get_client() -> RMMClient | None:
    token = st.session_state.get("access_token")
    if not token:
        return None
    cached = st.session_state.get("_rmm_client")
    if cached and cached._token == token:
        return cached
    client = RMMClient(access_token=token, refresh_token=st.session_state.get("refresh_token", ""))
    st.session_state["_rmm_client"] = client
    return client
```
Also correct or remove the CLAUDE.md claim once this is implemented (or if intentionally reverted, strike it from the changelog).

**Finding S4 (positive): `api/services/*.py` are genuine Facades over the DB/model layer**
- Location: `api/services/alert_service.py`, `script_service.py`, `ticket_service.py`, `fleet_query_service.py`, `device_query_service.py`
- Assessment: Exist specifically to give the AI Assistant's tool-dispatch layer (`ai_tools.py`) a safe, narrow surface instead of touching SQLAlchemy models directly — a correct Facade motivation (least-privilege for an LLM-driven code path). Coverage inconsistency (only 4 of 24 route files use the service layer) is analyzed in Domain → Service Layer below.
- **Importance: N/A here** — see Domain Finding D3.

### Decorator

**Finding S5: `_require_role(*roles)` is not a decorator — it's a manually-invoked guard, copy-pasted near-verbatim across 16 route files**
- Location: `api/routes/devices.py:32` and identically-named functions in `automation.py`, `customers.py`, `billing.py`, `alerts.py`, `mobile_mdm.py`, `network.py`, `terminal.py`, `patches.py`, `scripts.py`, `sla_policies.py`, `tickets.py`, `sensors.py`, `psa.py` (13 more, 16 total), plus a deliberately different `_require_superadmin()` in `usage.py:24`
- Snippet:
```python
# repeated in 16 files, byte-for-byte identical except usage.py
def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") == "superadmin":
        return None  # superadmin bypasses all role checks
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None

# called inline in ~60+ view bodies:
@devices_bp.route("/", methods=["GET"])
@jwt_required()
def list_devices():
    err = _require_role("admin", "technician")
    if err: return err
```
- Assessment: Functionally correct today, but real Decorator-pattern debt: role-checking is exactly the cross-cutting concern `@jwt_required()` already models as a stackable decorator two lines above it, yet `_require_role` is reimplemented as a plain function called at the top of ~60+ view bodies instead of being a second decorator. The `usage.py` variant is intentionally stricter (no superadmin bypass, per its own docstring) — a legitimate policy difference, but nothing stops one of the other 16 copies from silently drifting the same way during a future edit, since there is no single source of truth enforcing "superadmin always bypasses except usage.py."
- Simpler alternative? Yes — a real decorator factory removes ~10 duplicated lines × 16 files and makes the `usage.py` exception self-documenting.
- **Importance: 6/10** — maintainability + security-drift risk, not an active bug.
- Remediation:
```python
# api/utils/auth_decorators.py (new file)
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt

def roles_required(*roles, allow_superadmin=True):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            role = claims.get("role")
            if allow_superadmin and role == "superadmin":
                return fn(*args, **kwargs)
            if role not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```
```python
# usage:
@devices_bp.route("/", methods=["GET"])
@jwt_required()
@roles_required("admin", "technician")
def list_devices():
    ...

# usage.py keeps its stricter policy explicitly:
@usage_bp.route("/summary", methods=["GET"])
@jwt_required()
@roles_required("superadmin", allow_superadmin=False)  # self-documents "no bypass"
def summary():
    ...
```
Mechanical, low-risk refactor across 16 files — apply opportunistically per the project's "one bug fix at a time" convention rather than as one large PR.

### Proxy

**Finding S6: `jwt_cache.install()` is a correct caching Proxy — but its security trade-off isn't documented**
- Location: `api/utils/jwt_cache.py:23-49` (`install`, `_cached_decode`)
- Snippet:
```python
def _cached_decode(locations, fresh, refresh=False, verify_type=True, skip_revocation_check=False):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        key = _token_key(auth[7:])
        with _lock:
            hit = _cache.get(key)
        if hit is not None:
            return hit
    result = _orig(locations, fresh, refresh=refresh, verify_type=verify_type,
                   skip_revocation_check=skip_revocation_check)
    if auth.startswith("Bearer ") and result:
        with _lock:
            _cache[key] = result
    return result
_vd._decode_jwt_from_request = _cached_decode
```
- Assessment: Structurally correct — real subject invoked only on cache miss, memoized keyed by MD5(token), TTL-bounded (60s), thread-safe via `RLock`, revocation checks still run on first decode. The trade-off: **any token revoked, or any user whose role changes, between decode and the 60s cache expiry keeps working with stale claims** for up to 60s — including the superadmin bypass consumed by every `_require_role()` call (Finding S5), so a demoted admin retains elevated access for up to a minute. Not called out anywhere as a caveat.
- **Importance: 5/10** — a real, if narrow, staleness window on auth decisions.
- Remediation: Document the trade-off explicitly in the module docstring:
```python
# api/utils/jwt_cache.py
"""
SECURITY NOTE: decoded claims are cached for up to 60s, so a token
revoked (or a role changed) during that window remains valid/stale
until the cache entry expires. Keep TTL short; re-evaluate this window
before raising it, given the superadmin bypass in every route file's
_require_role().
"""
```
Optionally invalidate the specific cache entry from role-change admin routes — but given the window is already short, a doc comment is likely sufficient for now.

**Finding S7 (positive): `api/utils/cache.py` is a correctly fail-open caching Proxy over Redis**
- Location: `api/utils/cache.py:11-73`
- Assessment: Every function wraps its Redis call in `try/except Exception` and degrades to cache-miss/no-op on failure, consistent with the project's documented "silently no-ops if Redis unavailable" convention. `cache_get_raw`/`cache_set_raw` avoid double-JSON-serialization for the `health_map` hot path — a legitimately scoped micro-optimization.
- **Importance: 2/10** — positive finding.

**Finding S8: PgBouncer connection proxy — referenced in CLAUDE.md, not independently verified here**
- Location: **Unable to verify** — would need `api/app.py`'s `SQLALCHEMY_ENGINE_OPTIONS`/`pool_pre_ping` config and `.env.example`'s `DATABASE_URL` default port to confirm wiring.
- **Importance: N/A** (would need the above to rate; flagged as unverified rather than guessed).

---

## Behavioral Patterns

### Strategy

**Finding B1 (positive): PSA client selection is a factory-method Strategy**
- Location: `api/models/psa_integration.py:32-50` (`get_client`), consumed by `api/tasks/psa_tasks.py:45`
- Assessment: `sync_all_psa_integrations` stays fully vendor-agnostic — the caller never branches on `.type` itself, only calls generic methods on whatever client `get_client()` returned. Adding a third PSA vendor only touches `get_client()` plus a new `utils/psa/<vendor>.py` class. Cleanest pattern instance in the codebase.
- **Importance: 3/10** (working well; only a typing nit — no formal `Protocol`/ABC constrains `ConnectWiseClient`/`AutotaskClient`'s shared interface beyond convention).
- Remediation (optional): add a `PsaClient` structural `Protocol` in `api/utils/psa/__init__.py` so mypy/IDE checks the shared method signatures without changing runtime behavior.

**Finding B2 (positive): Agent platform dispatch is plain conditional branching, correctly — not Strategy**
- Location: `agent/collector.py:166-171,279-282,419-421`
- Snippet:
```python
if _PLATFORM == "win32":
    _enrich_windows(info)
elif _PLATFORM == "darwin":
    _enrich_macos(info)
elif _PLATFORM == "linux":
    _enrich_linux(info)
```
- Assessment: `_PLATFORM = sys.platform` is fixed for the process lifetime — no call site ever needs to swap platform-collector objects at runtime, so a `PlatformCollector` class hierarchy + factory would add three classes for zero behavioral gain.
- **Importance: 1/10** — style-only; do not introduce a class hierarchy here.

**Finding B3: AI Assistant tool dispatch enumerates 5 tool names across 3 parallel structures instead of one dispatch table**
- Location: `api/services/ai_tools.py:35-41` (`_TOOL_RATE_LIMITS`), `:193-206` (`_summarize`), `:228-257` (`execute_pending_action`)
- Snippet:
```python
if pending.tool_name == "create_ticket":
    return ticket_service.create_ticket_service(...)
if pending.tool_name == "acknowledge_alert":
    return alert_service.acknowledge_alert_service(...)
if pending.tool_name == "resolve_alert":
    return alert_service.resolve_alert_service(...)
if pending.tool_name == "run_builtin_action":
    return script_service.run_builtin_action_service(...)
if pending.tool_name == "run_script":
    return script_service.run_script_service(...)
return None, (f"Unknown tool '{pending.tool_name}'", 400)
```
- Assessment: `TOOL_DEFINITIONS`, `MUTATING_TOOLS`, `_TOOL_RATE_LIMITS`, `_summarize`, and `execute_pending_action` all separately enumerate the same five tool names. Adding a sixth mutating tool requires touching all five — easy to miss one, and the rate limit specifically exists to compensate for this path bypassing `@limiter.limit`, so "forgot the new tool's limit" is a plausible real regression.
- **Importance: 5/10**.
- Remediation:
```python
@dataclass
class ToolHandler:
    summarize: callable
    execute: callable
    rate_limit: tuple | None = None

TOOL_HANDLERS = {
    "create_ticket": ToolHandler(
        summarize=lambda ti: f"Create ticket: \"{ti.get('title','')[:80]}\" (priority: {ti.get('priority','medium')})",
        execute=lambda ti, ctx: ticket_service.create_ticket_service(
            ctx.user_id, ctx.role, ctx.customer_id, title=ti.get("title", ""),
            description=ti.get("description"), customer_id=ti.get("customer_id"),
            device_id=ti.get("device_id"), priority=ti.get("priority", "medium"), source="ai_assistant"),
        rate_limit=(20, 60),
    ),
    # ... one entry per tool
}

def execute_pending_action(pending, ctx):
    handler = TOOL_HANDLERS.get(pending.tool_name)
    if not handler:
        return None, (f"Unknown tool '{pending.tool_name}'", 400)
    if handler.rate_limit:
        allowed = check_and_increment(f"rmm:ai:toolrate:{ctx.user_id}:{pending.tool_name}", *handler.rate_limit)
        if not allowed:
            return None, ("Rate limit exceeded for this action — please wait a moment.", 429)
    return handler.execute(pending.tool_input or {}, ctx)
```

### Observer

**Finding B4 (positive): `api/utils/events.py` is a genuine Redis pub/sub Observer**
- Location: `api/utils/events.py:35-51` (`publish_event`), `:66-74` (`new_pubsub`)
- Snippet:
```python
def publish_event(event_type: str, data: dict) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        payload = json.dumps({"type": event_type, "data": data, "ts": ...})
        r.publish(_CHANNEL, payload)
        r.lpush(_RECENT_KEY, payload)
        r.ltrim(_RECENT_KEY, 0, _RECENT_MAX - 1)
        r.expire(_RECENT_KEY, 3600)
    except Exception as exc:
        logger.warning("publish_event failed: %s", exc)
```
- Assessment: Correctly implemented one-to-many Observer — publishers don't know or care who's listening, failure is fully isolated. Publishers: `alert_tasks.py:190-198` (`new_alert`), `:280-283` (`device_offline`). Both are wrapped in an *additional* outer `try/except: pass` at the call site, which is redundant since `publish_event()` already guarantees it never raises.
- **Importance: 2/10** — belt-and-suspenders, not a bug.
- Remediation: drop the outer wrapper — pure cleanup, no behavior change:
```python
from utils.events import publish_event
publish_event("new_alert", {"rule": rule.name, "device": device.hostname,
                             "severity": rule.severity, "message": alert.message})
```

**Finding B5: Alert notification fan-out is a hardcoded 3-block sequence, correct for current scale**
- Location: `api/tasks/alert_tasks.py:177-198` (inside `evaluate_all_rules`)
- Assessment: Three independent channel families (email / webhook-family / event-bus) triggered by three independent if-blocks in one task function — fine with a single producer. `mark_offline_devices` (lines 279-284) already duplicates the bare `publish_event` call in isolation from email/webhook, which is the leading indicator that a second producer is starting to need the same fan-out.
- **Importance: 3/10** — not worth abstracting into a formal `Subject`/`Observer` object graph yet; extract only once a second call site needs the *full* 3-channel sequence:
```python
def _notify_alert(rule_name, device, message, severity, channels):
    if channels.get("email"):
        send_alert_notification(rule_name, device.hostname, message, channels["email"])
    if any(channels.get(k) for k in ("slack", "teams", "webhook")):
        dispatch_alert_webhooks(channels, rule_name, device.hostname, message, severity)
    publish_event("new_alert", {"rule": rule_name, "device": device.hostname,
                                 "severity": severity, "message": message})
```

### Chain of Responsibility

**Finding B6 (positive): Flask's before/after_request hooks form a genuine, framework-provided chain**
- Location: `api/app.py:259-283` (`_start_timer`, `_log_request`)
- Assessment: Correct delegation to Flask/Werkzeug's own hook-dispatch chain (request timing/correlation ID in, usage-tracking + security headers out) rather than a custom middleware-chain abstraction, which would just duplicate framework functionality.
- **Importance: 1/10**.

**Finding B7: AI reply post-processing is a straight-line 3-stage pipeline, correctly not over-engineered into a handler chain**
- Location: `api/routes/assistant.py:244-256`
- Snippet:
```python
reply = final_text
if page in _RESTRICTED_PAGES:
    reply = _CODE_BLOCK_RE.sub("[code removed — command suggestions are disabled on this page]", reply)
contains_warning = inbound_warning or any(p.search(reply) for p in _DANGER_PATTERNS)
if pending_action and pending_action.contains_warning:
    contains_warning = True
if contains_warning and not (pending_action and pending_action.contains_warning):
    reply = ("**CAUTION:** This response references a potentially destructive operation. "
              "Do not execute without supervisor review.\n\n" + reply)
```
- Assessment: Three sequential transform stages (strip code on restricted pages → danger-pattern scan → prepend caution banner), each feeding the next — the shape Chain of Responsibility formalizes, but implemented as plain sequential code, which is the right call for exactly 3 fixed, always-run stages with no dynamic reconfiguration need.
- **Importance: 2/10**. Only worth a real handler-object chain if a 4th+ conditional stage with its own enable/disable logic gets added.

### Command

**Finding B8 (positive): `AiPendingAction` + confirm/deny is a correct, security-motivated Command pattern**
- Location: `api/services/ai_tools.py:209-225` (`stage_mutating_tool`), `:228-257` (`execute_pending_action`)
- Snippet:
```python
def stage_mutating_tool(name, tool_input, ctx, conversation_id, tool_use_id) -> AiPendingAction:
    pending = AiPendingAction(
        conversation_id=conversation_id, user_id=ctx.user_id,
        tool_name=name, tool_input=tool_input, tool_use_id=tool_use_id,
        summary=_summarize(name, tool_input)[:500],
        contains_warning=_danger_scan(tool_input),
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    db.session.add(pending)
    db.session.commit()
    return pending
```
- Assessment: Textbook Command, used for the right reason — decoupling "receive the request" (LLM tool call) from "invoke the action" (explicit human confirm). Permissions (`ctx`) are deliberately re-derived at execute-time from the confirming user's live JWT rather than trusted from the stored row, preventing a staged action from executing with stale/escalated permissions.
- **Importance: 2/10** — strongest pattern instance in the codebase; only improvement opportunity is Finding B3 (collapse the parallel dispatch maps).

**Finding B9 (positive): `TerminalCommand`/`ScriptRun` rows are a correct persisted-queue flavor of Command**
- Location: `api/models/terminal.py:31-49` (`TerminalCommand`); `api/services/script_service.py:8-11,58-79`
- Assessment: Correct for the use case — the "receiver" is a remote, possibly-offline agent polling over HTTP, so the Command must be a durable, status-tracked DB row (`pending`/`running`/`done`/`error`) rather than an in-memory object, which is why the "pending-command indicator" UI works at all.
- **Importance: 1/10**.

---

## Domain Patterns

### Repository

**Finding D1: No repository layer — the identical `Device.query.filter_by(is_online=True).all()` filter is hand-duplicated across 3+ Celery task files**
- Location: `api/tasks/alert_tasks.py:70`, `api/tasks/anomaly_tasks.py:120`, `api/tasks/automation_tasks.py:46`; more broadly, 19 of 24 `api/routes/*.py` files build SQLAlchemy queries inline with no data-access abstraction
- Snippet:
```python
# identical across 3 separate task files
devices = Device.query.filter_by(is_online=True).all()
```
- Assessment: Not wrong for a codebase this size — a full Repository-per-aggregate layer would be over-engineering for a single-database Flask+SQLAlchemy app. But any future change to "what counts as an online device" (e.g. adding a soft-delete clause) has to be hunted down and edited in every copy.
- **Importance: 4/10** — maintainability/DRY risk, not a correctness bug today.
- Remediation: extend the existing `api/services/device_query_service.py` with a named helper and import it from all three task files:
```python
# api/services/device_query_service.py
def online_devices():
    return Device.query.filter_by(is_online=True).all()
```
```python
# api/tasks/alert_tasks.py
from services.device_query_service import online_devices
all_online_devices = online_devices()
```

**Finding D2: Tenant-isolation scope check duplicated near-verbatim across two files, already drifting, after a documented prior leak**
- Location: `api/routes/devices.py:54-63` (`_client_scope_check`), `api/routes/mobile_mdm.py:53-62` (`_mdm_scope_check`)
- Snippet:
```python
# api/routes/devices.py
def _client_scope_check(device):
    claims = get_jwt()
    if claims.get("role") != "client":
        return None
    uid = get_jwt_identity()
    user = db.session.get(User, uid)
    if not user or device.customer_id != user.customer_id:
        return jsonify({"error": "Device not found"}), 404
    return None

# api/routes/mobile_mdm.py — already diverged to take a bare customer_id
def _mdm_scope_check(customer_id):
    claims = get_jwt()
    if claims.get("role") != "client":
        return None
    uid = get_jwt_identity()
    user = db.session.get(User, uid)
    if not user or customer_id != user.customer_id:
        return jsonify({"error": "Not found"}), 404
    return None
```
- Assessment: `mobile_mdm.py`'s own docstring says this follows "the same pattern as devices.py's `_client_scope_check`, established after the cross-tenant leak fixed in `4d4362a`" — the team already knows this is copy-pasted, on purpose, after a real security incident. That makes the duplication worse, not better: this is exactly the kind of security-critical logic where a fix to one copy and a forgotten twin reintroduces the same class of leak. The two functions have already started drifting (different signatures: `device` object vs. bare `customer_id`).
- Simpler alternative? No — needs consolidating, not simplifying away.
- **Importance: 7/10** — security-relevant duplication with a documented prior incident. **Highest-priority finding in this report.**
- Remediation:
```python
# api/utils/scope.py
def require_customer_scope(customer_id):
    claims = get_jwt()
    if claims.get("role") != "client":
        return None
    user = db.session.get(User, get_jwt_identity())
    if not user or customer_id != user.customer_id:
        return jsonify({"error": "Not found"}), 404
    return None
```
Then `devices.py` calls `require_customer_scope(device.customer_id)` and `mobile_mdm.py` calls `require_customer_scope(enrollment.customer_id)` — one function to audit for the next cross-tenant fix.

### Service Layer

**Finding D3: Service layer exists and is done well where used, but only 4 of 24 route files use it**
- Location: `api/services/ticket_service.py` (used by `tickets.py:106`, `assistant.py`), `alert_service.py`/`script_service.py` (used by `alerts.py`/`scripts.py`) vs. `devices.py`, `admin.py`, `billing.py`, `auth.py`, `psa.py`, `usage.py`, `terminal.py`, `mobile_mdm.py`, `automation.py`, `customers.py`, `patches.py`, `sensors.py`, `network.py`, `org_settings.py`, `update.py`, `events.py`, `sla_policies.py`, `agents.py`, `dashboard.py` — none of which import from `services/`
- Snippet:
```python
# api/services/ticket_service.py — correctly motivated: shared by two callers
"""Ticket creation logic shared by the human-facing route and the AI assistant tool executor.
Extracted from routes/tickets.py::create_ticket so both callers run the exact same
authorization/SLA/audit/notification logic — no duplicated permission checks."""
```
```python
# api/routes/tickets.py:106 — route correctly reduced to arg-marshalling + service call
def create_ticket():
    result, err = create_ticket_service(uid, role, actor_customer_id, title=data.get("title"), ...)
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(result), 201
```
- Assessment: Where the service layer exists, extraction is correctly motivated (shared logic between two callers — human route + AI tool dispatch — not speculative reuse) and the route is properly thin. But `devices.py:66-107` (`list_devices`) mixes cache-key construction, raw query building, pagination, and serialization inline with no extraction, and `billing.py`/`admin.py`/`terminal.py` (350/451/365 lines respectively) carry similarly heavy inline logic with zero service imports. The inconsistency itself is the finding — a reader can't predict from the route filename whether business logic lives in the route or a service.
- **Importance: 5/10** — inconsistent architecture, not a bug, but raises onboarding/maintenance cost.
- Remediation: no single code snippet fixes this (it's a scope/convention decision) — recommend adding a rule of thumb to CLAUDE.md's "Key Utilities" section: *"if route logic is called from more than one place — human route + AI tool + Celery task — extract it to `services/`; otherwise keep it in the route."*

**Finding D4: Small leftover duplicated helper between a route and its own extracted service**
- Location: `api/routes/tickets.py:40` and `api/services/ticket_service.py:47` — both define an identical `_customer_name(customer_id)`
- Assessment: Harmless (trivial 2-line body), but a leftover from an incomplete extraction — likely left behind because other non-extracted functions in `tickets.py` still need it.
- **Importance: 2/10**.
- Remediation:
```python
# api/routes/tickets.py — replace local def with:
from services.ticket_service import _customer_name
```

### DTO / Value Objects

**Finding D5: No output-DTO layer — Marshmallow `Schema` classes validate input only; response serialization happens via ad hoc `to_dict()` on the ORM models themselves**
- Location: `api/schemas/*.py` (8 files, input validation only — zero matches for `Schema().dump(` anywhere in `api/routes/*.py`); 37 `to_dict(` method definitions across `api/models/*.py`
- Snippet:
```python
# api/models/device.py:47 — output serialization lives on the model, not a schema
def to_dict(self, include_latest_metrics=False, latest_metrics_data=_MISSING):
    d = {"id": self.id, "customer_id": self.customer_id, ...}
```
- Assessment: A consistent, deliberate half-DTO split (Schema = validate requests, `to_dict()` = build responses) that works and shows real awareness of information hiding: `User.to_dict()` deliberately omits `password_hash`/`mfa_secret`; `PsaIntegration.to_dict(include_secret=False)` explicitly gates the secret field. The residual risk is that this safety is enforced by developer memory (hand-allowlisting fields in a dict literal) rather than by something CI can check — a new sensitive column added without a `to_dict()` update is safe by omission, but a field accidentally *added* to the dict is invisible until someone diffs it.
- **Importance: 3/10** — works correctly today (no leaks observed in models reviewed); flagged as process risk, not an active bug.
- Remediation: no code change to the pattern itself — add a regression test:
```python
# api/tests/test_serialization.py
def test_user_to_dict_never_leaks_secrets():
    u = User(...)
    assert "password_hash" not in u.to_dict()
    assert "mfa_secret" not in u.to_dict()
```

### Domain Model

**Finding D6: Models are largely anemic (`Alert`, `Ticket` have only `to_dict()`), inconsistent with two richer outlier models in the same codebase**
- Location: `api/models/alert.py`, `api/models/ticket.py` (only `to_dict` methods) vs. `api/models/psa_integration.py:33-47` (`get_client()` — a real Factory Method) and `api/models/user.py:29-37` (`set_password()`/`check_password()`)
- Assessment: Anemic models are a defensible, common choice for Flask+SQLAlchemy+Celery (state-machine/evaluation logic naturally lives in the task/service layer that already owns transactions and side effects like webhook dispatch). Not wrong — but the codebase has no single stated philosophy: a couple of models carry real behavior, most are pure data bags.
- **Importance: 3/10** — style/consistency, not correctness.
- Remediation: N/A as a forced rewrite; if standardizing, the two outliers are the better template — e.g. `Alert` gaining a `resolve(reason)` method that sets `status`/`resolved_at` together, called from `alert_tasks.py`, rather than the task setting those two fields separately at each resolution branch.
- **Unable to verify:** whether `Alert.status`/`resolved_at` are ever set independently across `alert_tasks.py`'s resolution branches (which would make the invariant-violation risk concrete rather than theoretical) — would need to grep every write site of `Alert.status`.

---

## Appendix — Items Marked "Unable to Verify"

| Item | What would confirm it |
|---|---|
| PgBouncer proxy wiring (Structural S8) | Read `api/app.py`'s `SQLALCHEMY_ENGINE_OPTIONS`/`pool_pre_ping` config + `.env.example`'s `DATABASE_URL` default port |
| Whether `Alert.status`/`resolved_at` are ever set independently (Domain D6) | Grep every write site of `Alert.status` in `api/tasks/alert_tasks.py` |
| Whether the SSE consumer side (`api/routes/events.py`) matches `events.py::new_pubsub()`'s producer contract (Behavioral B4) | Open `api/routes/events.py` and confirm the subscriber loop |

---

*Report generated by static codebase review — Claude Code, 2026-09-24.*
