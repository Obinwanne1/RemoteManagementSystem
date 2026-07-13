"""
Webhook notification adapter — Slack, Microsoft Teams, and generic HTTP.

notification_channels JSON format (per AlertRule):
  {
    "email":   ["ops@company.com"],
    "slack":   ["https://hooks.slack.com/services/T.../B.../..."],
    "teams":   ["https://company.webhook.office.com/webhookb2/..."],
    "webhook": ["https://your-server.com/rmm-alerts"]
  }

Any combination of channel types is valid. Multiple URLs per type are supported.
"""
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 5  # seconds per POST

_SEVERITY_COLORS = {
    "critical": "#FF3B30",
    "warning":  "#FF9500",
    "info":     "#007AFF",
}


def dispatch_alert_webhooks(
    channels: dict,
    rule_name: str,
    device_hostname: str,
    message: str,
    severity: str = "warning",
) -> None:
    """
    Dispatch alert notifications to all configured webhook channels.
    Never raises — all errors are logged and swallowed.
    """
    if not channels:
        return

    for url in channels.get("slack", []):
        _post_slack(url, rule_name, device_hostname, message, severity)

    for url in channels.get("teams", []):
        _post_teams(url, rule_name, device_hostname, message, severity)

    for url in channels.get("webhook", []):
        _post_generic(url, rule_name, device_hostname, message, severity)


def _post_slack(url: str, rule_name: str, hostname: str, message: str, severity: str) -> None:
    color = _SEVERITY_COLORS.get(severity, "#FF9500")
    payload = {
        "text": f":rotating_light: *RMM Alert* — {rule_name} on `{hostname}`",
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "Rule",     "value": rule_name, "short": True},
                    {"title": "Device",   "value": hostname,  "short": True},
                    {"title": "Severity", "value": severity.capitalize(), "short": True},
                    {"title": "Time",     "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "short": True},
                    {"title": "Message",  "value": message,   "short": False},
                ],
                "footer": "RMM Platform",
            }
        ],
    }
    _send(url, payload, "Slack")


def _post_teams(url: str, rule_name: str, hostname: str, message: str, severity: str) -> None:
    color = _SEVERITY_COLORS.get(severity, "#FF9500").lstrip("#")
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"RMM Alert: {rule_name}",
        "sections": [
            {
                "activityTitle": f"🚨 RMM Alert: **{rule_name}**",
                "activitySubtitle": f"Device: {hostname}",
                "facts": [
                    {"name": "Severity", "value": severity.capitalize()},
                    {"name": "Device",   "value": hostname},
                    {"name": "Message",  "value": message},
                    {"name": "Time",     "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")},
                ],
                "markdown": True,
            }
        ],
    }
    _send(url, payload, "Teams")


def _post_generic(url: str, rule_name: str, hostname: str, message: str, severity: str) -> None:
    payload = {
        "event":     "rmm_alert",
        "rule":      rule_name,
        "device":    hostname,
        "severity":  severity,
        "message":   message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _send(url, payload, "webhook")


def _send(url: str, payload: dict, channel_type: str) -> None:
    try:
        resp = requests.post(url, json=payload, timeout=_TIMEOUT)
        if not resp.ok:
            logger.warning(
                "%s webhook failed [%s]: HTTP %d — %s",
                channel_type, url[:60], resp.status_code, resp.text[:200],
            )
        else:
            logger.debug("%s webhook delivered to %s", channel_type, url[:60])
    except requests.exceptions.Timeout:
        logger.warning("%s webhook timed out after %ds [%s]", channel_type, _TIMEOUT, url[:60])
    except requests.exceptions.RequestException as exc:
        logger.warning("%s webhook error [%s]: %s", channel_type, url[:60], exc)
