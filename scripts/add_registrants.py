#!/usr/bin/env python3
"""Add registrants to a WebinarFuel webinar and tag them.

Usage:
  WEBINARFUEL_API_KEY=... python3 scripts/add_registrants.py WEBINAR_ID leads.tsv "tag1,tag2" [--dry-run]

leads.tsv: tab-separated, columns: full name, email, phone (extra columns ignored).
"""
import csv, json, os, sys, urllib.request, urllib.error

BASE = "https://api.webinarfuel.com"
KEY = os.environ.get("WEBINARFUEL_API_KEY")
TIMEZONE = os.environ.get("WEBINARFUEL_TIMEZONE", "Europe/Oslo")


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if len(args) != 3 or not KEY:
        sys.exit(__doc__)
    webinar_id, path, tags = args[0], args[1], [t.strip() for t in args[2].split(",") if t.strip()]

    status, data = call("GET", f"/webinars/{webinar_id}")
    if status != 200:
        sys.exit(f"Could not load webinar {webinar_id}: HTTP {status} {data}")
    webinar = data.get("webinar", data)
    sessions = webinar.get("sessions") or []
    print(f"Webinar: {webinar.get('name')} ({len(sessions)} sessions)")
    for s in sessions[:5]:
        print(f"  session {s.get('id')}: {s.get('formatted_scheduled_at')}")
    if not sessions:
        sys.exit("No sessions found on this webinar.")
    session_id = sessions[0]["id"]

    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.reader(f, delimiter="\t") if len(r) >= 2 and "@" in r[1]]

    ok = 0
    for r in rows:
        name, email = r[0].strip(), r[1].strip()
        phone = r[2].strip() if len(r) > 2 else ""
        first, _, last = name.partition(" ")
        body = {
            "webinar_id": int(webinar_id),
            "registrant": {"email": email, "first_name": first, "last_name": last,
                           "phone": phone, "tags": tags},
            "session": {"webinar_session_id": session_id, "timezone": TIMEZONE},
        }
        if dry:
            print("DRY", json.dumps(body, ensure_ascii=False))
            continue
        status, resp = call("POST", "/registrants", body)
        if status in (200, 201):
            # Make sure the tag is set even if the registrant already existed.
            call("POST", "/registrants/add_tags", {"email": email, "tags": tags})
            ok += 1
            print(f"OK    {email}")
        else:
            print(f"FAIL  {email}: HTTP {status} {resp}")
    print(f"\nDone: {ok}/{len(rows)} added" + (" (dry run)" if dry else ""))


if __name__ == "__main__":
    main()
