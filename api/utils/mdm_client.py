"""Abstract MDM client interface — mirrors utils/psa/base.py::PSAClient's shape.

MdmIntegration.get_client() (api/models/mdm_integration.py) currently has one
real implementation (AndroidManagementClient). This ABC exists so that when
Apple MDM is eventually built (needs an Apple Business Manager enrollment or
a vendor-signed MDM server decision made outside this codebase — see
MdmIntegration's docstring), the new client is checked against the exact
method surface routes/mobile_mdm.py and tasks/mdm_tasks.py actually call,
instead of silently drifting from AndroidManagementClient's shape.
"""
from abc import ABC, abstractmethod


class MdmClient(ABC):

    @abstractmethod
    def list_devices(self) -> list:
        """Return all enrolled devices under this integration as a list of dicts."""

    @abstractmethod
    def get_device(self, device_name: str) -> dict:
        """Return a single enrolled device's current state."""

    @abstractmethod
    def issue_command(self, device_name: str, command_type: str, **extra) -> dict:
        """Issue a remote command (LOCK, REBOOT, RESET_PASSWORD, START_LOST_MODE,
        STOP_LOST_MODE, RELINQUISH_OWNERSHIP, ...). Return the vendor's response."""

    @abstractmethod
    def delete_device(self, device_name: str, wipe_data_flags: list = None) -> None:
        """Remove/wipe a device from management."""

    @abstractmethod
    def create_enrollment_token(self, policy_name: str, ttl_hours: int = 1, **extra) -> dict:
        """Return a token/QR payload the device owner uses to enroll."""
