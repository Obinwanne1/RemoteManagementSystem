"""Mobile Device Management — Android Management API integration + enrollment records.

No custom agent runs on managed phones. Android devices run Google's own signed
"Android Device Policy" app, provisioned via enrollment token/QR during a
device-owner-initiated enrollment. See MobileEnrollment for the consent trail
this legally and technically requires.

`type == "apple"` and the apple_* columns are placeholders for a future iOS
phase (real Apple MDM needs an Apple Business Manager decision made outside
this codebase) — reserved now so that phase needs no schema migration.
"""
import uuid
from datetime import datetime, timezone

from extensions import db
from utils.crypto import encrypt_cred, decrypt_cred  # noqa: F401 (re-exported for route/task use)


class MdmIntegration(db.Model):
    __tablename__ = "mdm_integrations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(20), nullable=False, default="android")  # android | apple
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True, index=True)

    # --- Android Management API ---
    project_id = db.Column(db.String(255), nullable=True)
    enterprise_id = db.Column(db.String(255), nullable=True)  # set once enterprises.create completes
    service_account_json_enc = db.Column(db.Text, nullable=True)
    default_policy_name = db.Column(db.String(255), nullable=True)
    pubsub_topic = db.Column(db.String(255), nullable=True)  # reserved: future push-notification upgrade

    # --- Apple MDM (Phase 3 placeholder — not implemented) ---
    apple_push_cert_enc = db.Column(db.Text, nullable=True)
    apple_topic = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)
    sync_error = db.Column(db.Text, nullable=True)
    # Simple circuit breaker: tasks/mdm_tasks.py auto-disables (is_active=False) an
    # integration after too many consecutive sync failures, instead of retrying a
    # permanently-broken integration (e.g. revoked credentials) forever.
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    enrollments = db.relationship("MobileEnrollment", backref="integration",
                                  lazy="dynamic", cascade="all, delete-orphan")

    def get_client(self):
        if self.type == "android":
            from utils.android_mgmt import AndroidManagementClient
            return AndroidManagementClient(
                project_id=self.project_id,
                enterprise_id=self.enterprise_id,
                service_account_json=decrypt_cred(self.service_account_json_enc or ""),
            )
        if self.type == "apple":
            raise NotImplementedError(
                "Apple MDM is not implemented — requires an Apple Business Manager "
                "enrollment or a vendor-signed MDM server (Fleet/MicroMDM) decision "
                "made outside this codebase before a client can be built."
            )
        raise ValueError(f"Unknown MDM integration type: {self.type}")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "customer_id": self.customer_id,
            "project_id": self.project_id,
            "enterprise_id": self.enterprise_id,
            "bound": bool(self.enterprise_id),
            "default_policy_name": self.default_policy_name,
            "is_active": self.is_active,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_error": self.sync_error,
            "consecutive_failures": self.consecutive_failures,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MobileEnrollment(db.Model):
    """One-to-zero-or-one with Device. device_id is null until Google confirms
    enrollment (the phone owner actually scanned the QR / opened the link)."""
    __tablename__ = "mobile_enrollments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mdm_integration_id = db.Column(db.String(36), db.ForeignKey("mdm_integrations.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id", ondelete="SET NULL"),
                          nullable=True, unique=True, index=True)
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True, index=True)

    android_enterprise_device_name = db.Column(db.String(500), nullable=True)  # enterprises/{e}/devices/{id}
    enrollment_token = db.Column(db.String(500), nullable=True)
    enrollment_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    ownership_type = db.Column(db.String(20), nullable=False, default="byod")  # byod | corporate
    status = db.Column(db.String(20), nullable=False, default="pending")
    # pending | enrolled | revoked | wiped | expired

    # --- Consent audit trail (real columns, not a JSON blob — this is the legal record) ---
    consent_given_by_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    consent_given_at = db.Column(db.DateTime(timezone=True), nullable=True)
    consent_text_version = db.Column(db.String(50), nullable=True)
    consent_ip_address = db.Column(db.String(45), nullable=True)

    policy_name = db.Column(db.String(255), nullable=True)
    last_policy_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_status_report_at = db.Column(db.DateTime(timezone=True), nullable=True)
    policy_compliant = db.Column(db.Boolean, nullable=True)
    non_compliance_details = db.Column(db.JSON, nullable=True)

    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked_by_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    device = db.relationship("Device", backref=db.backref("mdm_enrollment", uselist=False))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mdm_integration_id": self.mdm_integration_id,
            "device_id": self.device_id,
            "customer_id": self.customer_id,
            "ownership_type": self.ownership_type,
            "status": self.status,
            "consent_given_at": self.consent_given_at.isoformat() if self.consent_given_at else None,
            "consent_text_version": self.consent_text_version,
            "policy_name": self.policy_name,
            "last_policy_sync_at": self.last_policy_sync_at.isoformat() if self.last_policy_sync_at else None,
            "last_status_report_at": self.last_status_report_at.isoformat() if self.last_status_report_at else None,
            "policy_compliant": self.policy_compliant,
            "non_compliance_details": self.non_compliance_details,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict_with_enrollment_info(self) -> dict:
        """Includes the enrollment token/QR payload — only ever returned right after creation."""
        d = self.to_dict()
        d["enrollment_token"] = self.enrollment_token
        d["enrollment_token_expires_at"] = (
            self.enrollment_token_expires_at.isoformat() if self.enrollment_token_expires_at else None
        )
        return d
