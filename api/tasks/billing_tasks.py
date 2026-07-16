"""
Recurring invoice generation task.

Runs daily. For each active customer where:
  - billing_day is set AND equals today's day-of-month
  - per_device_rate is set and > 0
Generates a draft invoice for the previous calendar month.
Skips if an invoice for that period already exists (idempotent).
"""
import logging
from datetime import datetime, timezone, timedelta
from calendar import monthrange

from tasks.celery_app import celery

logger = logging.getLogger(__name__)

_app = None


def _get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
    return _app


def _period_bounds(ref: datetime):
    """Return (period_start, period_end) for the month prior to ref."""
    first_of_this_month = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_of_prev = first_of_this_month - timedelta(seconds=1)
    first_of_prev = last_of_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_of_prev, first_of_this_month - timedelta(seconds=1)


def _next_invoice_number(year: int, db_session) -> str:
    from models.billing import Invoice
    count = db_session.query(Invoice).filter(
        Invoice.invoice_number.like(f"INV-{year}-%")
    ).count()
    return f"INV-{year}-{count + 1:04d}"


@celery.task(name="tasks.billing_tasks.generate_recurring_invoices", bind=True, max_retries=2)
def generate_recurring_invoices(self):
    """Auto-generate draft invoices for customers whose billing_day matches today."""
    from extensions import db
    from models.customer import Customer
    from models.billing import Invoice
    from models.device import Device

    with _get_app().app_context():
        try:
            now = datetime.now(timezone.utc)
            today_day = now.day

            candidates = Customer.query.filter(
                Customer.is_active == True,  # noqa: E712
                Customer.billing_day == today_day,
                Customer.per_device_rate != None,  # noqa: E711
                Customer.per_device_rate > 0,
            ).all()

            if not candidates:
                logger.info("billing_tasks: no customers due for invoicing today (day %d)", today_day)
                return {"generated": 0}

            period_start, period_end = _period_bounds(now)
            generated = 0

            for customer in candidates:
                # Idempotency — skip if invoice for this period already exists
                existing = Invoice.query.filter(
                    Invoice.customer_id == customer.id,
                    Invoice.period_start == period_start,
                ).first()
                if existing:
                    logger.info(
                        "billing_tasks: invoice for customer %s period %s already exists (%s) — skipping",
                        customer.id, period_start.date(), existing.invoice_number,
                    )
                    continue

                device_count = Device.query.filter_by(customer_id=customer.id).count()
                rate = float(customer.per_device_rate)
                subtotal = device_count * rate
                tax_rate = float(customer.tax_rate or 0)
                tax = round(subtotal * tax_rate, 2)
                total = round(subtotal + tax, 2)
                due_date = now.replace(day=1) + timedelta(days=30)

                invoice = Invoice(
                    invoice_number=_next_invoice_number(now.year, db.session),
                    customer_id=customer.id,
                    period_start=period_start,
                    period_end=period_end,
                    due_date=due_date,
                    device_count=device_count,
                    per_device_rate=rate,
                    subtotal=subtotal,
                    tax_rate=tax_rate,
                    tax=tax,
                    total=total,
                    status="draft",
                    notes=f"Auto-generated for {period_start.strftime('%B %Y')}",
                    line_items=[{
                        "description": f"Managed Devices — {period_start.strftime('%B %Y')}",
                        "quantity": device_count,
                        "rate": rate,
                        "amount": subtotal,
                    }],
                )
                db.session.add(invoice)
                db.session.flush()
                generated += 1
                logger.info(
                    "billing_tasks: created invoice %s for customer %s (%d devices × $%.2f = $%.2f)",
                    invoice.invoice_number, customer.name, device_count, rate, total,
                )

            db.session.commit()
            logger.info("billing_tasks: generated %d invoice(s)", generated)
            return {"generated": generated, "period": period_start.strftime("%Y-%m")}

        except Exception as exc:
            db.session.rollback()
            logger.exception("generate_recurring_invoices failed")
            raise self.retry(exc=exc, countdown=3600)
