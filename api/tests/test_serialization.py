"""Regression guard for the models/*.py::to_dict() half-DTO pattern (see
audits/design_patterns_audit.md, Domain Finding D5): there is no schema-based
output layer, so field-allowlisting in to_dict() is enforced by developer
memory rather than something CI checks. These tests fail loudly if a secret
column is ever added to a dict literal, instead of silently leaking it."""
import uuid

from extensions import db
from models.user import User
from models.psa_integration import PsaIntegration
from models.mdm_integration import MdmIntegration


def test_user_to_dict_never_leaks_secrets(app):
    with app.app_context():
        u = User(email=f"leak_{uuid.uuid4().hex[:8]}@test.local", full_name="Leak Test", role="technician")
        u.set_password("TestPassword@1!")
        u.mfa_secret = "JBSWY3DPEHPK3PXP"
        d = u.to_dict()
        assert "password_hash" not in d
        assert "mfa_secret" not in d


def test_psa_integration_to_dict_never_leaks_secret(app):
    with app.app_context():
        integ = PsaIntegration(
            name="Leak Test PSA", type="connectwise", api_url="https://example.invalid",
            client_id="pub-key", client_secret_enc="super-secret-encrypted-blob",
        )
        d = integ.to_dict()
        assert "client_secret" not in d
        assert "client_secret_enc" not in d
        assert "super-secret-encrypted-blob" not in str(d)


def test_mdm_integration_to_dict_never_leaks_credentials(app):
    with app.app_context():
        integ = MdmIntegration(
            name="Leak Test MDM", type="android",
            service_account_json_enc="super-secret-service-account-blob",
        )
        d = integ.to_dict()
        assert "service_account_json_enc" not in d
        assert "apple_push_cert_enc" not in d
        assert "super-secret-service-account-blob" not in str(d)
