import os
import aiosqlite
import json
import anyio
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ValidationError, BaseModel
from fastapi.encoders import jsonable_encoder
from datetime import datetime
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from models import SubmissionCreate, SubmissionDB

class ChatRequest(BaseModel):
    message: str

# Load environment variables
load_dotenv()

app = FastAPI(title="Bhaskar Gowda Portfolio Backend")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the portfolio domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLite Setup
SQLITE_DB = "submissions.db"

async def init_sqlite():
    async with aiosqlite.connect(SQLITE_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                created_at TIMESTAMP
            )
        """)
        await db.commit()

@app.on_event("startup")
async def startup_event():
    await init_sqlite()

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "portfolio_db"
mock_db = [] # Memory fallback

async def send_email_notification(submission: SubmissionCreate):
    """
    Sends an email notification to the site owner about a new contact form submission.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    notify_email = os.getenv("NOTIFY_EMAIL")

    if not all([smtp_host, smtp_user, smtp_pass, notify_email]):
        print("WARNING: SMTP configuration incomplete. Skipping email notification.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = notify_email
        msg['Subject'] = "New Message From Portfolio Website"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = f"""
New Contact Form Submission:

Name: {submission.name}
Email: {submission.email}
Phone: {submission.phone or 'N/A'}
Message:
{submission.message}

---
Submitted at: {timestamp}
"""
        msg.attach(MIMEText(body, 'plain'))

        def send_sync():
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return True

        print(f"DEBUG: Attempting to send email to {notify_email}...")
        await anyio.to_thread.run_sync(send_sync)
            
        print(f"SUCCESS: Email notification sent to {notify_email}")
        return True
    except Exception as e:
        print(f"ERROR: FAILED to send email notification: {e}")
        return False

@app.post("/api/contact", status_code=201)
@limiter.limit("5/minute")
async def create_submission(request: Request, submission: SubmissionCreate, background_tasks: BackgroundTasks):
    try:
        # Prepare data with timestamp
        print(f"DEBUG: Received submission: {submission}")
        submission_data = submission.model_dump()
        submission_data["created_at"] = datetime.utcnow()
        
        try:
            # Attempt MongoDB insertion
            client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            db = client[DB_NAME]
            collection = db["submissions"]
            result = await collection.insert_one(submission_data)
            submission_id = str(result.inserted_id)
        except Exception as db_error:
            print(f"MongoDB not available, using SQLite storage: {db_error}")
            async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
                await sqlite_db.execute(
                    "INSERT INTO submissions (data, created_at) VALUES (?, ?)",
                    (json.dumps(submission_data, default=str), submission_data["created_at"].isoformat())
                )
                await sqlite_db.commit()
                cursor = await sqlite_db.execute("SELECT last_insert_rowid()")
                submission_id = f"sqlite_{ (await cursor.fetchone())[0] }"
        
        # Email Notification (Background)
        background_tasks.add_task(send_email_notification, submission)
        
        return {
            "status": "success", 
            "message": "Submission received! We will notify the owner.", 
            "id": submission_id
        }
        
    except Exception as e:
        print(f"Error in create_submission: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/api/submissions")
async def get_submissions():
    try:
        # Attempt to get from MongoDB
        try:
            client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            db = client[DB_NAME]
            collection = db["submissions"]
            cursor = collection.find().sort("created_at", -1)
            submissions = await cursor.to_list(length=100)
            
            if submissions is None:
                submissions = []
                
            # Sterilize ObjectIDs for JSON response
            for s in submissions:
                if "_id" in s:
                    s["_id"] = str(s["_id"])
        except Exception as db_err:
            print(f"Database error in get_submissions: {db_err}")
            submissions = []
        
        # Get from SQLite
        sqlite_submissions = []
        try:
            async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
                async with sqlite_db.execute("SELECT data FROM submissions ORDER BY created_at DESC") as cursor:
                    async for row in cursor:
                        sqlite_submissions.append(json.loads(row[0]))
        except Exception as sqlite_err:
            print(f"SQLite error in get_submissions: {sqlite_err}")

        all_submissions = submissions + sqlite_submissions
        return JSONResponse(content=jsonable_encoder(all_submissions))
        
    except Exception as e:
        print(f"Critical error in get_submissions: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Gemini Chat Setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

BHASKAR_SYSTEM_PROMPT = """
You are "Bhaskar's AI Assistant", a friendly, professional, and concise representative for Bhaskar Gowda A N.
Your goal is to answer questions about Bhaskar using the following information:

NAME: Bhaskar Gowda A N
ROLE: AIML Student & Full Stack Developer using AI
EDUCATION:
- B.E. in Computer Science (AIML), The National Institute of Engineering, Mysuru (2024-2028 expected)
- Pre-University, BGS PU College, Mysuru (2022-2024)
- SSLC, Podar International School, Hassan (2019-2022)

TECHNICAL SKILLS:
- Programming: Python (Expert), C/C++ (Advanced), Java, SQL
- ML & AI: TensorFlow, PyTorch, Scikit-learn, Pandas, NLP (Transformers, LSTMs), Computer Vision
- DevOps/Tools: Docker, Git, FastAPI, Flask, AWS/GCP, CI/CD, Postman, VS Code

PROJECTS:
1. Sentiment-Pulse AI: A high-throughput sentiment analysis engine for stock news using LSTM and Selenium. (92% accuracy)
2. VisionGate Attendance: Secure facial recognition system using One-Shot learning with FaceNet.

EXPERIENCE:
- AIML Intern at TechCorp Solutions (June 2023 - Aug 2023): Optimized data preprocessing and built customer churn prediction models.

STRENGTHS: Quick Learner, Adaptable, Analytical Problem Solver, Effective Team Player, Detail Oriented.

CONTACT:
- Email: bhaskarnandakishore@gmail.com
- Phone: +91 7975685397
- LinkedIn: linkedin.com/in/bhaskar-gowda-409a96332/
- GitHub: github.com/Bhaskiiii

GUIDELINES:
- Be helpful and professional.
- Keep responses concise (usually 1-3 sentences).
- If asked something not in the profile, politely state you don't have that information but can provide his contact details if they'd like to ask him directly.
- Use a friendly tone.
"""

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat_with_assistant(request: Request, chat_req: ChatRequest):
    if not GEMINI_API_KEY:
        return {"response": "I'm currently in 'offline' mode as my AI brain (API Key) isn't configured yet. Please contact Bhaskar at bhaskarnandakishore@gmail.com for questions!"}

    try:
        model_name = 'models/gemini-2.5-flash-lite'
        model = genai.GenerativeModel(model_name, system_instruction=BHASKAR_SYSTEM_PROMPT)
        response = await anyio.to_thread.run_sync(lambda: model.generate_content(chat_req.message))
        return {"response": response.text}
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            return {"response": f"Quota reached for {model_name}. Please try again later or contact Bhaskar directly."}
        if "404" in error_msg:
            return {"response": f"AI model {model_name} not found. I'm working on a fix!"}
        print(f"Chat Error: {e}")
        return {"response": f"Technical issue: {error_msg[:100]}..."}
