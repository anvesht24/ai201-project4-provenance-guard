import json
import os
from datetime import datetime, timezone

LOG_FILE = "audit_log.json"

def _load_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def _save_log(entries):
    with open(LOG_FILE, "w") as f:
        json.dump(entries, f, indent=2)

def add_log_entry(entry: dict):
    """Appends a structured entry to the audit log file."""
    entries = _load_log()
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    entries.append(entry)
    _save_log(entries)

def get_log(limit: int = 50):
    """Returns the most recent log entries, newest first."""
    entries = _load_log()
    return list(reversed(entries))[:limit]

def update_log_entry(content_id: str, updates: dict) -> bool:
    """
    Finds the log entry matching content_id and updates it with the given 
    fields (e.g., status, appeal_reasoning). Returns True if found and 
    updated, False if no matching content_id exists.
    """
    entries = _load_log()
    found = False
    for entry in entries:
        if entry.get("content_id") == content_id:
            entry.update(updates)
            found = True
            break
    if found:
        _save_log(entries)
    return found