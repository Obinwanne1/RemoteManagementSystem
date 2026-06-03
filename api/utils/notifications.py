"""Email notification utility — reads SMTP config from .env."""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_alert_notification(rule_name: str, device_hostname: str, message: str, emails: list) -> bool:
    """Send email notification for a triggered alert. Silently skips if SMTP not configured."""
    if not emails:
        return True

    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP_HOST not set — skipping alert notification for: %s", rule_name)
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = f"[RMM Alert] {rule_name} — {device_hostname}"
    body = (
        f"RMM Alert Notification\n\n"
        f"Rule:    {rule_name}\n"
        f"Device:  {device_hostname}\n"
        f"Message: {message}\n\n"
        f"---\nThis is an automated notification from RMM System.\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = ", ".join(emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, emails, msg.as_string())

        logger.info("Alert notification sent for rule '%s' to %d recipient(s)", rule_name, len(emails))
        return True
    except Exception as exc:
        logger.warning("Failed to send alert notification for '%s': %s", rule_name, exc)
        return False
