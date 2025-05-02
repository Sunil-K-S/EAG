# mcp_server_tools.py

from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
import os
from modules.gmail_tool import GmailTool
from typing import Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
import json

# Google Drive/Sheets API config
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
GDRIVE_CLIENT_SECRETS_FILE = os.getenv('GDRIVE_CLIENT_SECRETS', 'client_secrets.json')
GDRIVE_TOKEN_FILE = os.getenv('GDRIVE_TOKEN_FILE', 'gdrive_token.json')

# Real GDrive tool
class GDriveTool:
    def __init__(self):
        self.service = self.get_sheets_service()

    def get_sheets_service(self):
        creds = None
        if os.path.exists(GDRIVE_TOKEN_FILE):
            with open(GDRIVE_TOKEN_FILE, 'r') as token:
                creds = Credentials.from_authorized_user_info(json.load(token), GDRIVE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(GDRIVE_CLIENT_SECRETS_FILE, GDRIVE_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(GDRIVE_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        return build('sheets', 'v4', credentials=creds)

    def create_spreadsheet(self, title: str) -> Dict[str, Any]:
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            result = self.service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
            spreadsheet_id = result.get('spreadsheetId')
            link = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}'
            return {"ok": True, "spreadsheet_id": spreadsheet_id, "link": link, "details": f"Spreadsheet '{title}' created."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

gmail_tool = GmailTool()
gdrive_tool = GDriveTool()

# Instantiate MCP server
mcp = FastMCP("WorkflowTools")

# Register Gmail tool
@mcp.tool()
def send_email(to_email: str, subject: str, body: str) -> dict:
    """
    Send an email using Gmail API.
    
    Parameters:
    - to_email (str): Recipient's email address.
    - subject (str): Email subject.
    - body (str): Email body. You can include links or summaries from previous tool outputs.

    Usage:
    send_email|to_email="user@example.com"|subject="Spreadsheet"|body="Here is the link: <spreadsheet_link>"
    """
    return gmail_tool.send_email(to_email, subject, body)

# Register GDrive tool
@mcp.tool()
def create_spreadsheet(title: str, data: list = None) -> dict:
    """
    Create a new spreadsheet in Google Drive and optionally populate it with data.

    Parameters:
    - title (str): The title of the spreadsheet.
    - data (list of dicts, optional): The rows to populate the spreadsheet. Each dict is a row, with keys as column headers.

    Usage:
    create_spreadsheet|title="Top 10 F1 Racers"|data=[{"racer": "Max Verstappen"}, {"racer": "Lewis Hamilton"}, ...]

    When using this tool after a search, extract only the relevant fields (e.g., names of racers) from the search results and format as a list of dicts.
    """
    result = gdrive_tool.create_spreadsheet(title)
    if not result.get("ok"):
        return result

    spreadsheet_id = result["spreadsheet_id"]
    try:
        # Get the actual sheet name
        sheet_metadata = gdrive_tool.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_name = sheet_metadata['sheets'][0]['properties']['title']
    except Exception as e:
        result["details"] += f" (Failed to get sheet name: {e})"
        print(f"[ERROR] Failed to get sheet name: {e}")
        return result

    if data:
        print("[DEBUG] Raw data received for spreadsheet:", data)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            headers = list(data[0].keys())
            values = [headers] + [[row.get(h, "") for h in headers] for row in data]
        else:
            values = data  # Assume already a list of lists
        print("[DEBUG] Writing values to spreadsheet:", values)
        try:
            response = gdrive_tool.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": values}
            ).execute()
            print("[DEBUG] Google Sheets API response:", response)
            result["details"] += " Data written to spreadsheet."
            print("[INFO] Data written to spreadsheet.")
        except Exception as e:
            result["details"] += f" (Failed to write data: {e})"
            print(f"[ERROR] Failed to write data: {e}")
    else:
        print("[WARN] No data provided to write to spreadsheet.")
    return result

# --- SSE Server using FastAPI ---
app = FastAPI()

# Simple in-memory event queue for demonstration
sse_event_queue = asyncio.Queue()

@app.get("/events")
async def sse_events(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(sse_event_queue.get(), timeout=15)
                yield f"data: {event}\n\n"
            except asyncio.TimeoutError:
                # Send a keep-alive comment
                yield ": keep-alive\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Example: function to emit an event (call this from your tool logic as needed)
def emit_event(event: str):
    sse_event_queue.put_nowait(event)

if __name__ == "__main__":
    # Run MCP server (stdio for agent integration)
    mcp.run(transport="stdio")
    # To run FastAPI SSE server, use: uvicorn mcp_server_tools:app --reload 