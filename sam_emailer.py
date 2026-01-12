import os
import csv
import io
import datetime as dt
import requests
import base64
import sendgrid
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

# --- CONFIG ---
SAM_KEY      = os.getenv("SAM_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL   = os.getenv("FROM_EMAIL")
TO_EMAIL     = os.getenv("TO_EMAIL")

SAM_BASE = "https://api.sam.gov/opportunities/v2/search"

def fetch_opps():
    """Fetch opportunities with debug info"""
    # Try a smaller date range first - 7 days back to 30 days forward
    start_date = dt.date.today() - dt.timedelta(days=7)
    end_date = dt.date.today() + dt.timedelta(days=30)
    
    def fmt(d):
        return d.strftime("%m/%d/%Y")
    
    # Try simpler keyword first
    params = {
        "api_key": SAM_KEY,
        "postedFrom": fmt(start_date),
        "postedTo": fmt(end_date),
        "title": "cisco",  # Start with single keyword to test
        "limit": 100,
        "offset": 0
    }
    
    print(f"DEBUG: Testing with simple query: {requests.Request('GET', SAM_BASE, params=params).url}")
    r = requests.get(SAM_BASE, params=params, timeout=60)
    print(f"DEBUG: Status: {r.status_code}, Found: {len(r.json().get('opportunitiesData', []))} opportunities")
    
    # If that works, try your original complex query
    if r.status_code == 200 and len(r.json().get('opportunitiesData', [])) > 0:
        print("✓ Simple query works!")
        
        # Now try your original complex query
        params["title"] = "(voice OR voip OR cisco OR webex OR ccum OR data OR database)"
        params["limit"] = 1000
        
        print(f"DEBUG: Running full query: {requests.Request('GET', SAM_BASE, params=params).url}")
        r = requests.get(SAM_BASE, params=params, timeout=60)
        print(f"DEBUG: Status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"ERROR with complex query: {r.text[:500]}")
            return []
    
    if r.status_code != 200:
        print(f"ERROR: {r.text[:500]}")
        r.raise_for_status()
    
    data = r.json()
    opps = data.get("opportunitiesData", [])
    print(f"✓ Found {len(opps)} opportunities")
    return opps

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
    """Send email via SendGrid with error handling"""
    try:
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
        
        mail = Mail(
            from_email=FROM_EMAIL,
            to_emails=TO_EMAIL,
            subject=f"SAM daily filter {dt.date.today():%Y-%m-%d}",
            plain_text_content="CSV attached for today's keyword filter (voice / voip / cisco / webex / ccum / data)."
        )
        
        # Proper base64 encoding
        encoded_csv = base64.b64encode(csv_string.encode()).decode()
        
        attachment = Attachment()
        attachment.file_content = FileContent(encoded_csv)
        attachment.file_name = FileName(filename)
        attachment.file_type = FileType("text/csv")
        attachment.disposition = Disposition("attachment")
        mail.attachment = attachment
        
        response = sg.send(mail)
        print(f"✓ Email sent via SendGrid: {response.status_code}")
        
    except Exception as e:
        print(f"❌ SendGrid error: {e}")
        print("Check:")
        print("1. SENDGRID_API_KEY is set in GitHub Secrets")
        print("2. API key has 'Mail Send' permission")
        print("3. FROM_EMAIL is verified in SendGrid")
        print("4. TO_EMAIL is a valid recipient")
        raise

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
