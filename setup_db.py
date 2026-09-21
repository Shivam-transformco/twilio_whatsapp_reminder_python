"""
One-time setup script to:
  1. Create MongoDB indexes
  2. Seed default message templates
  3. Optionally seed sample events and recipients

MongoDB Schema:

events {
    _id: ObjectId,
    name: str,                    # e.g. "Diwali Celebration"
    event_type: str,              # "birthday" | "camp" | "class" | "festival" | "other"
    event_date: datetime,         # the actual date/time of the event
    is_recurring: bool,           # true for yearly events like birthdays/festivals
    days_prior: int,              # how many days before the event to send reminder
    description: str,             # optional extra info
    recipient_ids: [ObjectId],    # list of recipient _ids (if empty, send to ALL recipients)
    is_active: bool,              # toggle to disable an event without deleting
    created_at: datetime,
    updated_at: datetime
}

recipients {
    _id: ObjectId,
    name: str,                    # e.g. "Shivam"
    phone: str,                   # WhatsApp number with country code e.g. "+919876543210"
    is_active: bool,
    created_at: datetime
}

message_templates {
    _id: ObjectId,
    event_type: str,              # unique key matching events.event_type
    template: str,                # message body with {placeholders}
    created_at: datetime,
    updated_at: datetime
}

reminder_log {
    _id: ObjectId,
    event_id: ObjectId,
    recipient_phone: str,
    sent_at: datetime,
    status: str,                  # "sent" | "failed"
    error: str | None
}

Template placeholders:
    {event_name}   - name of the event
    {event_date}   - formatted date of the event
    {days_left}    - days remaining until the event
    {description}  - event description
    {recipient}    - recipient name
"""

from datetime import datetime, timedelta
import pytz
from db import (
    get_events_collection,
    get_recipients_collection,
    get_templates_collection,
    get_reminder_log_collection,
)
from config import TIMEZONE

tz = pytz.timezone(TIMEZONE)

DEFAULT_TEMPLATES = [
    {
        "event_type": "birthday",
        "template": (
            "🎂 *Birthday Reminder!*\n\n"
            "Hi {recipient}, just a reminder that *{event_name}* is coming up on *{event_date}*.\n"
            "Only *{days_left} day(s)* left!\n\n"
            "{description}"
        ),
    },
    {
        "event_type": "camp",
        "template": (
            "🏕️ *Camp Reminder!*\n\n"
            "Hi {recipient}, the camp *{event_name}* is on *{event_date}*.\n"
            "That's *{days_left} day(s)* away. Get ready!\n\n"
            "{description}"
        ),
    },
    {
        "event_type": "class",
        "template": (
            "📚 *Class Reminder!*\n\n"
            "Hi {recipient}, the class *{event_name}* is scheduled for *{event_date}*.\n"
            "*{days_left} day(s)* to go.\n\n"
            "{description}"
        ),
    },
    {
        "event_type": "festival",
        "template": (
            "🎉 *Festival Reminder!*\n\n"
            "Hi {recipient}, *{event_name}* is on *{event_date}*!\n"
            "Only *{days_left} day(s)* left to prepare.\n\n"
            "{description}"
        ),
    },
    {
        "event_type": "other",
        "template": (
            "📌 *Event Reminder!*\n\n"
            "Hi {recipient}, *{event_name}* is coming up on *{event_date}*.\n"
            "*{days_left} day(s)* remaining.\n\n"
            "{description}"
        ),
    },
]


def create_indexes():
    """Create useful indexes on all collections."""
    events = get_events_collection()
    events.create_index("event_date")
    events.create_index("event_type")
    events.create_index("is_active")

    recipients = get_recipients_collection()
    recipients.create_index("phone", unique=True)

    templates = get_templates_collection()
    templates.create_index("event_type", unique=True)

    log = get_reminder_log_collection()
    log.create_index([("event_id", 1), ("recipient_phone", 1), ("sent_at", 1)])

    print("[OK] Indexes created.")


def seed_templates():
    """Insert default message templates (skip if already exist)."""
    templates = get_templates_collection()
    now = datetime.now(tz)
    inserted = 0
    for t in DEFAULT_TEMPLATES:
        if not templates.find_one({"event_type": t["event_type"]}):
            templates.insert_one({**t, "created_at": now, "updated_at": now})
            inserted += 1
    print(f"[OK] Templates seeded ({inserted} new, {len(DEFAULT_TEMPLATES) - inserted} already existed).")


def seed_sample_data():
    """Insert sample events and recipients for testing."""
    recipients_col = get_recipients_collection()
    events_col = get_events_collection()
    now = datetime.now(tz)

    # Sample recipient
    sample_recipient = {
        "name": "Shivam",
        "phone": "+919876543210",
        "is_active": True,
        "created_at": now,
    }
    result = recipients_col.update_one(
        {"phone": sample_recipient["phone"]},
        {"$setOnInsert": sample_recipient},
        upsert=True,
    )
    recipient_id = result.upserted_id
    if recipient_id is None:
        recipient_id = recipients_col.find_one({"phone": sample_recipient["phone"]})["_id"]

    # Sample events (relative to today so they're useful for testing)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    sample_events = [
        {
            "name": "Shivam's Birthday",
            "event_type": "birthday",
            "event_date": today + timedelta(days=3),
            "is_recurring": True,
            "days_prior": 3,
            "description": "Don't forget to wish!",
            "recipient_ids": [recipient_id],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Summer Art Camp",
            "event_type": "camp",
            "event_date": today + timedelta(days=7),
            "is_recurring": False,
            "days_prior": 7,
            "description": "Venue: Community Hall, 9 AM - 5 PM",
            "recipient_ids": [],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "name": "Diwali",
            "event_type": "festival",
            "event_date": today + timedelta(days=5),
            "is_recurring": True,
            "days_prior": 5,
            "description": "Festival of lights!",
            "recipient_ids": [],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]

    inserted = 0
    for evt in sample_events:
        if not events_col.find_one({"name": evt["name"]}):
            events_col.insert_one(evt)
            inserted += 1
    print(f"[OK] Sample data seeded ({inserted} events, 1 recipient).")


if __name__ == "__main__":
    print("Setting up database...")
    create_indexes()
    seed_templates()

    resp = input("Seed sample data for testing? (y/n): ").strip().lower()
    if resp == "y":
        seed_sample_data()

    print("\nDone! Your database is ready.")
