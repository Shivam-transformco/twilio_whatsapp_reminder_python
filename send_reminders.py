"""
WhatsApp Reminder Script — runs daily via cron at 7 AM IST.

Logic:
  1. Get today's date in IST.
  2. For each active event, compute: reminder_date = event_date - days_prior.
  3. If reminder_date == today, send WhatsApp messages to the event's recipients.
  4. For recurring events whose event_date has passed, auto-advance to next year.
  5. Log every send attempt in reminder_log to avoid duplicates.
"""

import sys
import argparse
import logging
from datetime import datetime, timedelta
from bson import ObjectId
import pytz
from twilio.rest import Client

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_FROM,
    TIMEZONE,
)
from db import (
    get_events_collection,
    get_recipients_collection,
    get_templates_collection,
    get_reminder_log_collection,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("reminder.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Twilio client
# ---------------------------------------------------------------------------
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
tz = pytz.timezone(TIMEZONE)


def get_today():
    """Return today's date (date only, no time) in configured timezone."""
    return datetime.now(tz).date()


def load_templates():
    """Return a dict mapping event_type -> template string."""
    templates = {}
    for doc in get_templates_collection().find():
        templates[doc["event_type"]] = doc["template"]
    return templates


def get_recipients_for_event(event):
    """
    If event has specific recipient_ids, return those recipients.
    Otherwise return all active recipients.
    """
    col = get_recipients_collection()
    if event.get("recipient_ids"):
        return list(col.find({"_id": {"$in": event["recipient_ids"]}, "is_active": True}))
    return list(col.find({"is_active": True}))


def already_sent_today(event_id, phone, today):
    """Check if a reminder was already sent for this event+phone today."""
    log = get_reminder_log_collection()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    return log.find_one({
        "event_id": event_id,
        "recipient_phone": phone,
        "sent_at": {"$gte": start, "$lt": end},
        "status": "sent",
    }) is not None


def build_message(template, event, recipient, days_left):
    """Fill placeholders in the template string."""
    event_date_str = event["event_date"].strftime("%d %b %Y (%A)")
    if days_left == 0:
        days_left_text = "Today"
    elif days_left == 1:
        days_left_text = "Tomorrow (1 day left)"
    else:
        days_left_text = f"{days_left} day(s) left"
    return template.format(
        event_name=event["name"],
        event_date=event_date_str,
        days_left=days_left,
        days_left_text=days_left_text,
        description=event.get("description", ""),
        recipient=recipient.get("name", ""),
    )


def send_whatsapp(to_phone, body):
    """Send a WhatsApp message via Twilio. Returns (sid, error)."""
    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
        return msg.sid, None
    except Exception as e:
        return None, str(e)


def log_reminder(event_id, phone, status, error=None):
    """Insert a record into reminder_log."""
    get_reminder_log_collection().insert_one({
        "event_id": event_id,
        "recipient_phone": phone,
        "sent_at": datetime.now(tz),
        "status": status,
        "error": error,
    })


def advance_recurring_event(event):
    """
    For recurring events whose event_date has already passed,
    advance event_date to the same month/day next year.
    """
    events_col = get_events_collection()
    old_date = event["event_date"]
    try:
        new_date = old_date.replace(year=old_date.year + 1)
    except ValueError:
        # handles Feb 29 -> Feb 28
        new_date = old_date.replace(year=old_date.year + 1, day=28)

    events_col.update_one(
        {"_id": event["_id"]},
        {"$set": {"event_date": new_date, "updated_at": datetime.now(tz)}},
    )
    logger.info("Recurring event '%s' advanced: %s -> %s", event["name"], old_date.date(), new_date.date())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(force=False):
    """
    Args:
        force: If True, send reminders for ALL active events regardless of date.
               Useful for testing.
    """
    today = get_today()
    logger.info("=== Reminder check for %s %s===", today, "(FORCE MODE) " if force else "")

    templates = load_templates()
    events_col = get_events_collection()
    active_events = list(events_col.find({"is_active": True}))
    logger.info("Found %d active events.", len(active_events))

    total_sent = 0
    total_failed = 0

    for event in active_events:
        event_date = event["event_date"].date() if isinstance(event["event_date"], datetime) else event["event_date"]
        days_left = (event_date - today).days

        # days_prior can be a single int or a list of ints (e.g. [0, 1] for same day + 1 day before)
        raw_days_prior = event.get("days_prior", 1)
        if isinstance(raw_days_prior, list):
            days_prior_list = raw_days_prior
        else:
            days_prior_list = [raw_days_prior]

        # Check if today matches ANY of the reminder days (skip check in force mode)
        if not force:
            reminder_dates = [event_date - timedelta(days=d) for d in days_prior_list]
            if today not in reminder_dates:
                continue
        else:
            logger.info("FORCE: Including event '%s' (event_date=%s, %d days away)", event["name"], event_date, days_left)

        event_type = event.get("event_type", "other")
        template = templates.get(event_type, templates.get("other", "Reminder: {event_name} on {event_date}"))

        recipients = get_recipients_for_event(event)
        if not recipients:
            logger.warning("Event '%s' has no recipients — skipping.", event["name"])
            continue

        logger.info("Sending reminders for '%s' (%s) to %d recipient(s).", event["name"], event_type, len(recipients))

        for recipient in recipients:
            phone = recipient["phone"]

            if not force and already_sent_today(event["_id"], phone, today):
                logger.info("  Already sent to %s today — skipping.", phone)
                continue

            body = build_message(template, event, recipient, days_left)
            sid, error = send_whatsapp(phone, body)

            if sid:
                logger.info("  Sent to %s (SID: %s)", phone, sid)
                log_reminder(event["_id"], phone, "sent")
                total_sent += 1
            else:
                logger.error("  Failed to send to %s: %s", phone, error)
                log_reminder(event["_id"], phone, "failed", error)
                total_failed += 1

    # Advance recurring events whose date has passed (skip in force mode)
    if not force:
        for event in active_events:
            if not event.get("is_recurring"):
                continue
            event_date = event["event_date"].date() if isinstance(event["event_date"], datetime) else event["event_date"]
            if event_date < today:
                advance_recurring_event(event)

    logger.info("=== Done. Sent: %d, Failed: %d ===", total_sent, total_failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send WhatsApp reminders")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send reminders for ALL active events regardless of date (for testing)",
    )
    args = parser.parse_args()
    run(force=args.force)
