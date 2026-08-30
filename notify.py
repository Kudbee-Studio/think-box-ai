#!/usr/bin/env python3
"""KUDBEE Notification System

Supports:
- Email (SMTP)
- SMS (Twilio)
- Webhook notifications

Usage:
    python3 notify.py --event "project_started" --message "Project X has begun"
    python3 notify.py --event "milestone_complete" --message "Level 1 done"
"""

import argparse
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/opt/kudbee/memory/notifications.db"

def init_db():
    conn = json.loads(open("/opt/kudbee/memory/notifications.json").read()) if os.path.exists("/opt/kudbee/memory/notifications.json") else {"notifications": [], "settings": {}}
    return conn

def save_notification(event, message, channels):
    """Save notification to database."""
    notification = {
        "id": f"notif-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "event": event,
        "message": message,
        "channels": channels,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent"
    }
    
    # Append to JSON file (simple persistence)
    db_path = "/opt/kudbee/memory/notifications.json"
    if os.path.exists(db_path):
        with open(db_path) as f:
            db = json.load(f)
    else:
        db = {"notifications": [], "settings": {}}
    
    db["notifications"].append(notification)
    
    with open(db_path, "w") as f:
        json.dump(db, f, indent=2)
    
    return notification

def send_email(to, subject, body):
    """Send email via SMTP."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_addr = os.environ.get("SMTP_FROM", smtp_user)
    
    if not smtp_host:
        return {"status": "not_configured", "message": "SMTP_HOST not set"}
    
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return {"status": "sent", "to": to}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

def send_sms(to, message):
    """Send SMS via Twilio."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    
    if not account_sid:
        return {"status": "not_configured", "message": "TWILIO_ACCOUNT_SID not set"}
    
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=message,
            from_=from_number,
            to=to
        )
        return {"status": "sent", "sid": msg.sid}
    except ImportError:
        return {"status": "not_configured", "message": "twilio package not installed"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

def send_webhook(url, payload):
    """Send webhook notification."""
    import urllib.request
    
    if not url:
        return {"status": "not_configured", "message": "Webhook URL not set"}
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": "sent", "response": resp.status}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

def notify(event, message, email_to=None, sms_to=None, webhook_url=None):
    """Send notification through all configured channels."""
    channels = []
    
    # Email
    if email_to or os.environ.get("NOTIFY_EMAIL"):
        result = send_email(email_to or os.environ.get("NOTIFY_EMAIL"), f"KUDBEE: {event}", message)
        channels.append({"channel": "email", **result})
    
    # SMS
    if sms_to or os.environ.get("NOTIFY_SMS"):
        result = send_sms(sms_to or os.environ.get("NOTIFY_SMS"), f"KUDBEE: {event} - {message}")
        channels.append({"channel": "sms", **result})
    
    # Webhook
    if webhook_url or os.environ.get("WEBHOOK_URL"):
        result = send_webhook(webhook_url or os.environ.get("WEBHOOK_URL"), {
            "event": event,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        channels.append({"channel": "webhook", **result})
    
    # Save to database
    notification = save_notification(event, message, channels)
    
    return notification

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KUDBEE Notification System")
    parser.add_argument("--event", required=True, help="Event type (e.g., project_started)")
    parser.add_argument("--message", required=True, help="Notification message")
    parser.add_argument("--email", help="Email recipient")
    parser.add_argument("--sms", help="SMS recipient (phone number)")
    parser.add_argument("--webhook", help="Webhook URL")
    
    args = parser.parse_args()
    
    result = notify(args.event, args.message, args.email, args.sms, args.webhook)
    print(json.dumps(result, indent=2))
