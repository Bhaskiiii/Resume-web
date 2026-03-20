import os
import traceback
import json
import aiosqlite
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
from google import genai
from google.genai import types
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "submissions.db")

class Database:
    client: AsyncIOMotorClient = None
    db = None
    contacts_collection = None
    chats_collection = None

db_instance = Database()

async def init_sqlite():
    async with aiosqlite.connect(SQLITE_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                data TEXT,
                created_at TIMESTAMP
            )
        """)
        await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_sqlite()
    # Check for MONGO_URL or MONGODB_URI (Render default)
    MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI")
    
    if MONGO_URL:
        try:
            db_instance.client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            # Use database from connection string
            # If default db name is not in URL, this might fail, so we fallback to a default
            try:
                db_instance.db = db_instance.client.get_default_database()
            except Exception:
                db_instance.db = db_instance.client[os.getenv("DB_NAME", "portfolio_db")]
            
            db_instance.contacts_collection = db_instance.db["contacts"]
            db_instance.chats_collection = db_instance.db["chat_history"]
            print("✅ Connected to MongoDB Atlas")
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB Atlas: {e}")
            print("⚠️ Falling back to SQLite")
    else:
        print("⚠️ MONGO_URL/MONGODB_URI not found, fallback to SQLite")
    
    yield
    # Shutdown
    if db_instance.client:
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
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini Client Initialized")
    except Exception as e:
        print(f"❌ Gemini Client Initialization Failed: {e}")

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
    try:
        data = form.model_dump()
        data["created_at"] = datetime.utcnow()
        
        # Try MongoDB
        saved_to_mongo = False
        if db_instance.contacts_collection is not None:
            try:
                await db_instance.contacts_collection.insert_one(data)
                saved_to_mongo = True
                print("✅ Saved contact to MongoDB")
            except Exception as e:
                print(f"MongoDB save failed: {e}")

        # Always Save to SQLite as backup/fallback
        async with aiosqlite.connect(SQLITE_DB) as db:
            await db.execute(
                "INSERT INTO submissions (type, data, created_at) VALUES (?, ?, ?)",
                ("contact", json.dumps(data, default=str), data["created_at"].isoformat())
            )
            await db.commit()
            if not saved_to_mongo:
                print("Saved contact to SQLite fallback")
        
        background_tasks.add_task(send_email_notification, form)
        return {"status": "success", "mongo": saved_to_mongo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"status": "backend running"}

@app.post("/api/chat")
async def chat(request: Request):
    if not client:
        return JSONResponse({"reply": "AI is offline. Please contact Bhaskar directly.", "response": "AI is offline. Please contact Bhaskar directly."})
    
    try:
        data = await request.json()
        user_message = data.get("message", "")
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=BHASKAR_SYSTEM_PROMPT,
            )
        )
        reply = response.text
        
        chat_data = {"user_message": user_message, "bot_reply": reply, "timestamp": datetime.utcnow()}
        
        # Try MongoDB
        if db_instance.chats_collection is not None:
            try:
                await db_instance.chats_collection.insert_one(chat_data)
                print("✅ Saved chat to MongoDB")
            except Exception as e:
                print(f"MongoDB chat save failed: {e}")

        # SQLite fallback
        async with aiosqlite.connect(SQLITE_DB) as db:
            await db.execute(
                "INSERT INTO submissions (type, data, created_at) VALUES (?, ?, ?)",
                ("chat", json.dumps(chat_data, default=str), chat_data["timestamp"].isoformat())
            )
            await db.commit()
            
        return JSONResponse({"reply": reply, "response": reply})
    except Exception as e:
        print("Chat error:", str(e))
        return JSONResponse({"reply": "Server is waking up. Please try again.", "response": "Server is waking up. Please try again."})

# --- Protected Admin Routes ---

@app.get("/api/admin/messages")
async def get_messages(current_user: str = Depends(get_current_admin)):
    results = []
    # Try MongoDB
    if db_instance.contacts_collection is not None:
        try:
            cursor = db_instance.contacts_collection.find().sort("created_at", -1)
            results = await cursor.to_list(length=100)
            for m in results: m["_id"] = str(m["_id"])
            return results
        except Exception: 
            pass
            
    # Fallback to SQLite
    async with aiosqlite.connect(SQLITE_DB) as db:
        async with db.execute("SELECT data FROM submissions WHERE type='contact' ORDER BY created_at DESC") as cursor:
            async for row in cursor:
                results.append(json.loads(row[0]))
    return results

@app.get("/api/admin/chats")
async def get_chats(current_user: str = Depends(get_current_admin)):
    results = []
    # Try MongoDB
    if db_instance.chats_collection is not None:
        try:
            cursor = db_instance.chats_collection.find().sort("timestamp", -1)
            results = await cursor.to_list(length=100)
            for c in results: c["_id"] = str(c["_id"])
            return results
        except Exception:
            pass

    # Fallback to SQLite
    async with aiosqlite.connect(SQLITE_DB) as db:
        async with db.execute("SELECT data FROM submissions WHERE type='chat' ORDER BY created_at DESC") as cursor:
            async for row in cursor:
                results.append(json.loads(row[0]))
    return results

@app.get("/health")
async def health(): 
    db_status = "connected" if db_instance.db else "sqlite-only"
    return {"status": "ok", "db": db_status}
