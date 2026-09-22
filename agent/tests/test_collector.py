"""
Starter tests for agent/collector.py's pure-logic and lightly-mocked helpers.
Focuses on the winget parsing fix (skips progress-bar lines, finds the real
separator row) documented in CLAUDE.md, plus other pure decoding helpers.
Subprocess-dependent functions are exercised via mocking `_run`, never a
real OS call.
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import collector  # noqa: E402


class TestDecodeOutput:
    def test_decodes_utf8(self):
        assert collector._decode_output("hello".encode("utf-8")) == "hello"

    def test_decodes_utf16_le_bom(self):
        raw = "hi".encode("utf-16-le")
        raw_with_bom = b"\xff\xfe" + raw
        assert collector._decode_output(raw_with_bom) == "hi"

    def test_decodes_utf16_be_bom(self):
        raw = "hi".encode("utf-16-be")
        raw_with_bom = b"\xfe\xff" + raw
        assert collector._decode_output(raw_with_bom) == "hi"


class TestWingetProgressLineDetection:
    def test_block_chars_flagged(self):
        assert collector._is_winget_progress_line("███████░░░░░░░ 50%") is True

    def test_plain_ascii_not_flagged(self):
        assert collector._is_winget_progress_line("7-Zip 23.01 7zip.7zip 23.01") is False

    def test_empty_line_not_flagged(self):
        assert collector._is_winget_progress_line("") is False


class TestGetWingetSoftware:
    def _completed(self, stdout: bytes, returncode: int = 0):
        return subprocess.CompletedProcess(args=["winget"], returncode=returncode, stdout=stdout, stderr=b"")

    def test_returns_empty_list_on_nonzero_exit(self):
        with patch.object(collector, "_run", return_value=self._completed(b"", returncode=1)):
            assert collector._get_winget_software() == []

    def test_parses_data_rows_after_separator_and_skips_progress_lines(self):
        stdout_lines = [
            "-\\|/ 50%",  # a plain ascii spinner-ish line (not a progress-bar unicode line)
            "Name               Id                Version",
            "----------------------------------------------",
            "███████████████████░░░░░░░░ 60%",  # winget progress bar (unicode blocks) — must be skipped
            "7-Zip              7zip.7zip         23.01",
            "Git                Git.Git           2.44.0",
        ]
        stdout = ("\n".join(stdout_lines)).encode("utf-8")
        with patch.object(collector, "_run", return_value=self._completed(stdout)):
            result = collector._get_winget_software()

        names = {row["name"] for row in result}
        assert "7-Zip" in names
        assert "Git" in names
        assert all(row["source"] == "winget" for row in result)
        versions = {row["name"]: row["version"] for row in result}
        assert versions["7-Zip"] == "23.01"
        assert versions["Git"] == "2.44.0"

    def test_no_separator_line_returns_empty(self):
        stdout = b"just some random text\nwith no dashed separator\n"
        with patch.object(collector, "_run", return_value=self._completed(stdout)):
            assert collector._get_winget_software() == []


class TestDetectLinuxPkgManager:
    def test_returns_apt_when_apt_get_found(self):
        def fake_run(cmd, timeout=3, **kwargs):
            if cmd == ["which", "apt-get"]:
                return subprocess.CompletedProcess(cmd, 0, b"/usr/bin/apt-get", b"")
            return subprocess.CompletedProcess(cmd, 1, b"", b"")

        with patch.object(collector, "_run", side_effect=fake_run):
            assert collector._detect_linux_pkg_manager() == "apt"

    def test_returns_unknown_when_none_found(self):
        def fake_run(cmd, timeout=3, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, b"", b"")

        with patch.object(collector, "_run", side_effect=fake_run):
            assert collector._detect_linux_pkg_manager() == "unknown"
