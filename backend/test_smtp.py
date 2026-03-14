import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def test_email():
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    notify_email = os.getenv("NOTIFY_EMAIL")

    print(f"Testing with:")
    print(f"Host: {smtp_host}")
    print(f"Port: {smtp_port}")
    print(f"User: {smtp_user}")
    print(f"Pass: [REDACTED]")
    print(f"Notify: {notify_email}")

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = notify_email
        msg['Subject'] = "SMTP Test Message"
        
        body = "This is a test message to verify SMTP settings."
        msg.attach(MIMEText(body, 'plain'))

        print("Connecting to server...")
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.set_debuglevel(1)
            print("Starting TLS...")
            server.starttls()
            print("Logging in...")
            server.login(smtp_user, smtp_pass)
            print("Sending message...")
            server.send_message(msg)
            
        print("SUCCESS: Email sent!")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    test_email()
