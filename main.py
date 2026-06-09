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

# Instantiate a single high-speed asynchronous network client session with a relaxed timeout
async_client = httpx.AsyncClient(timeout=15.0)
GUERRILLA_BASE = "https://api.guerrillamail.com/ajax.php"
MAILTM_BASE = "https://api.mail.tm"

def generate_random_sid_token(length=12):
    """Generates a random alphanumeric seed to forcefully bypass Guerrilla's IP lock."""
    letters_and_digits = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

def generate_secure_password(length=14):
    """Generates a random password conforming to Mail.tm validation rules."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

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
    Initializes a synchronized mailbox instance across alternative live providers.
    """
    if payload.provider == "guerrilla":
        try:
            url = f"{GUERRILLA_BASE}?f=get_email_address&lang=en"
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
        try:
            # Generate account parameters on the fly
            random_user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            full_email = f"{random_user}@{payload.domain}"
            secure_pass = generate_secure_password()
            
            # Request explicit account creation on Mail.tm remote gateway cluster
            account_res = await async_client.post(
                f"{MAILTM_BASE}/accounts",
                json={"address": full_email, "password": secure_pass},
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            if account_res.status_code not in [200, 201]:
                raise HTTPException(status_code=502, detail="Mail.tm gateway rejected registration parameters.")
            
            # Immediately request an active operational JWT Bearer context token
            token_res = await async_client.post(
                f"{MAILTM_BASE}/token",
                json={"address": full_email, "password": secure_pass},
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            if token_res.status_code != 200:
                raise HTTPException(status_code=502, detail="Mail.tm authentication subsystem handshake failed.")
                
            token_data = token_res.json()
            jwt_token = token_data.get("token")
            
            return {
                "email": full_email,
                "sid": f"jwt_{jwt_token}"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Mail.tm Node Exception: {str(e)}")
        
    elif payload.provider == "mailinator":
        try:
            # Standardizes down to direct open sandbox allocation under primary public domain routing
            random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            target_domain = "mailinator.com"  # Bypass non-routable secondary domain hooks permanently
            full_email = f"{random_id}@{target_domain}"
            return {
                "email": full_email,
                "sid": f"mali_{random_id}"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
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
            
    elif provider == "mailtm":
        if not sid or not sid.startswith("jwt_"):
            return {"mails": []}
        try:
            jwt = sid.replace("jwt_", "")
            headers = {
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/json"
            }
            response = await async_client.get(f"{MAILTM_BASE}/messages", headers=headers)
            
            if response.status_code != 200:
                return {"mails": []}
                
            raw_data = response.json()
            raw_list = raw_data.get("hydra:member", [])
            
            formatted_mails = []
            for m in raw_list:
                formatted_mails.append({
                    "id": m.get("id"),
                    "from": m.get("from", {}).get("address", "System Sender"),
                    "subject": m.get("subject", "No Subject Spec"),
                    "time": m.get("createdAt", "")[11:19]  # Clean Timestamp parsing layout slice
                })
            return {"mails": formatted_mails}
        except Exception:
            return {"mails": []}

    elif provider == "mailinator":
        # Mailinator Public fallback feed layout normalization route context
        return {"mails": []}

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

    elif provider == "mailtm":
        if not sid or not sid.startswith("jwt_"):
            raise HTTPException(status_code=401, detail="Authentication signature missing.")
        try:
            jwt = sid.replace("jwt_", "")
            headers = {
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/json"
            }
            response = await async_client.get(f"{MAILTM_BASE}/messages/{id}", headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Unable to retrieve Mail.tm message stream.")
                
            data = response.json()
            return {
                "id": data.get("id"),
                "from": data.get("from", {}).get("address"),
                "subject": data.get("subject"),
                "body": data.get("html") or f"<pre style='color: #d1d5db;'>{data.get('text')}</pre>"
            }
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to pull engine message layers.")

    return {"body": "<p>Content parsing omitted or restricted for selected sandbox providers.</p>"}

@app.on_event("shutdown")
async def shutdown_event():
    """Closes networking connection cycles cleanly on application shutdown."""
    await async_client.aclose()
