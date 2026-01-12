#!/usr/bin/env python3
"""
Daily ad-hoc SAM.gov query:
  (voice OR voip OR cisco OR webex OR ccum OR data)  AND  response due ≤ 90 days
→ CSV → Gmail (App-Password)  –  zero external providers.
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
SAM_KEY   = os.getenv("SAM_API_KEY")          # sam.gov API key
GMAIL_USER= os.getenv("GMAIL_USER")           # you@gmail.com
GMAIL_PASS= os.getenv("GMAIL_APP_PASS")       # 16-char app password
TO_EMAIL  = os.getenv("TO_EMAIL")             # comma-separated
# ------------------------------------------------------------------

SAM_BASE = "https://api.sam.gov/prod/opportunities/v2/search"

def fetch_opps1():
    """Build the same ad-hoc query you had in the browser."""
    tomorrow   = dt.date.today()
    three_mo   = tomorrow + dt.timedelta(days=90)

    params = dict(
        api_key=SAM_KEY,
        q="(voice OR voip OR cisco OR webex OR ccum OR data)",  # keywords
        postedFrom=tomorrow.isoformat(),
        postedTo=three_mo.isoformat(),
        responseDeadLineFrom=tomorrow.isoformat(),
        responseDeadLineTo=three_mo.isoformat(),
        limit=1000,
        sort="-modifiedDate"
    )
    r = requests.get(SAM_BASE, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("opportunities", [])

def fetch_opps():
    """Fetch opportunities with proper date format and error handling."""
    tomorrow = dt.date.today()
    three_mo = tomorrow + dt.timedelta(days=90)

    def fmt(d):
        return d.strftime("%m/%d/%Y")

    params = {
        "api_key": SAM_KEY,
        "q": "(voice OR voip OR cisco OR webex OR ccum OR data)",
        "postedFrom": fmt(tomorrow),
        "postedTo": fmt(three_mo),
        "responseDeadLineFrom": fmt(tomorrow),
        "responseDeadLineTo": fmt(three_mo),
        "limit": 1000,
        "sort": "-modifiedDate"
    }

    r = requests.get(SAM_BASE, params=params, timeout=60)
    print(f"Request URL: {r.url}")  # Debug
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(f"Error response: {r.text}")
    r.raise_for_status()
    
    data = r.json()
    return data.get("opportunities", [])

def build_csv(opps):
    if not opps:
        opps = [{"NoticeId": "none", "Title": "No matching opportunities"}]
    fieldnames = ["NoticeId", "Title", "Department", "SubTier", "Type",
                  "PostedDate", "ResponseDeadLine", "uiLink"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for o in opps:
        writer.writerow({k: o.get(k, "") for k in fieldnames})
    return buf.getvalue()

def send_mail(csv_string: str, filename: str):
    msg = MIMEMultipart()
    msg["Subject"] = f"SAM daily voice/VoIP/Cisco filter {dt.date.today():%Y-%m-%d}"
    msg["From"] = GMAIL_USER
    msg["To"]   = TO_EMAIL

    body = "CSV attached for today’s keyword filter (voice / voip / cisco / webex / ccum / data)."
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
    print("✓  Daily ad-hoc CSV e-mailed via Gmail")

def main():
    opps     = fetch_opps()
    csv_data = build_csv(opps)
    file_name= f"sam_voice_filter_{dt.date.today():%Y%m%d}.csv"
    send_mail(csv_data, file_name)

if __name__ == "__main__":
    main()
