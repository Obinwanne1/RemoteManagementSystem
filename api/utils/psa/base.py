"""Abstract PSA client interface. Implement per-PSA in subclasses."""
from abc import ABC, abstractmethod
from datetime import datetime


class PSAClient(ABC):

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Return (success, message)."""

    @abstractmethod
    def get_companies(self) -> list[dict]:
        """Return list of {id, name, identifier} dicts."""

    @abstractmethod
    def push_ticket(self, ticket, psa_company_id: str) -> str | None:
        """Create ticket in PSA. Return PSA ticket ID string or None on failure."""

    @abstractmethod
    def update_ticket(self, psa_ticket_id: str, ticket) -> bool:
        """Update existing PSA ticket. Return True on success."""

    @abstractmethod
    def pull_tickets(self, since: datetime) -> list[dict]:
        """Return PSA tickets modified since `since` as list of dicts."""

    @abstractmethod
    def push_config_item(self, device, psa_company_id: str) -> str | None:
        """Create or update a configuration item in PSA. Return PSA config ID or None."""
