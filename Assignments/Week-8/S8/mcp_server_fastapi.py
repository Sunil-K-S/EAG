from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import asyncio
from modules.gmail_tool import GmailTool
from mcp_server_tools import GDriveTool  # Reuse the class from your tools server

app = FastAPI()

# In-memory event queue for SSE
sse_event_queue = asyncio.Queue()

def emit_event(event: str):
    sse_event_queue.put_nowait(event)

# --- Tool Endpoints ---
gmail_tool = GmailTool()
gdrive_tool = GDriveTool()

class EmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str

@app.post("/tool/send_email")
async def send_email(req: EmailRequest):
    result = gmail_tool.send_email(req.to_email, req.subject, req.body)
    if result.get("ok"):
        emit_event(f"Email sent to {req.to_email} with subject '{req.subject}'")
    else:
        emit_event(f"Failed to send email: {result.get('error')}")
    return JSONResponse(content=result)

class SpreadsheetRequest(BaseModel):
    title: str
    data: list = None

@app.post("/tool/create_spreadsheet")
async def create_spreadsheet(req: SpreadsheetRequest):
    result = gdrive_tool.create_spreadsheet(req.title)
    if not result.get("ok"):
        emit_event(f"Failed to create spreadsheet: {result.get('error')}")
        return JSONResponse(content=result)

    spreadsheet_id = result["spreadsheet_id"]
    try:
        # Get the actual sheet name
        sheet_metadata = gdrive_tool.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_name = sheet_metadata['sheets'][0]['properties']['title']
    except Exception as e:
        result["details"] += f" (Failed to get sheet name: {e})"
        print(f"[ERROR] Failed to get sheet name: {e}")
        emit_event(f"Failed to get sheet name: {e}")
        return JSONResponse(content=result)

    data = req.data
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
            emit_event(f"Spreadsheet '{req.title}' created and data written: {result.get('link')}")
        except Exception as e:
            result["details"] += f" (Failed to write data: {e})"
            print(f"[ERROR] Failed to write data: {e}")
            emit_event(f"Failed to write data: {e}")
    else:
        print("[WARN] No data provided to write to spreadsheet.")
        emit_event("No data provided to write to spreadsheet.")
    return JSONResponse(content=result)

# --- SSE Endpoint ---
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
                yield ": keep-alive\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# To run: uvicorn mcp_server_fastapi:app --reload 