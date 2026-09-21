# Bace WhatsApp Reminder Bot

Automated WhatsApp reminder notifications for events like Birthdays, Camps, Classes, Festivals, etc. using **Twilio WhatsApp API** and **MongoDB**.

## Architecture

```
Cron (7 AM IST daily)
  └─ send_reminders.py
       ├─ Reads active events from MongoDB
       ├─ Checks if today == event_date - days_prior
       ├─ Fetches recipients (per-event or all)
       ├─ Renders message from per-type templates
       ├─ Sends via Twilio WhatsApp API
       ├─ Logs to reminder_log (avoids duplicate sends)
       └─ Auto-advances recurring events past their date
```

## MongoDB Schema

### `events` collection
| Field          | Type         | Description                                    |
|----------------|--------------|------------------------------------------------|
| name           | string       | Event name (e.g. "Diwali")                     |
| event_type     | string       | `birthday`, `camp`, `class`, `festival`, `other` |
| event_date     | datetime     | Actual date of the event                       |
| is_recurring   | bool         | Yearly recurring (birthdays, festivals)        |
| days_prior     | int          | Send reminder this many days before the event  |
| description    | string       | Optional details                               |
| recipient_ids  | [ObjectId]   | Specific recipients (empty = send to ALL)      |
| is_active      | bool         | Toggle without deleting                        |

### `recipients` collection
| Field   | Type   | Description                           |
|---------|--------|---------------------------------------|
| name    | string | Recipient name                        |
| phone   | string | WhatsApp number (e.g. `+919876543210`)|
| is_active | bool | Toggle recipient                      |

### `message_templates` collection
| Field      | Type   | Description                     |
|------------|--------|---------------------------------|
| event_type | string | Matches `events.event_type`     |
| template   | string | Message with `{placeholders}`   |

**Placeholders:** `{event_name}`, `{event_date}`, `{days_left}`, `{description}`, `{recipient}`

### `reminder_log` collection
Tracks every send attempt to prevent duplicate messages on re-runs.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
MONGO_URI=mongodb+srv://...
MONGO_DB_NAME=bace_reminders
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TIMEZONE=Asia/Kolkata
```

### 3. Initialize database

```bash
python setup_db.py
```

This creates indexes, seeds default message templates, and optionally adds sample data.

### 4. Add recipients and events

```bash
# Add a recipient
python manage.py add-recipient --name "Shivam" --phone "+919876543210"

# Add an event (birthday, remind 3 days before, recurring yearly)
python manage.py add-event \
  --name "Ravi's Birthday" \
  --type birthday \
  --date 2026-11-15 \
  --days-prior 3 \
  --recurring \
  --description "Don't forget the cake!"

# Add a one-time camp event, remind 7 days before
python manage.py add-event \
  --name "Winter Camp" \
  --type camp \
  --date 2026-12-20 \
  --days-prior 7 \
  --description "Bring warm clothes" \
  --recipients "+919876543210,+919876543211"

# List everything
python manage.py list-events
python manage.py list-recipients
```

### 5. Test Twilio setup

```bash
python manage.py test-send --phone "+919876543210"
```

### 6. Run manually

```bash
python send_reminders.py
```

### 7. Set up cron (7 AM IST daily)

```bash
crontab -e
```

Add this line (adjust the path):

```cron
30 1 * * * cd /Users/sshivam/Personal\ projects/Bace_Whatsapp_script && /usr/bin/python3 send_reminders.py >> cron.log 2>&1
```

> **Note:** `30 1 * * *` = 1:30 AM UTC = 7:00 AM IST. Adjust if your server timezone differs.

## Management Commands

| Command                                          | Description                  |
|--------------------------------------------------|------------------------------|
| `python manage.py add-recipient --name --phone`  | Add a WhatsApp recipient     |
| `python manage.py list-recipients`               | List all recipients          |
| `python manage.py add-event ...`                 | Add a new event              |
| `python manage.py list-events`                   | List all events              |
| `python manage.py deactivate-event --name`       | Disable an event             |
| `python manage.py activate-event --name`         | Re-enable an event           |
| `python manage.py test-send --phone`             | Send a test WhatsApp message |

## File Structure

```
.
├── .env                  # Your secrets (git-ignored)
├── .env.example          # Template for .env
├── .gitignore
├── config.py             # Loads environment variables
├── db.py                 # MongoDB connection helpers
├── manage.py             # CLI to manage events & recipients
├── send_reminders.py     # Main script (run via cron)
├── setup_db.py           # One-time DB setup & seeding
├── requirements.txt
└── README.md
```
