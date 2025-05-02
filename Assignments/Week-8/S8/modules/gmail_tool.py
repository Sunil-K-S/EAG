import os
import json
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CLIENT_SECRETS_FILE = os.getenv('GMAIL_CLIENT_SECRETS', 'client_secrets.json')
TOKEN_FILE = os.getenv('GMAIL_TOKEN_FILE', 'token.json')

class GmailTool:
    name = "gmail"
    description = "Send emails using Gmail API. Use for notifications, reports, and workflow outputs."
    parameters = {
        "to_email": "Recipient email address",
        "subject": "Email subject",
        "body": "Email body text"
    }

    def __init__(self):
        self.service = self.get_gmail_service()

    def get_gmail_service(self):
        creds = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as token:
                creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)

    def send_email(self, to_email: str, subject: str, body: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        try:
            msg = MIMEMultipart()
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(image_path))
                    msg.attach(img)
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            message = {'raw': raw_message}
            result = self.service.users().messages().send(userId='me', body=message).execute()
            return {"ok": True, "message_id": result.get('id'), "details": "Email sent successfully"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

# Example tool registry function

def get_gmail_tool():
    return GmailTool() 