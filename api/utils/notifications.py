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
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
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


def send_account_locked_email(locked_email: str, admin_emails: list) -> bool:
    """Notify all admins when a user account is locked after too many failed attempts."""
    if not admin_emails:
        return True

    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP_HOST not set — skipping account locked notification for: %s", locked_email)
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = f"[RMM Security] Account locked: {locked_email}"
    body = (
        f"RMM Security Alert\n\n"
        f"The following account has been locked after 3 consecutive failed login attempts:\n\n"
        f"  Account: {locked_email}\n\n"
        f"The account will auto-unlock after 5 minutes, or an admin can unlock it immediately:\n"
        f"  Admin Panel → Users tab → find the account → click Unlock\n\n"
        f"If this was not a legitimate user, consider reviewing the audit log for suspicious activity.\n\n"
        f"---\nThis is an automated security notification from RMM System.\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = ", ".join(admin_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, admin_emails, msg.as_string())

        logger.info("Account locked notification sent for '%s' to %d admin(s)", locked_email, len(admin_emails))
        return True
    except Exception as exc:
        logger.warning("Failed to send account locked notification for '%s': %s", locked_email, exc)
        return False


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Send a password reset link to the user. Silently skips if SMTP not configured."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP_HOST not set — skipping password reset email for: %s", to_email)
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = "[RMM] Password reset request"
    body = (
        f"RMM Password Reset\n\n"
        f"A password reset was requested for your account ({to_email}).\n\n"
        f"Click the link below to set a new password (valid for 1 hour):\n\n"
        f"  {reset_url}\n\n"
        f"If you did not request this, you can safely ignore this email.\n"
        f"Your password will not change unless you click the link above.\n\n"
        f"---\nThis is an automated notification from RMM System.\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())

        logger.info("Password reset email sent to '%s'", to_email)
        return True
    except Exception as exc:
        logger.warning("Failed to send password reset email to '%s': %s", to_email, exc)
        return False


def send_login_anomaly_alert(user_email: str, ip: str, admin_emails: list) -> bool:
    """Alert user + admins when login occurs from an unrecognised IP address."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = f"[RMM Security] New login location detected: {user_email}"
    body = (
        f"RMM Security Alert\n\n"
        f"A login to account {user_email} was detected from a new IP address:\n\n"
        f"  IP Address: {ip}\n\n"
        f"If this was you, no action is needed.\n"
        f"If this was NOT you, contact your admin immediately to secure your account.\n\n"
        f"---\nThis is an automated security notification from RMM System.\n"
    )

    recipients = list({user_email} | set(admin_emails))
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, recipients, msg.as_string())

        logger.info("Login anomaly alert sent for '%s' from IP %s", user_email, ip)
        return True
    except Exception as exc:
        logger.warning("Failed to send login anomaly alert for '%s': %s", user_email, exc)
        return False


def send_account_deactivated_email(to_email: str) -> bool:
    """Notify user their account was auto-deactivated due to 30 days inactivity."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = "[RMM] Your account has been deactivated"
    body = (
        f"RMM Account Notice\n\n"
        f"Your account ({to_email}) has been automatically deactivated due to\n"
        f"30 days of inactivity.\n\n"
        f"To regain access, contact your system administrator to reactivate your account.\n\n"
        f"---\nThis is an automated notification from RMM System.\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())

        logger.info("Account deactivated notification sent to '%s'", to_email)
        return True
    except Exception as exc:
        logger.warning("Failed to send deactivation email to '%s': %s", to_email, exc)
        return False


def send_dormant_admin_alert(deactivated_emails: list, admin_emails: list) -> bool:
    """Notify admins that dormant accounts were auto-deactivated."""
    if not admin_emails:
        return True
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = f"[RMM] {len(deactivated_emails)} dormant account(s) deactivated"
    account_list = "\n".join(f"  - {e}" for e in deactivated_emails)
    body = (
        f"RMM System Notice\n\n"
        f"The following account(s) were automatically deactivated due to 30+ days of inactivity:\n\n"
        f"{account_list}\n\n"
        f"To reactivate an account: Admin Panel → Users → Show inactive → Reactivate.\n\n"
        f"---\nThis is an automated notification from RMM System.\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = ", ".join(admin_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, admin_emails, msg.as_string())

        logger.info("Dormant admin alert sent: %d account(s) deactivated", len(deactivated_emails))
        return True
    except Exception as exc:
        logger.warning("Failed to send dormant admin alert: %s", exc)
        return False


def send_password_expiry_warning(to_email: str, days_left: int) -> bool:
    """Warn user their password expires in N days."""
    smtp_host = os.getenv("SMTP_HOST", "")
    if not smtp_host:
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "rmm@localhost")

    subject = f"[RMM] Your password expires in {days_left} day(s)"
    body = (
        f"RMM Password Expiry Notice\n\n"
        f"Your password for account {to_email} will expire in {days_left} day(s).\n\n"
        f"Please log in and change your password before it expires to avoid being locked out.\n"
        f"Go to: My Profile → Change Password\n\n"
        f"---\nThis is an automated notification from RMM System.\n"
    )

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())

        logger.info("Password expiry warning sent to '%s' (%d days left)", to_email, days_left)
        return True
    except Exception as exc:
        logger.warning("Failed to send expiry warning to '%s': %s", to_email, exc)
        return False
