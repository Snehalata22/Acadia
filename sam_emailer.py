#!/usr/bin/env python3
"""
Poll MULTIPLE SAM.gov saved-searches → one CSV per search → one e-mail per CSV
via Gmail SMTP (App-Password).  No external provider, no secrets for searches.
"""
import os
import csv
import io
import datetime as dt
import requests
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ------------------------------------------------------------------
# 1) CONFIG – only secrets are Gmail credentials
# ------------------------------------------------------------------
SAM_KEY    = os.getenv("SAM_API_KEY")           # still a secret
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASS")
TO_EMAIL   = os.getenv("TO_EMAIL")              # can be comma-separated

# 2) HARD-CODE YOUR SAVED-SEARCH IDs HERE ----------------------------
SEARCH_IDS = [124733, 125225]   # <-- add / remove / reorder
# ------------------------------------------------------------------

SAM_BASE = "https://api.sam.gov/prod/opportunities/v2/search"

def fetch_opps(search_id: int):
    params = dict(
        api_key=SAM_KEY,
        savedSearchId=search_id,
        postedFrom=(dt.date.today() - dt.timedelta(days=7)).isoformat(),
        postedTo=dt.date.today().isoformat(),
        limit=1000
    )
    r = requests.get(SAM_BASE, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("opportunities", [])

def build_csv(opps):
    if not opps:
        opps = [{"NoticeId": "none", "Title": "No new records"}]
    fieldnames = ["NoticeId", "Title", "Department", "SubTier", "Type",
                  "PostedDate", "ResponseDeadLine", "uiLink"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for o in opps:
        writer.writerow({k: o.get(k, "") for k in fieldnames})
    return buf.getvalue()

def send_mail(csv_string: str, filename: str, subject: str):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    body = f"CSV attached for saved-search run {dt.date.today()}."
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_string.encode())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
    print(f"✓  Mail sent for search {subject}")

def main():
    for search_id in SEARCH_IDS:
        print(f"---- processing search {search_id} ----")
        opps      = fetch_opps(search_id)
        csv_data  = build_csv(opps)
        file_name = f"sam_search_{search_id}_{dt.date.today():%Y%m%d}.csv"
        subject   = f"SAM opportunities search-{search_id} {dt.date.today():%Y-%m-%d}"
        send_mail(csv_data, file_name, subject)

if __name__ == "__main__":
    main()