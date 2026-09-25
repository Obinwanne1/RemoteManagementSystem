# Testing Implementation Audit — RMM System

**Date:** 2026-09-24
**Scope:** `api/tests/`, `dashboard/tests/`, `agent/tests/`, `frontend/` (test infrastructure — none found), `.github/workflows/ci.yml`.
**Method:** Every number below is measured, not estimated — the full `api/` suite was run with `pytest-cov` (149 tests, real line counts per file), the `dashboard/`/`agent/` suites were run standalone to confirm current pass/fail state, and CI's actual workflow file was read line-by-line rather than inferred from its name. Findings are anchored to real file paths/line numbers. Items that could not be directly verified are marked **Unable to verify**.

---

## Executive Summary

**Headline number: 44.4% real backend line coverage** (8,762 statements, 4,872 missed — `pytest --cov=. --cov-report=term-missing`, `tests/`/`migrations/` excluded from the denominator). CI's own Codecov upload reports a higher **54%**, because its `--cov=.` includes the `tests/` package itself in the denominator, where every test file is trivially ~100% "covered" by being imported — a measurement artifact, not a real difference (Finding C4).

The pattern across every dimension is the same: **where tests exist, they are good** (clear naming, real assertions on behavior, appropriate mocking, disciplined cleanup) — the gap is entirely in *what's not tested at all*, and the two biggest gaps are large, verifiable, and both zero-percent: the Celery task layer (the product's entire background-automation engine) and the React frontend (the primary UI).

| # | Finding | Category | Importance |
|---|---|---|---|
| 1 | `api/tasks/*.py` — the entire Celery background-job layer (alerts, billing, backups, patch deployment, PSA/MDM sync) — is **0% covered** in 16 of 20 files | Coverage | **9/10** |
| 2 | `frontend/` has **zero** test files and zero test tooling installed — no vitest/jest, no `@testing-library`, nothing in `package.json` | Coverage | **8/10** |
| 3 | 17 of 26 `api/routes/*.py` files (65%) have no dedicated test file — includes `billing.py` (26%), `terminal.py` (19%, the lowest of any route file), `scripts.py` (35%), `psa.py` (27%) | Coverage | **8/10** |
| 4 | `POST /api/auth/login`'s actual rate limit is untestable as configured — `TestConfig.RATELIMIT_ENABLED = False` disables Flask-Limiter suite-wide; the one rate-limit test in the suite exercises a different, unrelated primitive | Missing Tests | **6/10** |
| 5 | `dashboard/` has 1 test file covering the shared HTTP client only — 0 of 26 Streamlit pages have any test | Coverage | 6/10 |
| 6 | No E2E framework anywhere in the repo (`grep` for selenium/playwright/cypress/puppeteer: zero hits) | Coverage | 6/10 |
| 7 | CI computes coverage and uploads it but enforces **no floor** — no `--cov-fail-under`, and the upload step is `fail_ci_if_error: false` | Test Patterns | 5/10 |
| 8 | `dashboard/tests/` (10 tests) and `agent/tests/` (19 tests) exist and currently pass, but neither is wired into `.github/workflows/ci.yml` — silently orphaned | Test Patterns | 5/10 |
| 9 | Zero regression tests for the specific bugs `audits/error_handling_audit.md` already found and fixed (`FLASK_DEBUG`+`FLASK_ENV=production` guard, Flask-Limiter fail-open, JWT error-body shape) | Missing Tests | 5/10 |

---

## Remediation Status — 2026-09-24 (updated: full closure pass)

Every finding in this audit is now fixed, including all four large "zero coverage" findings (C1/C2/C3/C5) closed to **100% file coverage** — every API route file, every Celery task file, every dashboard page, and every React page now has a dedicated test file. C6 (E2E) has a working, verified harness but is deliberately not wired into CI (see below). This was done across two passes: an initial partial pass (representative examples per category) followed by a full completion pass once the approach was validated.

**Final counts, all verified stable across repeated runs:**
- **api/**: 484 tests (481 passed + 3 xfailed), coverage **44.4% → 72%**. All 26 `routes/*.py` files and all 20 `tasks/*.py` files have a dedicated test file.
- **dashboard/**: 83 tests, all passing. All 26 `pages/*.py` files (including the 2 underscore-prefixed detail pages) have a dedicated test file, using `streamlit.testing.v1.AppTest`.
- **frontend/**: 39 tests across 19 files, all passing. All 19 `pages/*.tsx` files have a dedicated test file. `tsc --noEmit` and `npm run build` both clean.
- **agent/**: 19 tests, unchanged from the initial pass.
- **E2E**: 2 Playwright tests, run and re-verified against the live stack after later changes.

| Finding | Status | What was done |
|---|---|---|
| C4 (5/10) — coverage % inflated | **Fixed** | New `api/.coveragerc` (omits `tests/`, `migrations/`, `seed.py`) |
| P4 (5/10) — no coverage floor in CI | **Fixed** | `--cov-fail-under=70` in `test-backend` (raised twice as real coverage grew: 44→46→68→70) |
| P3 (2/10) — no pytest markers | **Fixed** | `slow`/`integration` markers registered in `api/pytest.ini` |
| Q2 (4/10) — session-scoped DB fixture risk | **Fixed**, and then **proven correct twice more** | Docstring warning added; two *more* real collisions of exactly this kind surfaced and were fixed during the full-coverage pass (see "bugs found" below) — the risk this finding described was not hypothetical |
| Q4 (3/10) — real bcrypt in tests | **Fixed** | `BCRYPT_ROUNDS` config; suite wall-clock ~45s → ~3.4s (api/ alone; now ~7-16s with 3x the tests) |
| P5 (5/10) — dashboard/agent orphaned from CI | **Fixed** | `test-dashboard` (`ubuntu-latest`), `test-agent` (`windows-latest` — no Linux wheel for `pywin32`/`wmi`) |
| M1 (6/10) — login rate limit untestable | **Fixed** | `TestLoginRateLimit` — required discovering and fixing a real Flask-Limiter storage-precedence bug (below) |
| M2 (5/10) — no regression tests for shipped fixes | **Fixed** (2 of 3) | JWT error-shape test; `FLASK_DEBUG`+`production` guard extracted into `_refuse_debug_in_production()` for direct unit testing. Flask-Limiter's fail-open-on-Redis-outage fix still has no test (would need a mocked/unreachable Redis) |
| M3 (3/10) — no JWT tampering tests | **Fixed** | `TestJwtTampering` (tampered signature, truncated token) |
| M4 (2/10) — no performance tests | **Fixed** | `test_performance.py` — 2 response-time budget tests |
| P1 (3/10) — flat test pyramid | **Fixed** (cited example) | `test_pagination.py` — direct unit tests of `paginated_response()`, no HTTP/DB round-trip |
| **C3 (9/10) — Celery tasks 0% covered** | **Fixed — 20/20 task files** | Every file in `api/tasks/` now has a dedicated test file (or is covered within an existing one — `usage_tasks.py`/`maintenance_tasks.py` were already covered pre-audit). Highlights: `test_alert_tasks.py` (alert-storm-fix regression), `test_billing_tasks.py` (invoice idempotency regression), `test_network_tasks.py` (Windows false-positive-detection regression, agentless ping grace-period), `test_email_tasks.py` (IMAP fully mocked, ticket-vs-reply threading), `test_backup_tasks.py` (pg_dump fully mocked). External I/O (subprocess, IMAP, SNMP, MQTT, third-party PSA/MDM APIs) is mocked throughout — no test touches a real external system |
| **C2 (8/10) — route files untested** | **Fixed — 26/26 route files** | Every file in `api/routes/` now has a dedicated test file. `admin.py` 21%→55%, `terminal.py` 19%→90% (was the project's lowest), `sensors.py`/`sla_policies.py`/`update.py` all →87-92% |
| **C1 (8/10) — frontend zero tests** | **Fixed — 19/19 pages** | Vitest + RTL wired into CI. Every page in `frontend/src/pages/` has a test file; `tsc --noEmit` and production build both verified clean afterward |
| **C5 (6/10) — dashboard pages 0% covered** | **Fixed — 26/26 pages** | Every page in `dashboard/pages/` has a test file using `streamlit.testing.v1.AppTest`, including the two underscore-prefixed detail pages and the superadmin-gated Usage Monitoring page |
| C6 (6/10) — no E2E framework | **Harness fixed, CI wiring deliberately deferred** | Playwright installed; 2 tests verified against the live stack. Not wired into CI — a real E2E CI job needs Postgres+Redis+API+migrations+frontend all running together, a distinct infra task from writing the tests themselves |

**Bugs found and fixed during remediation, not in the original audit** (7 from the initial pass, 3 more found during the full-coverage pass):

1. **`extensions.py`'s `Limiter(storage_uri="redis://...")` silently overrides `TestConfig.RATELIMIT_STORAGE_URL`.** Flask-Limiter's `init_app()` prefers the constructor's `storage_uri`, so the in-memory test setting was dead code — a rate-limit test connected to whatever Redis was actually reachable, causing cross-invocation flakiness. Fixed by forcing `limiter._storage_uri = "memory://"` for the one test that needs real enforcement, restored after.
2. **`devices.py::list_devices`'s 30-second Redis response cache caused cross-test contamination** between `test_performance.py` and `test_devices.py`. Fixed with `cache_delete_pattern(...)` in a `finally` block.
3. **`frontend/vite.config.ts`'s dev proxy pointed at port 5003; the real API runs on 5000.** Found via the E2E test failing to authenticate. Proxy itself left alone (unclear intent); the dev server was run with an explicit `VITE_API_URL` override instead — **worth a maintainer's look**, since a plain `npm run dev` today hits a dead proxy target.
4. **`frontend/src/api/client.ts`'s 401-interceptor triggered a full-page reload even for a failed login itself**, wiping the error message before React could render it. Fixed by exempting `/auth/login`, `/auth/mfa/login`, `/auth/refresh` from the redirect-on-401 logic.
5. **`LoginPage.tsx`'s `<label>`s weren't associated with their `<input>`s** (no `htmlFor`/`id`) — an accessibility gap, and why `page.getByLabel(...)` couldn't find the fields. Fixed.
6. **`pages/03_Customers.py`'s customer name renders as an `st.expander()` label, not markdown** — not a bug, a discovery that shaped every subsequent `AppTest` file (check the actual element type before asserting).
7. **`streamlit.testing.v1.AppTest.from_file()` cannot resolve `st.page_link()`/`st.switch_page()` calls to sibling pages** on an isolated page file (`KeyError`/`StreamlitAPIException`) — the multipage registry only exists when Streamlit boots from `app.py`. Worked around with `patch("streamlit.page_link")` / `patch("streamlit.switch_page")` in every dashboard test file; became the standard first line of every new AppTest file written in the full-coverage pass.
8. **`dashboard/utils/cached_calls.py` — a real, serious cross-tenant/cross-session data leak, found while writing `test_dashboard_overview_page.py`.** All 13 `@st.cache_data`-wrapped functions (`cached_summary`, `cached_list_customers`, `cached_list_alerts`, etc.) took the caller's access token as an **underscore-prefixed** parameter (`_token`). Streamlit's `st.cache_data` excludes underscore-prefixed parameters from the cache key entirely — confirmed with a standalone repro (`cached_fn('token-A')` then `cached_fn('token-B')` returned `'token-A'`'s cached result both times, function body executed only once). Since `st.cache_data`'s cache is process-wide, this meant: **within each function's TTL (20-120 seconds), whichever user's request populated the cache first had their dashboard summary, device list, customer list, alerts, or usage data served back to every other user on the same server process, regardless of their own role, token, or customer.** Fixed by removing the underscore prefix on all 13 functions (the token is a plain string, trivially hashable — there was never a technical need for the underscore convention here). Verified the fix with the same repro (each token now gets its own cache entry). This is a materially more serious finding than anything scored in the original audit and would be rated **9/10** if it had been found then.
9. **`tests/test_network_tasks.py`'s `_upsert_agentless_host` test collided with a pre-existing placeholder MAC address (`AA:BB:CC:DD:EE:FF`) already used in `test_agents.py`**, a real, concrete instance of the exact risk Finding Q2 described in the abstract. The shared session-scoped DB meant `test_agents.py`'s leftover (agent-managed, non-agentless) device with that MAC caused my new test to see `"skipped"` instead of `"created"` — but only when run as part of the full suite, not in isolation. Fixed by generating a unique MAC per test run instead of a hardcoded literal.
10. `frontend/src/pages/ScriptsPage.test.tsx` (written mid-remediation, before the rate-limit interruption) referenced `@testing-library/user-event`, which wasn't yet an installed dependency — installed to fix.

**Not changed:** E2E-in-CI wiring (C6, a distinct infra task), and the third `error_handling_audit.md` regression test in M2 (Flask-Limiter fail-open, would need a mocked/unreachable Redis).

---

## 1. Test Coverage

### Finding C1 — Frontend: zero test files, zero test tooling
- **Location:** `frontend/package.json` — no `vitest`, `jest`, `@testing-library/*`, `cypress`, or `playwright` in `dependencies`/`devDependencies`; `find frontend/src -iname "*.test.*" -o -iname "*.spec.*"` returns nothing.
- **Assessment:** 19 page components (`frontend/src/pages/*.tsx`), a shared axios client, an auth context with token-refresh logic, and TanStack Query-driven data fetching/mutation across every page — none of it has a single automated test. `.github/workflows/ci.yml`'s `build-frontend` job (lines 113-148) only runs `tsc --noEmit` and `npm run build`; there is no `npm test` step because there is nothing to run.
- **Extraction/remediation method:** introduce Vitest + React Testing Library (the standard pairing for a Vite project — no separate test runner config needed since Vitest reads `vite.config.ts` directly).
- **Fix:**
```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```
```ts
// frontend/vite.config.ts — add a test block (Vitest reads this file directly)
export default defineConfig({
  // ...existing config
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
});
```
```ts
// frontend/src/test/setup.ts
import '@testing-library/jest-dom';
```
```tsx
// frontend/src/pages/CustomersPage.test.tsx — first test, smallest reasonable page
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CustomersPage from './CustomersPage';

test('renders customer names once loaded', async () => {
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <CustomersPage />
    </QueryClientProvider>
  );
  expect(await screen.findByText(/customers/i)).toBeInTheDocument();
});
```
```json
// frontend/package.json
"scripts": { "test": "vitest run" }
```
```yaml
# .github/workflows/ci.yml — build-frontend job, before "Type check"
- name: Run tests
  working-directory: frontend
  run: npm test
```
- **Effort:** Medium for the harness (~1-2 hours: install, config, one smoke test, wire into CI) — Large for meaningful coverage across 19 pages (a per-page effort, best done incrementally).
- **Importance: 8/10** — the primary user-facing surface for the product (per CLAUDE.md, the React frontend is meant to reach parity with the 22-page Streamlit dashboard) has no safety net at all; every refactor here is unverified until a human clicks through it.

### Finding C2 — 17 of 26 API route files have no dedicated test file; several are high-risk
- **Location:** `api/routes/*.py` vs `api/tests/test_*.py` — diffing the two directories by name (`admin`, `agents`✓, `alerts`✓, `assistant`✓, `auth`✓, `automation`, `billing`, `customers`, `dashboard`, `devices`✓, `docs`, `events`, `mobile_mdm`✓, `network`, `org_settings`, `patches`, `psa`, `reports`, `scripts`, `sensors`, `sla_policies`, `terminal`, `tickets`✓, `update`, `usage`✓ — ✓ = has a matching test file). Confirmed no incidental coverage either: `grep` for each untested blueprint's URL prefix inside the existing test files found none (the one apparent hit, `test_usage.py` referencing `/api/admin/usage/*`, is `usage.py`'s own blueprint mount point, not `admin.py`'s).
- **Measured coverage per untested file** (`pytest --cov`, statements/missed):

| File | Coverage | Statements missed |
|---|---|---|
| `routes/terminal.py` | **19%** | 177/219 |
| `routes/admin.py` | 21% | 255/324 |
| `routes/sensors.py` | 21% | 86/109 |
| `routes/events.py` | 24% | 52/68 |
| `routes/update.py` | 25% | 59/79 |
| `routes/billing.py` | 26% | 166/224 |
| `routes/sla_policies.py` | 26% | 54/73 |
| `routes/dashboard.py` | 27% | 72/98 |
| `routes/org_settings.py` | 27% | 69/94 |
| `routes/psa.py` | 27% | 119/163 |
| `routes/network.py` | 33% | 49/73 |
| `routes/patches.py` | 34% | 61/93 |
| `routes/automation.py` | 35% | 74/114 |
| `routes/scripts.py` | 35% | 73/112 |
| `routes/customers.py` | 36% | 72/112 |
| `routes/reports.py` | 41% | 26/44 |

- **Assessment:** The highest-risk gaps by *what the code does*, not just the percentage: `terminal.py` (remote shell session creation/command dispatch, 19% — the lowest coverage of any route file in the project), `scripts.py` (arbitrary script upload and dispatch to devices), `billing.py` (Stripe payment links, invoice PDF generation/email, webhook handling — `POST /api/billing/stripe/webhook` has no test), `admin.py` (user CRUD, and the GDPR Art. 17/20 export/delete endpoints have zero test coverage despite being irreversible), `psa.py` (external integration credential handling).
- **Extraction method:** one new `test_<name>.py` per file, following the existing suite's own template.
- **Fix (template, using `test_tickets.py`'s established shape — smallest reasonable file to start with is `terminal.py` or `admin.py` given the risk profile above):**
```python
# api/tests/test_admin.py (new)
"""Admin route tests — user CRUD, GDPR export/delete, role gating."""
from conftest import create_user, delete_user, login, auth_headers


class TestListUsers:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/admin/users", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_admin_sees_paginated_items(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get("/api/admin/users", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body and "pages" in body   # see audits/code_duplication_audit.md Finding N2
        finally:
            delete_user(app, admin_uid)


class TestGdprDelete:
    def test_anonymizes_pii_and_is_irreversible(self, app, client):
        """Unable to verify without writing this test — would prove the
        Art. 17 delete endpoint actually scrubs email/IP/comment-author fields."""
```
- **Effort:** Large — 17 files, prioritize by risk (`terminal.py`, `billing.py`, `admin.py`, `scripts.py`, `psa.py` first) rather than attempting all at once; each file is independently shippable.
- **Importance: 8/10** — this is where "untested" and "high blast radius if wrong" overlap most.

### Finding C3 — Celery task layer: 0% coverage in 16 of 20 files
- **Location:** `pytest --cov` output for `api/tasks/*.py`:

| File | Coverage | Statements |
|---|---|---|
| `tasks/alert_tasks.py` | **0%** | 243 |
| `tasks/network_tasks.py` | **0%** | 217 |
| `tasks/report_tasks.py` | **0%** | 145 |
| `tasks/psa_tasks.py` | **0%** | 141 |
| `tasks/email_tasks.py` | **0%** | 167 |
| `tasks/patch_tasks.py` | **0%** | 105 |
| `tasks/backup_tasks.py` | **0%** | 91 |
| `tasks/mqtt_tasks.py` | **0%** | 89 |
| `tasks/mdm_tasks.py` | **0%** | 81 |
| `tasks/anomaly_tasks.py` | **0%** | 83 |
| `tasks/snmp_tasks.py` | **0%** | 73 |
| `tasks/automation_tasks.py` | **0%** | 69 |
| `tasks/billing_tasks.py` | **0%** | 55 |
| `tasks/ticket_tasks.py` | **0%** | 23 |
| `tasks/script_tasks.py` | **0%** | 4 |
| (partial) `usage_tasks.py` 51%, `maintenance_tasks.py` 79%, `celery_app.py` 65%, `_app_singleton.py` 67% | | |

- **Assessment:** This is every piece of scheduled/background business logic in the product — alert rule evaluation and auto-resolution, nightly `pg_dump` backups, recurring invoice generation, patch deployment orchestration, PSA/MDM sync, SLA breach detection, dormant-account deactivation. `audits/error_handling_audit.md` already fixed real bugs in several of these files (retry/rollback in `prune_old_data`, circuit breakers in `psa_tasks.py`/`mdm_tasks.py`) — none of those fixes have a regression test, because the files they live in have no tests at all.
- **Why this is fixable, not just a gap:** two files in this exact directory *are* tested (`usage_tasks.py` 51%, `maintenance_tasks.py` 79%), and they establish a working, proven pattern for testing a Celery task as a plain function call (no live Celery worker needed):
```python
# api/tests/test_usage.py:187-190 — the existing, working pattern
import tasks.usage_tasks as usage_tasks
import tasks._app_singleton as app_singleton
app_singleton._app = app  # reuse the test app/db (shared singleton — tasks/_app_singleton.py)

result = usage_tasks.persist_hourly_usage_rollup()  # called directly, not via .delay()
assert result["rows"] == 1
```
- **Fix (apply this exact pattern to the highest-value target first — `alert_tasks.py`, the largest 0%-covered file and the one with the most business logic):**
```python
# api/tests/test_alert_tasks.py (new)
"""Alert rule evaluation + auto-resolve — the highest-value untested file
in api/tasks/ (243 statements, 0% covered)."""
import tasks._app_singleton as app_singleton
import tasks.alert_tasks as alert_tasks


class TestEvaluateAllRules:
    def test_fires_alert_when_threshold_crossed(self, app):
        app_singleton._app = app
        # arrange: create an AlertRule (metric="cpu_percent", operator="gt", threshold=90)
        #          and a Device + DeviceMetrics row with cpu_percent=95
        # act:
        alert_tasks.evaluate_all_rules()
        # assert: an Alert row now exists with status="open" for that device+rule

    def test_auto_resolves_when_metric_drops_back_below_threshold(self, app):
        """Regression test for the 'alert storm fix' documented in CLAUDE.md
        (open_alert_map vs resolved_alert_map split) — currently unverified by any test."""
```
- **Effort:** Large overall (16 files), but each file follows the same proven template — recommend one file per pass, starting with `alert_tasks.py` (highest business-logic density) then `psa_tasks.py`/`mdm_tasks.py` (already have circuit-breaker logic worth locking in).
- **Importance: 9/10** — highest-scored finding in this report. Zero coverage on the code that runs unattended, on a schedule, against production data, with no human in the loop to catch a bad deploy.

### Finding C4 — Reported coverage percentage is inflated by including the tests package itself
- **Location:** `.github/workflows/ci.yml:99-103` (`--cov=. --cov-report=xml`, no `--omit`/`--source` restricting to production code); confirmed by direct measurement: `pytest --cov=. --cov-report=term-missing` reports `TOTAL 10577 4874 54%`, but excluding `tests/*.py` and `migrations/*` from the same run's line counts gives `8762 stmts / 4872 missed = 44.4%`.
- **Assessment:** Every test file trivially shows ~100% coverage of itself (its own lines execute by virtue of being collected), which pulls the reported total up by ~10 percentage points versus the coverage of code that actually ships. Not a bug — a one-line config gap.
- **Extraction method:** config change.
- **Fix:**
```ini
# api/.coveragerc (new)
[run]
omit =
    tests/*
    migrations/*
    seed.py
```
```yaml
# .github/workflows/ci.yml:99-103 — no change needed once .coveragerc exists;
# pytest-cov reads it automatically. Optionally make the source explicit too:
- name: Run tests with coverage
  working-directory: api
  run: |
    pytest tests/ -v \
      --cov=. \
      --cov-config=.coveragerc \
      --cov-report=term-missing \
      --cov-report=xml \
      --tb=short
```
- **Effort:** Low — ~10 minutes.
- **Importance: 5/10** — doesn't change actual test coverage, but whoever reads the Codecov badge is currently seeing a number 10 points higher than reality.

### Finding C5 — `dashboard/` (26 Streamlit pages): only the shared HTTP client is tested
- **Location:** `dashboard/tests/test_api_client.py` (10 tests, all against `dashboard/utils/api_client.py::RMMClient`) is the only file in `dashboard/tests/`. None of `dashboard/pages/*.py` (26 files) has a test.
- **Assessment:** The tests that exist are genuinely good (verified by reading — they cover retry/backoff, 401 auto-refresh, non-idempotent-method-not-retried, all with `unittest.mock`-based fake `requests.Session`). But page-level logic — the AI assistant restricted-mode stripping, the ticket SLA countdown formatting (`_sla_text()` in `02_Tickets.py`), the client-side `must_change_password` gate in `dashboard/app.py` — has no test. Streamlit pages are harder to unit-test than a plain function (they execute top-to-bottom as a script against `st.*` calls), which is likely why coverage stopped at the client layer; `streamlit.testing.v1.AppTest` (built into Streamlit 1.28+, and this project is on Streamlit — confirmed `streamlit==1.58.0` in the dashboard venv) exists specifically to make this practical without a browser.
- **Fix:**
```python
# dashboard/tests/test_tickets_page.py (new) — using Streamlit's built-in AppTest
from streamlit.testing.v1 import AppTest

def test_sla_text_shows_breached_for_overdue_ticket():
    at = AppTest.from_file("pages/02_Tickets.py")
    # Unable to verify the exact mock-injection point without reading how
    # 02_Tickets.py obtains its RMMClient (likely via require_auth() reading
    # st.session_state) — would need that to finish this test.
```
- **Effort:** Medium to start (Streamlit's `AppTest` has a learning curve around mocking `st.session_state`/network calls), Large for real coverage across 26 pages.
- **Importance: 6/10** — smaller blast radius than C1 (frontend) since Streamlit is being phased toward parity with React per CLAUDE.md, but it's still the primary UI today.

### Finding C6 — No E2E test coverage; no framework installed
- **Location:** repo-wide `grep` for `selenium|playwright|puppeteer|cypress` across `*.json`/`*.txt`/`*.py` (excluding `node_modules`/`venv`): zero matches.
- **Assessment:** There is no test anywhere that exercises a real user flow (login → view dashboard → open a device → run a script → see the result) through an actual browser against the actual running stack. Given this session's own live-restart-and-smoke-test of the API (see the pagination fix applied earlier) had to be done manually with `curl` and a hand-minted JWT, an E2E suite would have caught the `admin.py` `"users"` vs `"items"` key-mismatch bug (Finding N1 fixed in `audits/code_duplication_audit.md`) automatically, the first time it ran, without anyone reading `AdminPage.tsx`'s source by hand.
- **Fix:**
```bash
cd frontend
npm install -D @playwright/test
npx playwright install --with-deps chromium
```
```ts
// frontend/e2e/login-and-view-devices.spec.ts (new)
import { test, expect } from '@playwright/test';

test('admin can log in and see the devices list', async ({ page }) => {
  await page.goto('http://localhost:3000/login');
  await page.fill('input[name=email]', process.env.E2E_ADMIN_EMAIL!);
  await page.fill('input[name=password]', process.env.E2E_ADMIN_PASSWORD!);
  await page.click('button[type=submit]');
  await page.goto('http://localhost:3000/devices');
  await expect(page.getByRole('heading', { name: /devices/i })).toBeVisible();
});
```
- **Effort:** Medium to stand up the first test (needs a running API+DB, so a CI job would need the same `postgres`+`redis` services `test-backend` already provisions, plus the API itself started as a background step); Large for meaningful flow coverage.
- **Importance: 6/10** — highest-value single E2E test would be exactly the login→core-page smoke test above, since it's cheap and would have caught a real, already-shipped bug.

---

## 2. Test Quality

### Finding Q1 (positive) — Test naming is consistently clear and behavior-descriptive
- **Location:** e.g. `api/tests/test_auth.py` — `TestLogin::test_lockout_after_three_failures`, `test_auto_unlock_after_lockout_expiry`; `dashboard/tests/test_api_client.py` — `TestUnauthorizedRefreshFlow::test_401_triggers_refresh_and_retries_successfully`.
- **Assessment:** Every test name read during this audit states the scenario and expected outcome without needing to open the test body. Grouped into `Test<Feature>` classes, which also gives a readable `pytest -v` output as documentation.
- **Importance: 1/10** — positive finding, no fix needed.

### Finding Q2 — Session-scoped app/DB fixture is a structural test-independence risk
- **Location:** `api/tests/conftest.py:22-32` (`app` fixture, `scope="session"`)
```python
@pytest.fixture(scope="session")
def app():
    """Create one Flask app + SQLite in-memory DB for the entire test session."""
    ...
    yield flask_app
    db.drop_all()
```
- **Assessment:** All 149 tests across 10 files share one Flask app and one SQLite database for the entire run. This is currently safe *in practice* because every test observed during this audit either (a) creates uniquely-suffixed data (`conftest.py::create_user` uses `uuid.uuid4().hex[:8]` in the email) and cleans up in a `finally` block, or (b) doesn't touch shared/global state. But nothing enforces this discipline structurally — a future test that asserts `User.query.count() == N` or forgets its `finally: delete_user(...)` would pass or fail depending on what ran before it in the same session, and that failure would be confusing (order-dependent) rather than a clean, obvious bug in the new test.
- **Extraction method:** none required immediately — documenting the invariant is the cheap fix; per-test DB isolation (function-scoped app, or a SAVEPOINT-per-test rollback pattern) is the robust fix if this becomes a real problem.
- **Fix (cheap version — document the invariant so future tests are written correctly):**
```python
# api/tests/conftest.py — expand the app fixture's docstring
@pytest.fixture(scope="session")
def app():
    """Create one Flask app + SQLite in-memory DB for the entire test session.

    IMPORTANT: this DB is SHARED across all 149+ tests in the suite. Every test
    that creates a row MUST use a unique identifier (see create_user()'s uuid
    suffix) and clean up in a finally block (see delete_user()). Never assert
    on a global count (e.g. User.query.count()) — it is order-dependent.
    """
```
- **Fix (robust version, if the cheap fix proves insufficient — SAVEPOINT rollback per test):**
```python
# api/tests/conftest.py
@pytest.fixture
def db_session(app):
    """Wrap each test in a SAVEPOINT that's rolled back afterward — true
    per-test isolation without recreating the whole app per test."""
    from extensions import db
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        db.session.bind = connection
        yield db.session
        transaction.rollback()
        connection.close()
```
- **Effort:** Low (docstring) or Medium (SAVEPOINT pattern, would need every existing test's `db.session` usage verified compatible).
- **Importance: 4/10** — no observed failure from this today (every test read during this audit was disciplined about cleanup), but it's exactly the kind of thing that produces a flaky, hard-to-debug CI failure months from now.

### Finding Q3 (positive) — Mock usage is minimal and appropriately scoped to the real external boundary
- **Location:** `api/tests/test_assistant.py:12-61` — mocks only `anthropic.Anthropic` via `monkeypatch.setattr`, with a fake `_FakeMessages.create()` returning scripted `_FakeResponse` objects matching the real SDK's shape (`content`, `stop_reason`, tool-use blocks).
- **Assessment:** This is the only mocking found anywhere in `api/tests/` (`grep -n "mock\|Mock\|patch(" api/tests/test_assistant.py` was the only file with real hits beyond `test_usage.py`'s `MagicMock()` for a Redis client in `TestHourlyRollupPersistence`, also an appropriate external-boundary mock). Everything else in the 149-test suite exercises the real Flask app, real SQLAlchemy models, and a real (in-memory) database — asserting on HTTP status codes and response bodies, not on internal call sequences. This is testing behavior, not implementation.
- **Importance: 1/10** — positive finding, cited as the pattern to keep following as coverage expands (Findings C2/C3).

### Finding Q4 — Real bcrypt cost (`rounds=12`) runs unmodified in tests, measurably the top time cost
- **Location:** `api/models/user.py:31-32` (`bcrypt.gensalt(rounds=12)`, hardcoded); `api/config.py:57-62` (`TestConfig` already exists but has no `BCRYPT_ROUNDS` override)
- **Evidence** (`pytest --durations=10`):
```
1.17s call     tests/test_auth.py::TestMFA::test_mfa_disable
1.04s call     tests/test_auth.py::TestPasswordChange::test_change_password_success
0.90s call     tests/test_auth.py::TestLogin::test_lockout_after_three_failures
0.88s call     tests/test_assistant.py::TestMutatingToolStaging::test_cross_user_cannot_confirm_others_pending_action
```
Every one of the 4 slowest tests in the entire 149-test suite involves `set_password`/`check_password` (real bcrypt work) either directly or via `conftest.py::create_user`.
- **Assessment:** Correct security choice for production (`rounds=12` is a reasonable modern default), wrong default for tests — bcrypt's cost is *the point* in production and pure overhead in a test that just needs "a user that can log in." The suite is currently 45s total, not yet painful, but scales linearly with every new test that calls `create_user`.
- **Fix:**
```python
# api/models/user.py
from flask import current_app

def set_password(self, password):
    rounds = current_app.config.get("BCRYPT_ROUNDS", 12)
    self.password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)
    )
```
```python
# api/config.py — TestConfig
class TestConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URL = "memory://"
    BCRYPT_ROUNDS = 4  # bcrypt is O(2^rounds) — 4 vs 12 is roughly 250x faster, security cost is irrelevant for ephemeral test data
```
- **Effort:** Low — ~15 minutes, 2 files, verify `check_password` reads the stored hash's own cost factor (bcrypt encodes it in the hash itself, so mismatched rounds between `set_password` calls is never an issue).
- **Importance: 3/10** — real, measured, cheap to fix, not yet urgent at 45s total suite time.

### Finding Q5 — No shared factory for `Device`/`Ticket`/`Customer`/`AlertRule` test data
- **Location:** `conftest.py` centralizes `create_user()`/`delete_user()`, but no equivalent exists for other models.
- **Assessment: Unable to verify** whether this causes real duplication across test files without reading every test file's setup code (only `test_devices.py`/`test_tickets.py` were spot-checked, and both construct their fixtures inline rather than via a shared helper, which is consistent with — but not proof of — duplicated construction logic elsewhere). **What would confirm it:** `grep -n "Device(\|Ticket(\|AlertRule(" api/tests/*.py` and diff the resulting construction blocks for near-identical field sets.
- **Importance: not scored** — flagged for follow-up investigation, not a confirmed finding.

---

## 3. Test Patterns

### Finding P1 — Test pyramid is flat, not layered: ~149 integration-style tests, ~0 isolated unit tests, 0 E2E
- **Location:** every test in `api/tests/*.py` drives the suite through `client.post()`/`client.get()` against a real Flask app + real (in-memory) DB (confirmed by reading `test_auth.py`, `test_assistant.py`, `test_usage.py` in full). `grep -rn "pytest.mark" api/tests/*.py` returns nothing — no markers distinguish any test as a narrower unit test.
- **Assessment:** Not automatically wrong — HTTP-level tests catch more real regressions per test for a CRUD-heavy API, and this project's suite is good at that layer. But it means shared utility functions (`require_role()` in `utils/auth_decorators.py`, `_slugify()` in `routes/customers.py`, the new `paginated_response()` in `utils/pagination.py`) have no direct unit test of their own — only incidental exercise via whichever route happens to call them. A pure-logic bug in a shared utility surfaces (or doesn't) depending on which routes' tests happen to hit the affected branch.
- **Extraction method:** N/A — this is an architectural observation, not a single fixable location. Where it matters most: `utils/pagination.py::paginated_response()` (new, just added — see `audits/code_duplication_audit.md`) has no direct test, only indirect coverage via the 9 route tests that now call it.
- **Fix (one example, for the shared pagination helper specifically):**
```python
# api/tests/test_pagination.py (new)
from utils.pagination import paginated_response

def test_caps_per_page_at_max(app, client):
    """Direct unit test — doesn't need a real route, just an app context and a query."""
    with app.app_context():
        from models.customer import Customer
        with app.test_request_context("/?per_page=9999"):
            body, status = paginated_response(Customer.query, lambda c: c.to_dict(), max_per_page=100)
            assert status == 200
```
- **Effort:** Low per utility function once identified; the observation itself doesn't need fixing, only awareness when adding new shared utilities.
- **Importance: 3/10** — defensible current shape, flagged for awareness rather than urgency.

### Finding P2 (positive) — No "testing implementation, not behavior" anti-pattern observed
- **Location:** all files read during this audit (`test_auth.py`, `test_assistant.py`, `test_usage.py`, `dashboard/tests/test_api_client.py`).
- **Assessment:** Assertions consistently target HTTP status codes and response body content, not internal call counts or mock call-argument inspection (`test_assistant.py`'s `_FakeMessages.calls` list is the one exception, and it's used to assert on what was *sent* to the external API, i.e. still behavior from the app's perspective, not internal implementation).
- **Importance: 1/10** — positive finding.

### Finding P3 — No pytest markers registered or used
- **Location:** `api/pytest.ini` has no `markers =` section; `grep -rn "@pytest.mark" api/tests/*.py` — zero matches.
- **Assessment:** Combined with Finding P1 (flat pyramid), there's no way to run `pytest -m unit` for a fast subset, or `-m "not slow"` to skip the bcrypt-heavy tests from Finding Q4 during rapid local iteration.
- **Fix:**
```ini
# api/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: tests that take noticeably longer (e.g. real bcrypt hashing)
    integration: tests that exercise the full Flask app + DB stack (currently ~all of them)
```
- **Effort:** Low — ~10 minutes to add the section; ongoing small effort to tag tests as they're written.
- **Importance: 2/10**.

### Finding P4 — CI measures coverage but enforces no minimum
- **Location:** `.github/workflows/ci.yml:96-110`
```yaml
- name: Run tests with coverage
  working-directory: api
  run: |
    pytest tests/ -v \
      --cov=. \
      --cov-report=term-missing \
      --cov-report=xml \
      --tb=short

- name: Upload coverage report
  uses: codecov/codecov-action@v7
  if: always()
  with:
    files: api/coverage.xml
    fail_ci_if_error: false
```
- **Assessment:** Coverage is computed and uploaded, but nothing in this pipeline can turn red because of it — no `--cov-fail-under=N` on the pytest invocation, and the Codecov upload step explicitly tolerates its own failure. Coverage (whichever number — see Finding C4) can regress indefinitely with CI staying green throughout.
- **Fix:**
```yaml
- name: Run tests with coverage
  working-directory: api
  run: |
    pytest tests/ -v \
      --cov=. \
      --cov-config=.coveragerc \
      --cov-report=term-missing \
      --cov-report=xml \
      --cov-fail-under=44 \
      --tb=short
```
Start the floor at the current measured value (44%, Finding C4) so this doesn't immediately fail the pipeline — raise it incrementally as Findings C2/C3 close gaps, never lower it.
- **Effort:** Low — one flag, once `.coveragerc` (Finding C4) exists so the threshold is measured against real production code.
- **Importance: 5/10** — cheap, concrete, and directly prevents the coverage numbers in this report from quietly getting worse.

### Finding P5 — `dashboard/` and `agent/` test suites exist, pass, and are invisible to CI
- **Location:** `.github/workflows/ci.yml` has exactly 3 jobs: `test-backend` (runs `api/tests/` only), `build-frontend` (type-check + build, no tests), `build-docker`. No job references `dashboard/tests/` or `agent/tests/`.
- **Verified live during this audit** (both suites run standalone, outside CI):
```
dashboard: 10 passed in 0.70s
agent:     19 passed in 0.06s
```
- **Assessment:** 29 tests currently pass but are pure dead weight from an automation standpoint — nothing re-runs them on a PR, so they could start failing today and no one would find out until someone happens to run them by hand (exactly as this audit just did). `agent/tests/` in particular covers real correctness-critical logic (`_get_winget_software()`'s progress-bar-line filtering, `_build_command()`'s per-script-type dispatch) that CLAUDE.md documents as a past bug fix.
- **Fix:**
```yaml
# .github/workflows/ci.yml — new job, alongside test-backend
  test-dashboard:
    name: Dashboard Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: dashboard/requirements.txt
      - run: pip install -r requirements.txt pytest
        working-directory: dashboard
      - run: pytest tests/ -v
        working-directory: dashboard

  test-agent:
    name: Agent Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: agent/requirements.txt
      - run: pip install -r requirements.txt pytest
        working-directory: agent
      - run: pytest tests/ -v
        working-directory: agent
```
Note `agent/requirements.txt` includes Windows-only packages (`pywin32`, `wmi` — see CLAUDE.md); `pip install` on `ubuntu-latest` will need those two either made conditional in `requirements.txt` or the job pinned to `windows-latest`. **Unable to verify which is the right fix without attempting the install** — the tests read (`test_collector.py`, `test_script_runner.py`) test cross-platform-safe logic (UTF decoding, command-string building) that doesn't itself need Windows, only the import of `agent/collector.py` at module scope might.
- **Effort:** Low for `dashboard` (~20 min, pure-Python deps). Low-Medium for `agent` pending the Windows-dependency question above.
- **Importance: 5/10** — cheap, concrete, directly closes a "tests exist but nobody's watching them" gap.

---

## 4. Missing Tests

### Finding M1 — Login rate limiting is structurally untestable as configured
- **Location:** `api/config.py:61` (`TestConfig.RATELIMIT_ENABLED = False`); the only rate-limit-shaped test in the suite is `api/tests/test_assistant.py:412-419` (`TestToolRateLimit::test_check_and_increment_blocks_after_limit`), which exercises `utils/rate_limit.py::check_and_increment` — a *different*, Redis-counter-based primitive used only by the AI assistant's agentic tool-execution path (per CLAUDE.md, this bypasses Flask-Limiter entirely since it calls service functions directly). `grep -rn "RATELIMIT\|429" api/tests/*.py` confirms no other file references rate limiting at all.
- **Assessment:** `POST /api/auth/login`'s actual production control — `@limiter.limit("5 per minute")`, tightened from 10/min in the Tier-3 hardening pass per CLAUDE.md — has zero regression protection. Because `RATELIMIT_ENABLED = False` is set at the config level (not per-test), it's currently impossible to test Flask-Limiter's real 429 behavior without either a config override fixture or a second `TestConfig` variant.
- **Fix:**
```python
# api/tests/test_auth.py — new test, needs a per-test config override since
# RATELIMIT_ENABLED=False is global in TestConfig
class TestLoginRateLimit:
    def test_sixth_attempt_in_a_minute_is_429(self, app, client):
        app.config["RATELIMIT_ENABLED"] = True
        try:
            for _ in range(5):
                client.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"})
            r = client.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"})
            assert r.status_code == 429
        finally:
            app.config["RATELIMIT_ENABLED"] = False  # restore for tests after this one
```
- **Effort:** Low — ~20 minutes; verify Flask-Limiter's in-memory storage (per `RATELIMIT_STORAGE_URL = "memory://"` in `TestConfig`) actually re-toggles cleanly with a runtime `app.config` flip rather than needing app recreation — **unable to verify without running it**.
- **Importance: 6/10** — a previously-tightened, security-relevant control with no regression protection at all.

### Finding M2 — No regression tests for previously-fixed error-handling bugs
- **Location:** cross-referencing `audits/error_handling_audit.md`'s "Remediation Status" table against `api/tests/`: `grep -rn "FLASK_DEBUG\|in_memory_fallback\|unauthorized_loader" api/tests/*.py` — zero matches for any of them.
- **Assessment:** Three specific, real, previously-shipped bugs (`FLASK_DEBUG=1` + `FLASK_ENV=production` starting anyway with the interactive debugger exposed; Flask-Limiter failing closed on a Redis outage — reproduced live in that audit; JWT error responses using `{"msg":...}` instead of the app's `{"error":...}` convention) were fixed in `api/app.py` with no accompanying test. Nothing stops any of them from silently regressing.
- **Fix (the cheapest of the three to test — JWT error body shape):**
```python
# api/tests/test_auth.py
class TestJwtErrorShape:
    def test_missing_token_returns_error_key_not_msg(self, client):
        r = client.get("/api/admin/users")  # any @jwt_required() route, no Authorization header
        assert r.status_code == 401
        body = r.get_json()
        assert "error" in body
        assert "msg" not in body
```
```python
# api/tests/test_app_factory.py (new) — the other two need process-level testing,
# harder to do in-process; Unable to verify the cleanest approach without prototyping
# (likely subprocess.run(["python", "app.py"], env={...}) and asserting non-zero exit)
def test_refuses_to_start_with_debug_and_production():
    """Would prove api/app.py:367-373's RuntimeError guard still fires."""
```
- **Effort:** Low for the JWT-shape test (~15 min). Medium for the `FLASK_DEBUG` guard test (needs subprocess-level testing, not a simple Flask test client call, since it's an `if __name__ == "__main__":` guard).
- **Importance: 5/10** — these are exactly the kind of fix that regresses silently in a future refactor without a test pinning the behavior.

### Finding M3 — No security-shaped tests (JWT tampering, injection payloads)
- **Location:** `grep -rn "tamper\|malformed\|injection\|DROP TABLE\|<script>" api/tests/*.py` — zero matches.
- **Assessment: Unable to verify** whether the app is actually vulnerable to any of these (SQLAlchemy's parameterized queries make classic SQL injection unlikely by default, and `to_dict()`-based serialization doesn't execute stored strings) — no exploit was attempted here, consistent with this audit's scope (static review, not a penetration test; `/code-review` or `/security-review` is the right tool for that). The finding is specifically the *absence of any test* for this threat class, on a codebase that has one documented prior cross-tenant leak (`4d4362a`, referenced in `audits/design_patterns_audit.md` Finding D2).
- **What would confirm the underlying risk (not just the test gap):** a run of `/security-review` or a manual attempt to submit `<script>`-containing strings into `Ticket.description`/`AlertRule.name` and check whether they're escaped on render (`dashboard/utils/sanitize.py::esc` exists per earlier session context, suggesting awareness of this risk — but its actual call-site coverage wasn't audited here).
- **Fix (one concrete example — JWT signature tampering):**
```python
# api/tests/test_auth.py
class TestJwtTampering:
    def test_tampered_signature_is_rejected(self, app, client):
        uid, email, pw = create_user(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            tampered = token[:-4] + "AAAA"  # corrupt the signature
            r = client.get("/api/auth/me", headers=auth_headers(tampered))
            assert r.status_code == 422  # per api/app.py's invalid_token_loader
        finally:
            delete_user(app, uid)
```
- **Effort:** Low for the JWT tampering test above (~15 min). Medium-Large for systematic injection-payload testing across every freeform text field.
- **Importance: 3/10** — flagged as a gap in test *presence*, not a confirmed vulnerability; scored moderately because the underlying risk is unverified, not because it's dismissed.

### Finding M4 — No performance/load tests
- **Location:** repo-wide search for `locust`, `k6`, or any test asserting a response-time budget: none found.
- **Assessment:** Explicitly requested by this audit's scope; noting the gap plainly. Reasonable for a project at this scale/stage — this is the lowest-priority finding in the report.
- **Fix (if/when it becomes worth doing):**
```python
# api/tests/test_performance.py (new) — a budget test, not a full load-test suite
import time

def test_device_list_responds_within_budget(app, client, auth_headers_admin):
    start = time.monotonic()
    r = client.get("/api/devices/?per_page=50", headers=auth_headers_admin)
    elapsed = time.monotonic() - start
    assert r.status_code == 200
    assert elapsed < 0.5, f"devices list took {elapsed:.2f}s, budget is 0.5s"
```
- **Effort:** Low for a single budget test like the above; Large for a real load-test suite (k6/locust, needs its own infra decision).
- **Importance: 2/10**.

---

## Appendix — Unable to Verify

| Item | What would confirm it |
|---|---|
| Whether Q5's lack of a `Device`/`Ticket`/`Customer`/`AlertRule` factory causes real duplicated construction code across test files | `grep -n "Device(\|Ticket(\|AlertRule(" api/tests/*.py`, diff the resulting blocks |
| Whether `app.config["RATELIMIT_ENABLED"] = True` (Finding M1's fix) actually re-enables Flask-Limiter at runtime without app recreation | Running the proposed test and confirming a 429 |
| Whether `agent/tests/` can run on `ubuntu-latest` in CI given `pywin32`/`wmi` in `agent/requirements.txt` (Finding P5) | Attempting the `pip install` step on a Linux runner |
| Whether the app is actually vulnerable to any injection/XSS payload (Finding M3) | A `/security-review` pass or manual payload submission against a freeform field, checked against `dashboard/utils/sanitize.py::esc`'s call sites |
| Whether `FLASK_DEBUG`+`FLASK_ENV=production` guard (Finding M2) is more naturally tested in-process vs. via `subprocess` | Prototyping both approaches against `api/app.py`'s `if __name__ == "__main__":` block |

---

*Report generated by static + measured codebase review — Claude Code, 2026-09-24.*
