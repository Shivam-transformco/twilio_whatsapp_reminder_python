"""
CLI utility to manage events and recipients.

Usage:
    python manage.py add-recipient --name "Shivam" --phone "+919876543210"
    python manage.py list-recipients
    python manage.py add-event --name "Diwali" --type festival --date 2026-10-20 --days-prior 5 --recurring
    python manage.py list-events
    python manage.py deactivate-event --name "Diwali"
    python manage.py test-send --phone "+919876543210"
"""

import argparse
from datetime import datetime
import pytz
from bson import ObjectId

from config import TIMEZONE
from db import (
    get_events_collection,
    get_recipients_collection,
    get_templates_collection,
)

tz = pytz.timezone(TIMEZONE)


def add_recipient(args):
    col = get_recipients_collection()
    doc = {
        "name": args.name,
        "phone": args.phone,
        "is_active": True,
        "created_at": datetime.now(tz),
    }
    result = col.update_one({"phone": args.phone}, {"$setOnInsert": doc}, upsert=True)
    if result.upserted_id:
        print(f"Added recipient: {args.name} ({args.phone})")
    else:
        print(f"Recipient with phone {args.phone} already exists.")


def list_recipients(args):
    col = get_recipients_collection()
    for r in col.find():
        status = "active" if r.get("is_active") else "inactive"
        print(f"  [{status}] {r['name']} — {r['phone']}  (id: {r['_id']})")


def add_event(args):
    col = get_events_collection()
    now = datetime.now(tz)
    event_date = datetime.strptime(args.date, "%Y-%m-%d")
    event_date = tz.localize(event_date)

    # Resolve recipient IDs if provided
    recipient_ids = []
    if args.recipients:
        recipients_col = get_recipients_collection()
        for phone in args.recipients.split(","):
            phone = phone.strip()
            r = recipients_col.find_one({"phone": phone})
            if r:
                recipient_ids.append(r["_id"])
            else:
                print(f"Warning: recipient with phone {phone} not found — skipping.")

    # Parse days_prior: "1" -> 1, "0,1,3" -> [0, 1, 3]
    days_prior_parts = [int(x.strip()) for x in args.days_prior.split(",")]
    days_prior = days_prior_parts[0] if len(days_prior_parts) == 1 else days_prior_parts

    doc = {
        "name": args.name,
        "event_type": args.type,
        "event_date": event_date,
        "is_recurring": args.recurring,
        "days_prior": days_prior,
        "description": args.description or "",
        "recipient_ids": recipient_ids,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    col.insert_one(doc)
    print(f"Added event: {args.name} on {args.date} (remind {days_prior} day(s) prior)")


def list_events(args):
    col = get_events_collection()
    for e in col.find().sort("event_date", 1):
        status = "active" if e.get("is_active") else "inactive"
        recurring = "recurring" if e.get("is_recurring") else "one-time"
        date_str = e["event_date"].strftime("%Y-%m-%d")
        dp = e.get("days_prior", 1)
        dp_str = ",".join(str(d) for d in dp) + "d" if isinstance(dp, list) else f"{dp}d"
        print(
            f"  [{status}] {e['name']} — {date_str} | type: {e['event_type']} | "
            f"remind: {dp_str} prior | {recurring}"
        )


def deactivate_event(args):
    col = get_events_collection()
    result = col.update_one({"name": args.name}, {"$set": {"is_active": False, "updated_at": datetime.now(tz)}})
    if result.modified_count:
        print(f"Deactivated event: {args.name}")
    else:
        print(f"Event '{args.name}' not found or already inactive.")


def activate_event(args):
    col = get_events_collection()
    result = col.update_one({"name": args.name}, {"$set": {"is_active": True, "updated_at": datetime.now(tz)}})
    if result.modified_count:
        print(f"Activated event: {args.name}")
    else:
        print(f"Event '{args.name}' not found or already active.")


def test_send(args):
    """Send a test WhatsApp message to verify Twilio setup."""
    from twilio.rest import Client
    from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{args.phone}",
            body="Hello! This is a test message from Bace WhatsApp Reminder Bot.",
        )
        print(f"Test message sent! SID: {msg.sid}")
    except Exception as e:
        print(f"Failed to send test message: {e}")


def main():
    parser = argparse.ArgumentParser(description="Manage WhatsApp reminder events and recipients")
    sub = parser.add_subparsers(dest="command")

    # add-recipient
    p = sub.add_parser("add-recipient")
    p.add_argument("--name", required=True)
    p.add_argument("--phone", required=True, help='Phone with country code, e.g. "+919876543210"')

    # list-recipients
    sub.add_parser("list-recipients")

    # add-event
    p = sub.add_parser("add-event")
    p.add_argument("--name", required=True, help="Event name")
    p.add_argument("--type", required=True, choices=["birthday", "camp", "class", "festival", "other"])
    p.add_argument("--date", required=True, help="Event date in YYYY-MM-DD format")
    p.add_argument("--days-prior", default="1", help='Days before event to send reminder. Comma-separated for multiple, e.g. "0,1" (default: 1)')
    p.add_argument("--recurring", action="store_true", help="Mark as yearly recurring event")
    p.add_argument("--description", default="", help="Optional description")
    p.add_argument("--recipients", default="", help='Comma-separated phone numbers, e.g. "+91...,+91..."')

    # list-events
    sub.add_parser("list-events")

    # deactivate-event
    p = sub.add_parser("deactivate-event")
    p.add_argument("--name", required=True)

    # activate-event
    p = sub.add_parser("activate-event")
    p.add_argument("--name", required=True)

    # test-send
    p = sub.add_parser("test-send")
    p.add_argument("--phone", required=True, help='Phone number to send test message to, e.g. "+919876543210"')

    args = parser.parse_args()

    commands = {
        "add-recipient": add_recipient,
        "list-recipients": list_recipients,
        "add-event": add_event,
        "list-events": list_events,
        "deactivate-event": deactivate_event,
        "activate-event": activate_event,
        "test-send": test_send,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
