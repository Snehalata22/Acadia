#!/usr/bin/env python3
"""
Poll SAM.gov saved-search → CSV → e-mail  via  SendGrid  API.
"""
import os, csv, io, datetime as dt, requests, base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

SAM_KEY   = os.getenv("SAM_API_KEY")
SEARCH_ID = os.getenv("SAVED_SEARCH_ID", "12345")   # id from URL
FROM      = os.getenv("FROM_EMAIL")
TO        = os.getenv("TO_EMAIL").split(",")

def fetch_opps():
    url = "https://api.sam.gov/prod/opportunities/v2/search"
    params = dict(api_key=SAM_KEY, savedSearchId=SEARCH_ID,
                  postedFrom=(dt.date.today()-dt.timedelta(days=30)).isoformat(),
                  postedTo=dt.date.today().isoformat(), limit=1000)
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("opportunities", [])

def build_csv(opps):
    if not opps:
        opps = [{"NoticeId":"none","Title":"No new records"}]
    fieldnames = ["NoticeId","Title","Department","SubTier","Type",
                  "PostedDate","ResponseDeadLine","uiLink"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for o in opps:
        writer.writerow({k:o.get(k,"") for k in fieldnames})
    return buf.getvalue()

def send_csv_mail(csv_string, filename):
    mail = Mail(from_email=FROM, to_emails=TO,
                subject=f"SAM opportunities {dt.date.today():%Y-%m-%d}",
                plain_text_content="See attached CSV for today’s opportunities.")
    # build attachment
    attachment = Attachment(
        file_content=FileContent(base64.b64encode(csv_string.encode()).decode()),
        file_name=FileName(filename),
        file_type=FileType("text/csv"),
        disposition=Disposition("attachment"))
    mail.add_attachment(attachment)
    SendGridAPIClient(os.getenv("SENDGRID_API_KEY")).send(mail)
    print("✓  Mail sent via SendGrid")

if __name__ == "__main__":
    opps = fetch_opps()
    csv_data = build_csv(opps)
    send_csv_mail(csv_data, f"sam_opps_{dt.date.today():%Y%m%d}.csv")