"""
RMM load test — simulates concurrent agents and dashboard users.

Usage:
    pip install locust
    locust -f tests/load/locustfile.py --host http://localhost:5000

Then open http://localhost:8089 to start the test.

Recommended scenarios:
  - 100 AgentUser / 10 DashboardUser: baseline
  - 500 AgentUser / 50 DashboardUser: stress test
  - ramp-up: 10 users/sec spawn rate
"""
import uuid
import random
from locust import HttpUser, task, between, events


ORG_TOKEN = "change-this-to-match-your-env-ORG_REGISTRATION_TOKEN"
ADMIN_EMAIL = "superadmin@rmm.local"
ADMIN_PASSWORD = "SuperAdmin@RMM1"


class AgentUser(HttpUser):
    """Simulates a registered RMM agent sending heartbeats."""
    wait_time = between(25, 35)  # agents heartbeat every ~30s

    device_id = None
    agent_token = None

    def on_start(self):
        """Register as a new agent on spawn."""
        hostname = f"LOAD-{uuid.uuid4().hex[:8].upper()}"
        resp = self.client.post("/api/agents/register", json={
            "org_token": ORG_TOKEN,
            "hostname": hostname,
            "mac_address": f"AA:BB:CC:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}",
            "serial_number": uuid.uuid4().hex[:12],
            "platform": "windows",
            "os_name": "Windows 11",
            "os_version": "23H2",
            "cpu_model": "Intel i7-12700",
            "cpu_cores": 8,
            "ram_gb": 16.0,
            "agent_version": "1.0.0",
        }, name="/api/agents/register")

        if resp.status_code == 201:
            data = resp.json()
            self.device_id = data["device_id"]
            self.agent_token = data["agent_token"]

    @task(10)
    def heartbeat(self):
        if not self.device_id or not self.agent_token:
            return
        cpu = random.uniform(5, 95)
        ram = random.uniform(20, 85)
        disk = random.uniform(30, 70)
        resp = self.client.post(
            f"/api/agents/{self.device_id}/heartbeat",
            json={
                "cpu_pct": cpu,
                "ram_pct": ram,
                "disk_pct": disk,
                "ram_used_gb": ram * 0.16,
                "uptime_seconds": random.randint(3600, 86400 * 30),
            },
            headers={"Authorization": f"Bearer {self.agent_token}"},
            name="/api/agents/<id>/heartbeat",
        )
        # Handle token rotation
        if resp.status_code == 200:
            body = resp.json()
            if "new_agent_token" in body:
                self.agent_token = body["new_agent_token"]

    @task(2)
    def poll_tasks(self):
        if not self.device_id or not self.agent_token:
            return
        self.client.get(
            f"/api/agents/{self.device_id}/tasks",
            headers={"Authorization": f"Bearer {self.agent_token}"},
            name="/api/agents/<id>/tasks",
        )

    @task(1)
    def update_software(self):
        if not self.device_id or not self.agent_token:
            return
        self.client.put(
            f"/api/agents/{self.device_id}/software",
            json={"software": [
                {"name": "Notepad++", "version": "8.6", "publisher": "Notepad++ Team"},
                {"name": "7-Zip", "version": "24.01", "publisher": "Igor Pavlov"},
                {"name": "Google Chrome", "version": "120.0", "publisher": "Google LLC"},
            ]},
            headers={"Authorization": f"Bearer {self.agent_token}"},
            name="/api/agents/<id>/software",
        )


class DashboardUser(HttpUser):
    """Simulates a technician browsing the dashboard."""
    wait_time = between(2, 8)

    access_token = None

    def on_start(self):
        resp = self.client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }, name="/api/auth/login")
        if resp.status_code == 200:
            self.access_token = resp.json().get("access_token")

    def _auth(self):
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    @task(5)
    def list_devices(self):
        self.client.get("/api/devices/?per_page=50", headers=self._auth(),
                        name="/api/devices/")

    @task(3)
    def list_alerts(self):
        self.client.get("/api/alerts?per_page=20", headers=self._auth(),
                        name="/api/alerts")

    @task(2)
    def list_tickets(self):
        self.client.get("/api/tickets/?per_page=20", headers=self._auth(),
                        name="/api/tickets/")

    @task(2)
    def dashboard_summary(self):
        self.client.get("/api/dashboard/summary", headers=self._auth(),
                        name="/api/dashboard/summary")

    @task(1)
    def health_check(self):
        self.client.get("/api/health", name="/api/health")

    @task(1)
    def refresh_token(self):
        """Simulate token refresh every ~10 requests."""
        pass  # real refresh needs refresh token — skip in load test
