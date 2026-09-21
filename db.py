"""
MongoDB connection and collection helpers.

Collections:
  - events: stores event details with reminder configuration
  - recipients: stores WhatsApp recipient numbers
  - message_templates: stores per-event-type message templates
  - reminder_log: tracks sent reminders to avoid duplicates
"""

import certifi
from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB_NAME

_client = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    return _client


def get_db():
    return get_client()[MONGO_DB_NAME]


def get_events_collection():
    return get_db()["events"]


def get_recipients_collection():
    return get_db()["recipients"]


def get_templates_collection():
    return get_db()["message_templates"]


def get_reminder_log_collection():
    return get_db()["reminder_log"]
