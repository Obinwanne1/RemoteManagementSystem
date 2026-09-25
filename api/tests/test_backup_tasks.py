"""Tests for tasks/backup_tasks.py (audits/testing_audit.md Finding C3).
Never invokes a real pg_dump binary — _pg_dump_path() and subprocess.Popen
are always mocked."""
import gzip
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import tasks.backup_tasks as backup_tasks


class TestPruneOldBackups:
    def test_removes_files_older_than_retain_days(self, tmp_path):
        old_file = tmp_path / "rmmdb_20200101_000000.sql.gz"
        old_file.write_bytes(b"old")
        new_file = tmp_path / "rmmdb_20990101_000000.sql.gz"
        new_file.write_bytes(b"new")

        import os
        old_time = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
        os.utime(old_file, (old_time, old_time))

        backup_tasks._prune_old_backups(tmp_path, retain_days=7)

        assert not old_file.exists()
        assert new_file.exists()

    def test_ignores_non_matching_files(self, tmp_path):
        other = tmp_path / "not-a-backup.txt"
        other.write_text("keep me")
        backup_tasks._prune_old_backups(tmp_path, retain_days=0)
        assert other.exists()


class TestBackupDatabase:
    def test_returns_error_status_when_pg_dump_missing(self, app):
        with app.app_context():
            with patch.object(backup_tasks, "_pg_dump_path", side_effect=FileNotFoundError("pg_dump not found")):
                result = backup_tasks.backup_database()
        assert result["status"] == "error"
        assert "pg_dump" in result["reason"]

    def test_writes_gzip_file_on_successful_dump(self, app, tmp_path, monkeypatch):
        monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
        fake_sql = b"-- fake pg_dump output --\nSELECT 1;\n"

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (fake_sql, b"")
        mock_proc.returncode = 0

        with app.app_context():
            with patch.object(backup_tasks, "_pg_dump_path", return_value="pg_dump"), \
                 patch("tasks.backup_tasks.subprocess.Popen", return_value=mock_proc):
                result = backup_tasks.backup_database()

        assert result["status"] == "ok"
        out_file = tmp_path / result["file"]
        assert out_file.exists()
        with gzip.open(out_file, "rb") as gz:
            assert gz.read() == fake_sql

    def test_removes_partial_file_and_retries_on_nonzero_exit(self, app, tmp_path, monkeypatch):
        monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"", b"connection refused")
        mock_proc.returncode = 1

        with app.app_context():
            with patch.object(backup_tasks, "_pg_dump_path", return_value="pg_dump"), \
                 patch("tasks.backup_tasks.subprocess.Popen", return_value=mock_proc):
                try:
                    backup_tasks.backup_database()
                    raised = False
                except Exception:
                    raised = True

        assert raised, "expected self.retry() to raise when pg_dump exits non-zero"
        # No .sql.gz file should be left behind on failure
        assert list(tmp_path.glob("*.sql.gz")) == []
