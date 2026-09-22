"""
Starter tests for agent/script_runner.py's pure-logic helpers.
Only covers functions that don't require actually spawning a subprocess.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from script_runner import _decode_output, _build_command, CREATE_NO_WINDOW  # noqa: E402


class TestDecodeOutput:
    def test_decodes_utf8_bytes(self):
        assert _decode_output("hello world".encode("utf-8")) == "hello world"

    def test_decodes_utf8_with_non_ascii(self):
        assert _decode_output("café".encode("utf-8")) == "café"

    def test_falls_back_on_invalid_utf8(self):
        # 0x81 is invalid as a standalone UTF-8 byte but valid cp1252
        raw = b"progress: 50\x81% done"
        result = _decode_output(raw)
        assert "progress: 50" in result
        assert "% done" in result


class TestBuildCommand:
    def test_bat_uses_cmd_exe(self):
        cmd = _build_command("C:/tmp/script.bat", "bat")
        assert cmd == ["cmd.exe", "/c", "C:/tmp/script.bat"]

    def test_ps1_uses_powershell_non_interactive(self):
        cmd = _build_command("C:/tmp/script.ps1", "ps1")
        assert cmd[0] == "powershell.exe"
        assert "-NonInteractive" in cmd
        assert cmd[-2:] == ["-File", "C:/tmp/script.ps1"]

    def test_py_uses_current_interpreter(self):
        cmd = _build_command("C:/tmp/script.py", "py")
        assert cmd == [sys.executable, "C:/tmp/script.py"]

    def test_unsupported_type_returns_none(self):
        assert _build_command("C:/tmp/script.exe", "exe") is None


class TestCreateNoWindowFlag:
    def test_create_no_window_constant_is_set(self):
        # CLAUDE.md critical rule: Windows subprocesses must always use
        # CREATE_NO_WINDOW — guard against it being accidentally removed/zeroed.
        assert CREATE_NO_WINDOW == 0x08000000
