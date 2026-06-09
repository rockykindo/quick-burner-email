import os
import random
import string
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel

app = FastAPI(title="Temp Email ID Backend Node")

# Enable Cross-Origin Resource Sharing (CORS) for local environment testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate a single high-speed asynchronous network client session
async_client = httpx.AsyncClient(timeout=10.0)
GUERRILLA_BASE = "https://api.guerrillamail.com/ajax.php"

def generate_random_sid_token(length=12):
    """Generates a random alphanumeric seed to forcefully bypass Guerrilla's IP lock."""
    letters_and_digits = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

@app.get("/")
async def serve_frontend():
    """Serves the main single-page dashboard app canvas directly."""
    frontend_path = Path("index.html")
    if not frontend_path.exists():
        raise HTTPException(status_code=404, detail="Frontend layout template missing.")
    return FileResponse(frontend_path)

class EmailRequest(BaseModel):
    provider: str
    domain: str
    force_new: bool = False  # Handles the Session Burner protocol tracking flag

@app.post("/api/get-email")
async def get_email_address(payload: EmailRequest):
    """
    Initializes a synchronized mailbox instance.
    If force_new is true, it passes a randomized token sequence to break IP affinity.
    """
    if payload.provider == "guerrilla":
        try:
            url = f"{GUERRILLA_BASE}?f=get_email_address&lang=en"
            
            # SESSION BURNER WORKAROUND: Force a unique session seed if requested
            if payload.force_new:
                random_token = generate_random_sid_token()
                url += f"&sid_token={random_token}"
            
            response = await async_client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Guerrilla node rejected handshake.")
            
            data = response.json()
            return {
                "email": data.get("email_addr"),
                "sid": data.get("sid")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    elif payload.provider == "mailtm":
        # Production Mockup: Generates predictable, secure IDs to satisfy UI requirements
        random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {
            "email": f"tm_user_{random_id}@{payload.domain}", 
            "sid": f"mock_session_mtm_{random_id}"
        }
        
    elif payload.provider == "mailinator":
        random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {
            "email": f"sandbox_{random_id}@{payload.domain}", 
            "sid": f"mock_session_mali_{random_id}"
        }
        
    else:
        raise HTTPException(status_code=400, detail="Engine configuration not supported.")

@app.get("/api/check-inbox")
async def check_inbox(email: str = Query(...), provider: str = Query(...), sid: str = Query(None)):
    """Fetches and normalizes live incoming data array streams from selected provider."""
    if provider == "guerrilla":
        try:
            url = f"{GUERRILLA_BASE}?f=check_email&seq=0"
            if sid:
                url += f"&sid={sid}"
                
            response = await async_client.get(url)
            if response.status_code != 200:
                return {"mails": []}
                
            data = response.json()
            raw_list = data.get("list", [])
            
            formatted_mails = []
            for m in raw_list:
                formatted_mails.append({
                    "id": m.get("mail_id"),
                    "from": m.get("mail_from"),
                    "subject": m.get("mail_subject"),
                    "time": m.get("mail_date")
                })
            return {"mails": formatted_mails}
        except Exception:
            return {"mails": []}
            
    # Clean fallbacks for mock modules during manual validation stages
    return {"mails": []}

@app.get("/api/get-mail-body")
async def get_mail_body(id: str = Query(...), provider: str = Query(...), sid: str = Query(None)):
    """Extracts raw content layout bodies safely for rendering within sandboxed view pane."""
    if provider == "guerrilla":
        try:
            url = f"{GUERRILLA_BASE}?f=fetch_email&email_id={id}"
            if sid:
                url += f"&sid={sid}"
                
            response = await async_client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Content extraction fault.")
                
            data = response.json()
            return {
                "id": data.get("mail_id"),
                "from": data.get("mail_from"),
                "subject": data.get("mail_subject"),
                "body": data.get("mail_body")
            }
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to parse remote payload structure.")

    return {"body": "<p>Content parsing omitted for alternative sandbox providers.</p>"}

@app.on_event("shutdown")
async def shutdown_event():
    """Closes networking connection cycles cleanly on application shutdown."""
    await async_client.aclose()
