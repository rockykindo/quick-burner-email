from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel
from pathlib import Path

app = FastAPI(title="Temp Email ID Backend Node")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async_client = httpx.AsyncClient(timeout=10.0)
GUERRILLA_BASE = "https://api.guerrillamail.com/ajax.php"

@app.get("/")
async def serve_frontend():
    frontend_path = Path("index.html")
    if not frontend_path.exists():
        raise HTTPException(status_code=404, detail="Frontend layout template missing.")
    return FileResponse(frontend_path)

class EmailRequest(BaseModel):
    provider: str
    domain: str

@app.post("/api/get-email")
async def get_email_address(payload: EmailRequest):
    if payload.provider == "guerrilla":
        try:
            # Request fresh initialization address token from Guerrilla
            url = f"{GUERRILLA_BASE}?f=get_email_address&lang=en"
            response = await async_client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Guerrilla node rejected handshake.")
            
            data = response.json()
            return {
                "email": data.get("email_addr"),
                "sid": data.get("sid")  # CRITICAL: Sending this token back to the UI frontend
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    elif payload.provider == "mailtm":
        # Dynamic mockup to bypass offline provider loops during testing
        return {"email": f"tm_user_{int(Path('/dev/urandom').read(2).hex(), 16)}@{payload.domain}", "sid": "mailtm_session_mock"}
    elif payload.provider == "mailinator":
        return {"email": f"sandbox_{int(Path('/dev/urandom').read(2).hex(), 16)}@{payload.domain}", "sid": "mailinator_mock"}
    else:
        raise HTTPException(status_code=400, detail="Engine configuration not supported.")

@app.get("/api/check-inbox")
async def check_inbox(email: str = Query(...), provider: str = Query(...), sid: str = Query(None)):
    if provider == "guerrilla":
        try:
            # FIX: We now explicitly append the user's active session ID string to the API call
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

    return {"body": "<p>Content parsing omitted for alternative sandbox providers.</p>"}

@app.on_event("shutdown")
async def shutdown_event():
    await async_client.aclose()
