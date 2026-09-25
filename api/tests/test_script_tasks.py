"""Tests for tasks/script_tasks.py (audits/testing_audit.md Finding C3).

dispatch_script_run is currently a no-op (the agent polls for queued script
runs via GET /agents/{id}/tasks instead of being pushed to — see the file's
own docstring), so this is a deliberately thin regression test: it exists to
catch two things — the task no longer being importable/registered under its
Celery name, and someone accidentally giving the "no-op by design" function
real side effects without a matching test being added here."""
import tasks.script_tasks as script_tasks


class TestDispatchScriptRun:
    def test_is_a_noop_and_does_not_raise(self):
        # No app/DB context needed — the function body is `pass`.
        assert script_tasks.dispatch_script_run("any-run-id") is None

    def test_registered_under_the_expected_celery_task_name(self):
        assert script_tasks.dispatch_script_run.name == "tasks.script_tasks.dispatch_script_run"
