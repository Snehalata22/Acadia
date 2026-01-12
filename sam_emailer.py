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

# --- CONFIG ---
SAM_KEY    = os.getenv("SAM_API_KEY")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASS")
TO_EMAIL   = os.getenv("TO_EMAIL")

# FIX: Correct endpoint (no /prod path)
SAM_BASE = "https://api.sam.gov/opportunities/v2/search"

def fetch_opps():
    """Fetch opportunities using OFFICIAL API parameters"""
    tomorrow = dt.date.today()
    three_mo = tomorrow + dt.timedelta(days=90)
    
    # FIX: Proper MM/dd/yyyy format
    def fmt(d):
        return d.strftime("%m/%d/%Y")
    
    # FIX: Use correct parameter names from documentation
    params = {
        "api_key": SAM_KEY,
        "postedFrom": fmt(tomorrow),    # Required with limit
        "postedTo": fmt(three_mo),      # Required with limit
        "rdlfrom": fmt(tomorrow),       # Correct param name
        "rdlto": fmt(three_mo),         # Correct param name
        "title": "(voice OR voip OR cisco OR webex OR ccum OR data)",  # Use title, not q
        "limit": 1000,
        "offset": 0
    }
    
    # Debug: show what we're actually sending
    print(f"DEBUG: Requesting: {requests.Request('GET', SAM_BASE, params=params).url}")
    
    r = requests.get(SAM_BASE, params=params, timeout=60)
    print(f"DEBUG: Response status: {r.status_code}")
    
    if r.status_code != 200:
        print(f"ERROR: {r.text[:500]}")
        r.raise_for_status()
    
    data = r.json()
    # FIX: Correct response key from documentation
    return data.get("opportunitiesData", [])

def build_csv(opps):
    if not opps:
        opps = [{"noticeId": "none", "title": "No matching opportunities"}]
    
    fieldnames = ["noticeId", "title", "department", "subTier", "type",
                  "postedDate", "reponseDeadLine", "uiLink"]
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
    msg["To"] = TO_EMAIL

    body = "CSV attached for today's keyword filter (voice / voip / cisco / webex / ccum / data)."
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
    print("✓ Email sent successfully")

def main():
    print("=== Starting SAM.gov scraper ===")
    
    # Check environment
    required = [SAM_KEY, GMAIL_USER, GMAIL_PASS, TO_EMAIL]
    if not all(required):
        print("❌ Missing environment variables!")
        print(f"SAM_API_KEY: {'✓' if SAM_KEY else 'MISSING'}")
        print(f"GMAIL_USER: {'✓' if GMAIL_USER else 'MISSING'}")
        print(f"GMAIL_APP_PASS: {'✓' if GMAIL_PASS else 'MISSING'}")
        print(f"TO_EMAIL: {'✓' if TO_EMAIL else 'MISSING'}")
        return 1
    
    print("Step 1: Fetching opportunities...")
    opps = fetch_opps()
    print(f"Found {len(opps)} opportunities")
    
    print("Step 2: Building CSV...")
    csv_data = build_csv(opps)
    
    print("Step 3: Sending email...")
    file_name = f"sam_voice_filter_{dt.date.today():%Y%m%d}.csv"
    send_mail(csv_data, file_name)
    
    print("=== Success ===")
    return 0

if __name__ == "__main__":
    exit(main())
