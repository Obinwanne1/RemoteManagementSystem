"""Ticket lifecycle tasks — SLA breach detection."""
import logging
from datetime import datetime, timezone
from tasks.celery_app import celery

logger = logging.getLogger(__name__)

_app = None


def _get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
    return _app


@celery.task(name="tasks.ticket_tasks.check_sla_breaches", bind=True, max_retries=2)
def check_sla_breaches(self):
    """Mark tickets as SLA-breached when due_date has passed and ticket is still open/in_progress."""
    from extensions import db
    from models.ticket import Ticket

    with _get_app().app_context():
        try:
            now = datetime.now(timezone.utc)
            breached = Ticket.query.filter(
                Ticket.status.in_(["open", "in_progress"]),
                Ticket.sla_breached == False,  # noqa: E712
                Ticket.due_date != None,  # noqa: E711
                Ticket.due_date < now,
            ).all()

            if not breached:
                return

            for ticket in breached:
                ticket.sla_breached = True

            db.session.commit()
            logger.info("SLA breach check: marked %d ticket(s) as breached", len(breached))
        except Exception as exc:
            db.session.rollback()
            logger.exception("check_sla_breaches failed")
            raise self.retry(exc=exc, countdown=60)
