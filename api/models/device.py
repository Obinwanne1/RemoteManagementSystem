import uuid
from datetime import datetime, timezone
from extensions import db


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=False, index=True)
    group_id = db.Column(db.String(36), db.ForeignKey("device_groups.id"), nullable=True)
    hostname = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=True)
    platform = db.Column(db.String(50), default="windows")  # windows/linux/mac
    os_name = db.Column(db.String(255), nullable=True)
    os_version = db.Column(db.String(255), nullable=True)
    os_build = db.Column(db.String(100), nullable=True)
    architecture = db.Column(db.String(50), nullable=True)
    cpu_model = db.Column(db.String(255), nullable=True)
    cpu_cores = db.Column(db.Integer, nullable=True)
    ram_gb = db.Column(db.Float, nullable=True)
    serial_number = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    mac_address = db.Column(db.String(100), nullable=True)
    public_ip = db.Column(db.String(45), nullable=True)
    hardware_fingerprint = db.Column(db.String(255), nullable=True)  # SHA-256(hostname+MAC+serial)
    agent_version = db.Column(db.String(50), nullable=True)
    last_seen = db.Column(db.DateTime(timezone=True), nullable=True)
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(50), default="unknown")  # healthy/warning/critical/offline/unknown
    metadata_ = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    metrics = db.relationship("DeviceMetrics", backref="device", lazy="dynamic",
                              cascade="all, delete-orphan")
    installed_software = db.relationship("InstalledSoftware", backref="device", lazy="dynamic",
                                         cascade="all, delete-orphan")
    agent_tokens = db.relationship("AgentToken", backref="device", lazy="dynamic",
                                   cascade="all, delete-orphan")

    def to_dict(self, include_latest_metrics=False):
        d = {
            "id": self.id,
            "customer_id": self.customer_id,
            "group_id": self.group_id,
            "hostname": self.hostname,
            "display_name": self.display_name or self.hostname,
            "platform": self.platform,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "os_build": self.os_build,
            "architecture": self.architecture,
            "cpu_model": self.cpu_model,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "serial_number": self.serial_number,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "agent_version": self.agent_version,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_online": self.is_online,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_latest_metrics:
            latest = self.metrics.order_by(DeviceMetrics.collected_at.desc()).first()
            d["latest_metrics"] = latest.to_dict() if latest else None
        return d


class DeviceMetrics(db.Model):
    __tablename__ = "device_metrics"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False, index=True)
    collected_at = db.Column(db.DateTime(timezone=True), nullable=False,
                             default=lambda: datetime.now(timezone.utc), index=True)
    cpu_pct = db.Column(db.Float, nullable=True)
    ram_pct = db.Column(db.Float, nullable=True)
    ram_used_gb = db.Column(db.Float, nullable=True)
    disk_pct = db.Column(db.Float, nullable=True)
    disk_used_gb = db.Column(db.Float, nullable=True)
    disk_total_gb = db.Column(db.Float, nullable=True)
    network_bytes_sent = db.Column(db.BigInteger, nullable=True)
    network_bytes_recv = db.Column(db.BigInteger, nullable=True)
    battery_pct = db.Column(db.Float, nullable=True)
    battery_plugged = db.Column(db.Boolean, nullable=True)
    uptime_seconds = db.Column(db.BigInteger, nullable=True)
    top_processes = db.Column(db.JSON, nullable=True)
    disks = db.Column(db.JSON, nullable=True)  # per-drive usage

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "cpu_pct": self.cpu_pct,
            "ram_pct": self.ram_pct,
            "ram_used_gb": self.ram_used_gb,
            "disk_pct": self.disk_pct,
            "disk_used_gb": self.disk_used_gb,
            "disk_total_gb": self.disk_total_gb,
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "battery_pct": self.battery_pct,
            "battery_plugged": self.battery_plugged,
            "uptime_seconds": self.uptime_seconds,
            "top_processes": self.top_processes,
            "disks": self.disks,
        }


class InstalledSoftware(db.Model):
    __tablename__ = "installed_software"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False, index=True)
    name = db.Column(db.String(500), nullable=False)
    version = db.Column(db.String(255), nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    install_date = db.Column(db.String(50), nullable=True)
    source = db.Column(db.String(50), nullable=True)  # registry/winget/choco
    last_seen = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "name": self.name,
            "version": self.version,
            "publisher": self.publisher,
            "install_date": self.install_date,
            "source": self.source,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


import uuid  # noqa: E402 (needed at bottom due to default= lambda)
