import os
import traceback
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from dotenv import load_dotenv
import google.generativeai as genai
from jose import JWTError, jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

# --- Security Configuration ---
SECRET_KEY = os.getenv("JWT_SECRET", "supersecretkey123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")

# --- Models ---

class ContactForm(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    message: str = Field(..., min_length=1, max_length=1000)

class ChatRequest(BaseModel):
    message: str

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Database Setup ---

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_instance = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_instance.client = AsyncIOMotorClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
    db_instance.db = db_instance.client[os.getenv("DB_NAME", "portfolio_db")]
    yield
    db_instance.client.close()

app = FastAPI(title="Bhaskar Portfolio Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth Helpers ---

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username != ADMIN_USERNAME:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

# --- AI & Email Helpers ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

BHASKAR_SYSTEM_PROMPT = """
You are "Bhaskar's AI Assistant", representing Bhaskar Gowda A N (AIML Student & Full Stack Developer).
Keep responses concise, professional, and friendly.
Skills: Python, C++, ML/AI (TensorFlow, PyTorch), Web (FastAPI, React).
Projects: Sentiment-Pulse AI, VisionGate Attendance.
Contact: bhaskarnandakishore@gmail.com | +91 7975685397
"""

async def send_email_notification(form: ContactForm):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    notify_email = os.getenv("NOTIFY_EMAIL")

    if not all([smtp_host, smtp_user, smtp_pass, notify_email]):
        print("SMTP config missing")
        return

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = notify_email
    msg['Subject'] = f"New Message from {form.name}"
    
    body = f"Name: {form.name}\nEmail: {form.email}\nPhone: {form.phone}\n\nMessage:\n{form.message}"
    msg.attach(MIMEText(body, 'plain'))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        print("Email sent successfully")
    except Exception as e:
        print(f"Email failed: {e}")

# --- Routes ---

@app.post("/api/admin/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or form_data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": ADMIN_USERNAME})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/contact")
async def contact_form(form: ContactForm, background_tasks: BackgroundTasks):
    data = form.model_dump()
    data["created_at"] = datetime.utcnow()
    await db_instance.db.contacts.insert_one(data)
    background_tasks.add_task(send_email_notification, form)
    return {"status": "success"}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not GEMINI_API_KEY: 
        return {"response": "I'm currently in 'offline' mode. Please contact Bhaskar directly!"}
    
    try:
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash-latest',
            system_instruction=BHASKAR_SYSTEM_PROMPT
        )
        response = model.generate_content(req.message)
        bot_reply = response.text
        
        await db_instance.db.chat_history.insert_one({
            "user_message": req.message, 
            "bot_reply": bot_reply, 
            "timestamp": datetime.utcnow()
        })
        return {"response": bot_reply}
    except Exception as e:
        print(f"Chat error: {e}")
        return {"response": "Technical issue with AI. Please try again later."}

# --- Protected Admin Routes ---

@app.get("/api/admin/messages")
async def get_messages(current_user: str = Depends(get_current_admin)):
    cursor = db_instance.db.contacts.find().sort("created_at", -1)
    messages = await cursor.to_list(length=100)
    for m in messages: m["_id"] = str(m["_id"])
    return messages

@app.get("/api/admin/chats")
async def get_chats(current_user: str = Depends(get_current_admin)):
    cursor = db_instance.db.chat_history.find().sort("timestamp", -1)
    chats = await cursor.to_list(length=100)
    for c in chats: c["_id"] = str(c["_id"])
    return chats

@app.get("/health")
async def health(): return {"status": "ok"}
