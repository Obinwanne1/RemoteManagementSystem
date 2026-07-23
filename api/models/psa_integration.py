import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone

from extensions import db


def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(os.getenv("SECRET_KEY", "").encode()).digest())
    return Fernet(key)


def encrypt_cred(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().encrypt(value.encode()).decode()
    except Exception:
        return value


def decrypt_cred(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception:
        return value


class PsaIntegration(db.Model):
    __tablename__ = "psa_integrations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(30), nullable=False)          # connectwise | autotask
    api_url = db.Column(db.String(500), nullable=False)
    company_id = db.Column(db.String(255), nullable=True)    # CW: company identifier; AT: unused
    client_id = db.Column(db.String(500), nullable=False)    # CW: public key; AT: integration code
    client_secret_enc = db.Column(db.Text, nullable=False)   # encrypted private key / secret
    site_name = db.Column(db.String(255), nullable=True)     # AT: username; CW: unused
    sync_tickets = db.Column(db.Boolean, default=True, nullable=False)
    sync_companies = db.Column(db.Boolean, default=True, nullable=False)
    sync_configs = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)
    sync_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    company_maps = db.relationship("PsaCompanyMap", backref="integration",
                                   lazy="dynamic", cascade="all, delete-orphan")
    ticket_maps = db.relationship("PsaTicketMap", backref="integration",
                                  lazy="dynamic", cascade="all, delete-orphan")

    def get_client(self):
        secret = decrypt_cred(self.client_secret_enc)
        if self.type == "connectwise":
            from utils.psa.connectwise import ConnectWiseClient
            return ConnectWiseClient(
                api_url=self.api_url,
                company_id=self.company_id or "",
                client_id=self.client_id,
                client_secret=secret,
            )
        if self.type == "autotask":
            from utils.psa.autotask import AutotaskClient
            return AutotaskClient(
                api_url=self.api_url,
                client_id=self.client_id,
                username=self.site_name or "",
                secret=secret,
            )
        raise ValueError(f"Unknown PSA type: {self.type}")

    def to_dict(self, include_secret=False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "api_url": self.api_url,
            "company_id": self.company_id,
            "client_id": self.client_id,
            "site_name": self.site_name,
            "sync_tickets": self.sync_tickets,
            "sync_companies": self.sync_companies,
            "sync_configs": self.sync_configs,
            "is_active": self.is_active,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_error": self.sync_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return d


class PsaCompanyMap(db.Model):
    __tablename__ = "psa_company_maps"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    psa_integration_id = db.Column(db.String(36), db.ForeignKey("psa_integrations.id",
                                   ondelete="CASCADE"), nullable=False, index=True)
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id",
                            ondelete="CASCADE"), nullable=False, index=True)
    psa_company_id = db.Column(db.String(100), nullable=False)
    psa_company_name = db.Column(db.String(255), nullable=True)
    synced_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("psa_integration_id", "customer_id", name="uq_psa_company_map"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "psa_integration_id": self.psa_integration_id,
            "customer_id": self.customer_id,
            "psa_company_id": self.psa_company_id,
            "psa_company_name": self.psa_company_name,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }


class PsaTicketMap(db.Model):
    __tablename__ = "psa_ticket_maps"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    psa_integration_id = db.Column(db.String(36), db.ForeignKey("psa_integrations.id",
                                   ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = db.Column(db.String(36), db.ForeignKey("tickets.id",
                          ondelete="CASCADE"), nullable=False, index=True)
    psa_ticket_id = db.Column(db.String(100), nullable=False)
    last_synced_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sync_error = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("psa_integration_id", "ticket_id", name="uq_psa_ticket_map"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "psa_integration_id": self.psa_integration_id,
            "ticket_id": self.ticket_id,
            "psa_ticket_id": self.psa_ticket_id,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "sync_error": self.sync_error,
        }
