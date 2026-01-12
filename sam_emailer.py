import os
import csv
import io
import datetime as dt
import requests
import base64  # ADD THIS
import sendgrid
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

# --- CONFIG ---
SAM_KEY      = os.getenv("SAM_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL   = os.getenv("FROM_EMAIL")
TO_EMAIL     = os.getenv("TO_EMAIL")

SAM_BASE = "https://api.sam.gov/opportunities/v2/search"

def fetch_opps():
    """Fetch opportunities using OFFICIAL API parameters"""
    tomorrow = dt.date.today()
    three_mo = tomorrow + dt.timedelta(days=90)
    
    def fmt(d):
        return d.strftime("%m/%d/%Y")
    
    params = {
        "api_key": SAM_KEY,
        "postedFrom": fmt(tomorrow),
        "postedTo": fmt(three_mo),
        "rdlfrom": fmt(tomorrow),
        "rdlto": fmt(three_mo),
        "title": "(voice OR voip OR cisco OR webex OR ccum OR data)",
        "limit": 1000,
        "offset": 0
    }
    
    print(f"DEBUG: Requesting: {requests.Request('GET', SAM_BASE, params=params).url}")
    r = requests.get(SAM_BASE, params=params, timeout=60)
    print(f"DEBUG: Response status: {r.status_code}")
    
    if r.status_code != 200:
        print(f"ERROR: {r.text[:500]}")
        r.raise_for_status()
    
    data = r.json()
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
    """Send email via SendGrid with proper base64 encoding"""
    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
    
    mail = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject=f"SAM daily filter {dt.date.today():%Y-%m-%d}",
        plain_text_content="CSV attached for today's keyword filter (voice / voip / cisco / webex / ccum / data)."
    )
    
    # FIX: Properly base64 encode the content
    encoded_csv = base64.b64encode(csv_string.encode()).decode()
    
    attachment = Attachment()
    attachment.file_content = FileContent(encoded_csv)
    attachment.file_name = FileName(filename)
    attachment.file_type = FileType("text/csv")
    attachment.disposition = Disposition("attachment")
    mail.attachment = attachment
    
    response = sg.send(mail)
    print(f"✓ Email sent via SendGrid: {response.status_code}")

def main():
    print("=== Starting SAM.gov scraper (SendGrid Version) ===")
    
    required = [SAM_KEY, SENDGRID_KEY, FROM_EMAIL, TO_EMAIL]
    if not all(required):
        print("❌ Missing environment variables!")
        print(f"SAM_API_KEY: {'✓' if SAM_KEY else 'MISSING'}")
        print(f"SENDGRID_API_KEY: {'✓' if SENDGRID_KEY else 'MISSING'}")
        print(f"FROM_EMAIL: {'✓' if FROM_EMAIL else 'MISSING'}")
        print(f"TO_EMAIL: {'✓' if TO_EMAIL else 'MISSING'}")
        return 1
    
    print("Step 1: Fetching opportunities...")
    opps = fetch_opps()
    print(f"Found {len(opps)} opportunities")
    
    print("Step 2: Building CSV...")
    csv_data = build_csv(opps)
    
    print("Step 3: Sending email via SendGrid...")
    file_name = f"sam_voice_filter_{dt.date.today():%Y%m%d}.csv"
    send_mail(csv_data, file_name)
    
    print("=== Success ===")
    return 0

if __name__ == "__main__":
    exit(main())
