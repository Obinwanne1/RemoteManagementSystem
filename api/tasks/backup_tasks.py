"""
Nightly PostgreSQL backup task.

Runs pg_dump, gzip-compresses the output, saves to BACKUP_DIR,
and prunes backups older than BACKUP_RETAIN_DAYS (default 7).

Required env vars (same DB connection the Flask app uses):
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
  BACKUP_DIR (optional, default: <api_dir>/../backups)
  BACKUP_RETAIN_DAYS (optional, default: 7)
"""
import gzip
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from tasks.celery_app import celery

logger = logging.getLogger(__name__)

_API_DIR = Path(__file__).parent.parent


def _backup_dir() -> Path:
    d = Path(os.getenv("BACKUP_DIR", str(_API_DIR / ".." / "backups")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pg_dump_path() -> str:
    """Find pg_dump binary or raise."""
    found = shutil.which("pg_dump")
    if found:
        return found
    # Common Windows PostgreSQL install paths
    for version in range(17, 11, -1):
        candidate = Path(f"C:/Program Files/PostgreSQL/{version}/bin/pg_dump.exe")
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "pg_dump not found. Add PostgreSQL bin directory to PATH."
    )


@celery.task(name="tasks.backup_tasks.backup_database", bind=True, max_retries=2)
def backup_database(self):
    """Dump PostgreSQL database to a gzip-compressed SQL file."""
    from sqlalchemy.exc import OperationalError

    db_url = os.getenv("DATABASE_URL", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "rmmdb")
    db_user = os.getenv("DB_USER", "rmm_app")
    db_pass = os.getenv("DB_PASSWORD", "")

    # Parse DATABASE_URL if set (overrides individual vars)
    if db_url and db_url.startswith("postgresql"):
        try:
            from urllib.parse import urlparse
            p = urlparse(db_url)
            db_host = p.hostname or db_host
            db_port = str(p.port or 5432)
            db_name = p.path.lstrip("/") or db_name
            db_user = p.username or db_user
            db_pass = p.password or db_pass
        except Exception:
            pass

    try:
        pg_dump = _pg_dump_path()
    except FileNotFoundError as exc:
        logger.error("backup_database: %s", exc)
        return {"status": "error", "reason": str(exc)}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = _backup_dir() / f"rmmdb_{timestamp}.sql.gz"

    env = os.environ.copy()
    env["PGPASSWORD"] = db_pass

    cmd = [
        pg_dump,
        "-h", db_host,
        "-p", db_port,
        "-U", db_user,
        "--no-password",
        "--format=plain",
        "--encoding=UTF8",
        db_name,
    ]

    try:
        logger.info("backup_database: starting dump → %s", out_path)
        with gzip.open(str(out_path), "wb") as gz:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout, stderr = proc.communicate(timeout=600)
            if proc.returncode != 0:
                out_path.unlink(missing_ok=True)
                err_msg = stderr.decode("utf-8", errors="replace")[:500]
                logger.error("pg_dump failed (exit %d): %s", proc.returncode, err_msg)
                raise RuntimeError(f"pg_dump exit {proc.returncode}: {err_msg}")
            gz.write(stdout)

        size_kb = out_path.stat().st_size // 1024
        logger.info("backup_database: dump complete, %d KB → %s", size_kb, out_path.name)

        # Prune old backups
        retain_days = int(os.getenv("BACKUP_RETAIN_DAYS", "7"))
        _prune_old_backups(_backup_dir(), retain_days)

        return {"status": "ok", "file": out_path.name, "size_kb": size_kb}

    except subprocess.TimeoutExpired:
        out_path.unlink(missing_ok=True)
        logger.error("backup_database: pg_dump timed out after 600s")
        raise self.retry(countdown=3600)
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        logger.error("backup_database failed: %s", exc)
        raise self.retry(exc=exc, countdown=1800)


def _prune_old_backups(backup_dir: Path, retain_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retain_days)
    removed = 0
    for f in backup_dir.glob("rmmdb_*.sql.gz"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                removed += 1
                logger.info("backup_database: pruned old backup %s", f.name)
        except Exception as exc:
            logger.warning("backup_database: could not prune %s: %s", f.name, exc)
    if removed:
        logger.info("backup_database: pruned %d old backup(s)", removed)
