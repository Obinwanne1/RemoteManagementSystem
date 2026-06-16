# Load Testing

## Setup

```powershell
pip install locust
```

Edit `locustfile.py` line 14 — set `ORG_TOKEN` to match your `.env` `ORG_REGISTRATION_TOKEN`.

If superadmin credentials differ from defaults, update `ADMIN_EMAIL` / `ADMIN_PASSWORD` too.

## Run

Start all services first (API + Postgres + Redis):

```powershell
# terminal 1
cd api; python app.py

# terminal 2 (optional — needed for patch deploy / automation tasks)
cd api; celery -A tasks.celery_app worker --pool=solo -l info
```

Then:

```powershell
locust -f tests/load/locustfile.py --host http://localhost:5000
```

Open **http://localhost:8089** → set user count + spawn rate → Start.

## Recommended scenarios

| Scenario | AgentUser | DashboardUser | Spawn rate | Goal |
|---|---|---|---|---|
| Baseline | 50 | 5 | 5/s | Confirm < 200ms p95 on heartbeat |
| Normal load | 100 | 10 | 10/s | Sustain 10 min, watch error rate |
| Stress | 500 | 50 | 20/s | Find where errors start appearing |
| Spike | 0→200 in 10s | 0→20 in 10s | 20/s | Check recovery after spike |

## What to watch

- **Heartbeat p95 latency** — target < 300ms under normal load
- **Error rate** — should be 0% under normal load, < 1% under stress
- **DB connections** — watch Postgres `pg_stat_activity` if errors spike
- **Memory** — Flask process RSS under sustained 500-agent load

## Results

Record findings in this file after each run:

```
Date: YYYY-MM-DD
Scenario: 100 agents / 10 dashboard users / 10 min
p50 heartbeat: Xms | p95: Xms | p99: Xms
Error rate: X%
Throughput: X req/s
Bottleneck: (DB pool / CPU / memory / none observed)
```
