import os
import csv
import io
import datetime as dt
import requests
import base64
import sendgrid
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, To, From

# --- CONFIG ---
SAM_KEY      = os.getenv("SAM_API_KEY")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL   = os.getenv("FROM_EMAIL")
TO_EMAIL     = os.getenv("TO_EMAIL")

# ENSURE: No trailing space in URL
SAM_BASE = "https://api.sam.gov/opportunities/v2/search"

def fetch_opps():
    """Fetch opportunities"""
    start_date = dt.date.today() - dt.timedelta(days=7)
    end_date = dt.date.today() + dt.timedelta(days=30)
    
    def fmt(d):
        return d.strftime("%m/%d/%Y")
    
    keywords = ["voice", "voip", "cisco", "webex", "ccum", "data"]
    all_opps = []
    
    print(f"DEBUG: Searching for keywords: {keywords}")
    
    for keyword in keywords:
        params = {
            "api_key": SAM_KEY,
            "postedFrom": fmt(start_date),
            "postedTo": fmt(end_date),
            "title": keyword,
            "limit": 200,
            "offset": 0
        }
        
        r = requests.get(SAM_BASE, params=params, timeout=60)
        
        if r.status_code == 200:
            opps = r.json().get("opportunitiesData", [])
            print(f"  - '{keyword}': {len(opps)} opportunities")
            all_opps.extend(opps)
        else:
            print(f"  - ERROR for '{keyword}': {r.status_code}")
    
    # Remove duplicates by noticeId
    unique_opps = {o["noticeId"]: o for o in all_opps}.values()
    print(f"✓ Total unique opportunities: {len(unique_opps)}")
    return list(unique_opps)

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
    """Send email via SendGrid with VERBOSE logging"""
    try:
        # ============================================
        # EMAIL ADDRESS VERIFICATION PRINTS
        # ============================================
        print("\n" + "="*50)
        print("EMAIL CONFIGURATION VERIFICATION")
        print("="*50)
        print(f"FROM_EMAIL: {FROM_EMAIL}")
        # Parse comma-separated TO_EMAIL
        to_emails_list = [email.strip() for email in TO_EMAIL.split(',')]
        print(f"📧 Sending to:   {', '.join(to_emails_list)}\n")
        #print(f"TO_EMAIL:   {TO_EMAIL}")
        print(f"SENDGRID_KEY: {'*' * len(SENDGRID_KEY) if SENDGRID_KEY else 'NOT SET'}")
        print(f"FROM_VERIFIED: {FROM_EMAIL == TO_EMAIL}")
        print("="*50 + "\n")
  
    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
    
    mail = Mail(
        from_email=From(FROM_EMAIL),
        to_emails=[To(email) for email in to_emails_list],
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
        
        print("DEBUG: Sending to SendGrid...")
        response = sg.send(mail)
        print(f"DEBUG: SendGrid response status: {response.status_code}")
        print(f"DEBUG: SendGrid response body: {response.body}")
        print(f"DEBUG: SendGrid response headers: {dict(response.headers)}")
        
        if response.status_code == 202:
            print("✓ Email ACCEPTED by SendGrid (status 202)")
            print(f"  📧 FROM: {FROM_EMAIL}")
            print(f"  📧 Sending to:   {', '.join(to_emails_list)}\n")
            print("  ⚠️  This means API call succeeded but doesn't guarantee delivery")
            print("  🔍 Check your spam folder!")
            print("  🔍 Check SendGrid dashboard: Activity → Email Activity")
        
    except Exception as e:
        print(f"❌ SendGrid error: {e}")
        print("\n=== TROUBLESHOOTING ===")
        print("SendGrid Account Status:")
        print("- Free accounts: Must verify recipient email first")
        print("- Go to: Settings → Sender Authentication → Trusted Contacts")
        print(f"- Add {TO_EMAIL} as trusted contact")
        print("\nEmail Verification:")
        print("- FROM_EMAIL must be verified in SendGrid")
        print("- Check: Settings → Sender Authentication → Single Sender")
        print("\nAPI Key:")
        print("- Must have 'Mail Send' permission")
        print("\nQUICK FIX: Set FROM_EMAIL = TO_EMAIL for testing")
        raise

def main():
    print("=== Starting SAM.gov scraper (SendGrid Version) ===")
    
    # ============================================
    # ENVIRONMENT VARIABLE VERIFICATION
    # ============================================
    print("\n" + "="*50)
    print("ENVIRONMENT VARIABLES")
    print("="*50)
    print(f"SAM_API_KEY:      {'✓ SET' if SAM_KEY else '❌ MISSING'}")
    print(f"SENDGRID_API_KEY: {'✓ SET' if SENDGRID_KEY else '❌ MISSING'}")
    print(f"FROM_EMAIL:       {FROM_EMAIL if FROM_EMAIL else '❌ MISSING'}")
    print(f"TO_EMAIL:         {TO_EMAIL if TO_EMAIL else '❌ MISSING'}")
    print("="*50 + "\n")
    
    required = [SAM_KEY, SENDGRID_KEY, FROM_EMAIL, TO_EMAIL]
    if not all(required):
        print("❌ Missing required environment variables!")
        return 1
    
    print("Step 1: Fetching opportunities...")
    opps = fetch_opps()
    print(f"Found {len(opps)} opportunities")
    
    print("Step 2: Building CSV...")
    csv_data = build_csv(opps)
    print(f"CSV size: {len(csv_data)} bytes")
    
    # DEBUG: Print first few lines of CSV
    csv_lines = csv_data.split('\n')[:5]
    print("CSV preview:")
    for line in csv_lines:
        print(f"  {line[:80]}...")
    
    print("Step 3: Sending email via SendGrid...")
    file_name = f"sam_voice_filter_{dt.date.today():%Y%m%d}.csv"
    send_mail(csv_data, file_name)
    
    print("=== Success ===")
    return 0

if __name__ == "__main__":
    exit(main())
