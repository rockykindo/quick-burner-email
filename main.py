from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel
from pathlib import Path
import random
import string

app = FastAPI(title="Temp Email ID Backend Node")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async_client = httpx.AsyncClient(timeout=12.0)
GUERRILLA_BASE = "https://api.guerrillamail.com/ajax.php"
SECMAIL_BASE = "https://www.1secmail.com/api/v1/"

def generate_random_sid_token(length=12):
    """Generates an alphanumeric seed to forcefully bypass Guerrilla's IP cache lock."""
    letters_and_digits = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

@app.get("/")
async def serve_frontend():
    frontend_path = Path("index.html")
    if not frontend_path.exists():
        raise HTTPException(status_code=404, detail="Frontend layout template missing.")
    return FileResponse(frontend_path)

class EmailRequest(BaseModel):
    provider: str
    domain: str
    force_new: bool = False  # Track structural session burning requirements upstream

@app.post("/api/get-email")
async def get_email_address(payload: EmailRequest):
    if payload.provider == "guerrilla":
        try:
            url = f"{GUERRILLA_BASE}?f=get_email_address&lang=en&domain={payload.domain}"
            
            # If the user hits 'New', generate an alternative unique token seed 
            # to break out of the server's tracking state
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
            
    elif payload.provider in ["mailtm", "mailinator"]:
        try:
            random_user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            full_email = f"{random_user}@{payload.domain}"
            return {
                "email": full_email,
                "sid": f"sec_{random_user}"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Engine configuration not supported.")

@app.get("/api/check-inbox")
async def check_inbox(email: str = Query(...), provider: str = Query(...), sid: str = Query(None)):
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
                # Omit welcome message clutter cleanly from dashboard streams
                if m.get("mail_from") == "no-reply@guerrillamail.com":
                    continue
                formatted_mails.append({
                    "id": m.get("mail_id"),
                    "from": m.get("mail_from"),
                    "subject": m.get("mail_subject"),
                    "time": m.get("mail_date")
                })
            return {"mails": formatted_mails}
        except Exception:
            return {"mails": []}
            
    elif provider in ["mailtm", "mailinator"]:
        if not sid or not sid.startswith("sec_"):
            return {"mails": []}
        try:
            username = sid.replace("sec_", "")
            domain = email.split("@")[1]
            
            url = f"{SECMAIL_BASE}?action=getMessages&login={username}&domain={domain}"
            response = await async_client.get(url)
            if response.status_code != 200:
                return {"mails": []}
                
            raw_list = response.json()
            formatted_mails = []
            for m in raw_list:
                formatted_mails.append({
                    "id": str(m.get("id")),
                    "from": m.get("from", "Unknown Sender"),
                    "subject": m.get("subject", "No Subject"),
                    "time": m.get("date", "")[11:19]
                })
            return {"mails": formatted_mails}
        except Exception:
            return {"mails": []}

    return {"mails": []}

@app.get("/api/get-mail-body")
async def get_mail_body(id: str = Query(...), provider: str = Query(...), sid: str = Query(None)):
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

    elif provider in ["mailtm", "mailinator"]:
        if not sid or not sid.startswith("sec_"):
            raise HTTPException(status_code=401, detail="Authentication signature missing.")
        try:
            username = sid.replace("sec_", "")
            for domain_ext in ["1secmail.com", "1secmail.org", "1secmail.net"]:
                url = f"{SECMAIL_BASE}?action=readMessage&login={username}&domain={domain_ext}&id={id}"
                response = await async_client.get(url)
                if response.status_code == 200 and "id" in response.text:
                    data = response.json()
                    return {
                        "id": str(data.get("id")),
                        "from": data.get("from"),
                        "subject": data.get("subject"),
                        "body": data.get("htmlBody") or f"<pre style='color: #d1d5db;'>{data.get('textBody')}</pre>"
                    }
            raise HTTPException(status_code=404, detail="Message element missing.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {"body": "<p>Content parsing omitted.</p>"}

@app.on_event("shutdown")
async def shutdown_event():
    await async_client.aclose()