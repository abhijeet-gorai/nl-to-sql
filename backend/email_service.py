"""
Email Service Module
Handles sending verification emails using Brevo API (with SMTP fallback)
"""

import smtplib
import os
import secrets
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import Optional

from database_config import get_connection, execute, fetchrow

# Email configuration from environment
GMAIL_EMAIL_ID = os.getenv("GMAIL_EMAIL_ID")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Brevo API configuration
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")

# Frontend URL for verification links
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Token expiry in hours
VERIFICATION_TOKEN_EXPIRY_HOURS = 24


async def init_verification_tokens_table():
    """Initialize the email verification tokens table"""
    async with get_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


def generate_verification_token() -> str:
    """Generate a secure random token for email verification"""
    return secrets.token_urlsafe(32)


async def create_verification_token(user_id: int) -> str:
    """
    Create a verification token for a user.
    Deletes any existing tokens for this user first.
    Returns the new token.
    """
    async with get_connection() as conn:
        # Delete any existing tokens for this user
        await conn.execute(
            "DELETE FROM email_verification_tokens WHERE user_id = $1",
            user_id
        )

        # Generate new token
        token = generate_verification_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TOKEN_EXPIRY_HOURS)

        await conn.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id, token, expires_at
        )

        return token


async def get_verification_token_data(token: str) -> Optional[dict]:
    """
    Get verification token data.
    Returns dict with user_id and expires_at, or None if not found.
    """
    row = await fetchrow(
        """
        SELECT user_id, expires_at, created_at
        FROM email_verification_tokens
        WHERE token = $1
        """,
        token
    )

    if row:
        return {
            "user_id": row["user_id"],
            "expires_at": row["expires_at"],
            "created_at": row["created_at"]
        }
    return None


async def delete_verification_token(token: str) -> bool:
    """Delete a verification token after successful verification"""
    result = await execute(
        "DELETE FROM email_verification_tokens WHERE token = $1",
        token
    )
    return "DELETE" in result


async def mark_email_verified(user_id: int) -> bool:
    """Mark a user's email as verified"""
    result = await execute(
        """
        UPDATE users 
        SET is_email_verified = TRUE, updated_at = NOW()
        WHERE id = $1
        """,
        user_id
    )
    return "UPDATE" in result


async def verify_email_token(token: str) -> dict:
    """
    Verify an email token.
    Returns dict with success status and message.
    """
    token_data = await get_verification_token_data(token)

    if not token_data:
        return {"success": False, "message": "Invalid verification token"}

    # Check if token has expired
    expires_at = token_data["expires_at"]
    # Handle both datetime objects and strings
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace(' ', 'T'))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if datetime.now(timezone.utc) > expires_at:
        # Clean up expired token
        await delete_verification_token(token)
        return {"success": False, "message": "Verification token has expired"}

    # Mark user as verified
    if await mark_email_verified(token_data["user_id"]):
        # Delete the used token
        await delete_verification_token(token)
        
        # Grant read access to sample project (project_id = 4)
        await _grant_sample_project_access(token_data["user_id"])
        
        return {"success": True, "message": "Email verified successfully"}

    return {"success": False, "message": "Failed to verify email"}


async def _grant_sample_project_access(user_id: int):
    """
    Grant read-only access to the Sample Project for new verified users.
    Sample Project ID is 4 - verify it exists and has the correct name before granting access.
    """
    SAMPLE_PROJECT_ID = 4
    SAMPLE_PROJECT_NAME = "Sample Project"
    
    try:
        # Verify the sample project exists with the correct name
        row = await fetchrow(
            "SELECT id, name, created_by FROM projects WHERE id = $1",
            SAMPLE_PROJECT_ID
        )
        
        if not row or row["name"] != SAMPLE_PROJECT_NAME:
            print(f"Sample project not found or name mismatch. Expected '{SAMPLE_PROJECT_NAME}' at ID {SAMPLE_PROJECT_ID}")
            return
        
        # Check if user is already a member
        existing = await fetchrow(
            "SELECT id FROM project_members WHERE project_id = $1 AND user_id = $2",
            SAMPLE_PROJECT_ID, user_id
        )
        
        if existing:
            # User already has access
            return
        
        # Add user as viewer
        await execute(
            """
            INSERT INTO project_members (project_id, user_id, role, added_by)
            VALUES ($1, $2, 'read', $3)
            """,
            SAMPLE_PROJECT_ID, user_id, row["created_by"]
        )
        print(f"Granted read access to Sample Project for user {user_id}")
        
    except Exception as e:
        # Don't fail verification if sample project access fails
        print(f"Failed to grant sample project access: {e}")


def _get_email_content(username: str, verification_link: str) -> tuple[str, str]:
    """Generate plain text and HTML email content"""
    text_content = f"""
Hello {username},

Welcome to DataTalk! Please verify your email address to complete your registration.

Click the link below to verify your email:
{verification_link}

This link will expire in {VERIFICATION_TOKEN_EXPIRY_HOURS} hours.

If you did not create an account, please ignore this email.

Best regards,
The DataTalk Team
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid #6366f1;
        }}
        .logo {{
            font-size: 28px;
            font-weight: bold;
            color: #6366f1;
        }}
        .content {{
            padding: 30px 0;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white !important;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .button:hover {{
            opacity: 0.9;
        }}
        .footer {{
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }}
        .link {{
            word-break: break-all;
            color: #6366f1;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🗄️ DataTalk</div>
    </div>
    <div class="content">
        <h2>Verify your email address</h2>
        <p>Hello <strong>{username}</strong>,</p>
        <p>Welcome to DataTalk! Please verify your email address to complete your registration and start exploring your data.</p>
        <p style="text-align: center;">
            <a href="{verification_link}" class="button">Verify Email Address</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p class="link">{verification_link}</p>
        <p><em>This link will expire in {VERIFICATION_TOKEN_EXPIRY_HOURS} hours.</em></p>
    </div>
    <div class="footer">
        <p>If you did not create an account, please ignore this email.</p>
        <p>© DataTalk - Natural Language to SQL</p>
    </div>
</body>
</html>
"""
    return text_content, html_content


def send_verification_email(email: str, username: str, token: str) -> bool:
    """
    Send a verification email using Brevo API.
    Falls back to SMTP if Brevo is not configured.
    Returns True if email was sent successfully, False otherwise.
    """
    verification_link = f"{FRONTEND_URL}/verify-email?token={token}"
    text_content, html_content = _get_email_content(username, verification_link)
    
    # Try Brevo API first
    if BREVO_API_KEY and BREVO_SENDER_EMAIL:
        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "accept": "application/json"
                },
                json={
                    "sender": {
                        "name": "DataTalk",
                        "email": BREVO_SENDER_EMAIL
                    },
                    "to": [{"email": email, "name": username}],
                    "subject": "Verify your DataTalk account",
                    "textContent": text_content,
                    "htmlContent": html_content
                },
                timeout=30
            )
            
            if response.status_code in [200, 201, 202]:
                print(f"Verification email sent to {email} via Brevo")
                return True
            else:
                print(f"Brevo API error: {response.status_code} - {response.text}")
                # Fall through to SMTP fallback
                
        except Exception as e:
            print(f"Brevo API failed: {e}")
            # Fall through to SMTP fallback
    
    # Fallback to SMTP
    print("Falling back to SMTP")
    return send_verification_email_smtp(email, username, token)


def send_verification_email_smtp(email: str, username: str, token: str) -> bool:
    """
    Send a verification email using Gmail SMTP (fallback).
    Returns True if email was sent successfully, False otherwise.
    """
    if not GMAIL_EMAIL_ID or not GMAIL_APP_PASSWORD:
        print("Warning: Neither Brevo nor Gmail credentials configured. Email not sent.")
        return False

    verification_link = f"{FRONTEND_URL}/verify-email?token={token}"
    text_content, html_content = _get_email_content(username, verification_link)

    # Create the email
    message = MIMEMultipart("alternative")
    message["Subject"] = "Verify your DataTalk account"
    message["From"] = GMAIL_EMAIL_ID
    message["To"] = email

    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_EMAIL_ID, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_EMAIL_ID, email, message.as_string())
        print(f"Verification email sent to {email} via SMTP")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP Authentication Error: {e}")
        print("Make sure you're using an App Password, not your regular Gmail password.")
        return False
    except Exception as e:
        print(f"Failed to send verification email via SMTP: {e}")
        return False


async def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email (for resend verification)"""
    row = await fetchrow("SELECT * FROM users WHERE email = $1", email)
    return dict(row) if row else None


async def resend_verification_email(email: str) -> dict:
    """
    Resend verification email to a user.
    Returns dict with success status and message.
    """
    user = await get_user_by_email(email)

    if not user:
        # Don't reveal if email exists or not for security
        return {"success": True, "message": "If an account exists with this email, a verification link has been sent."}

    if user.get("is_email_verified"):
        return {"success": False, "message": "Email is already verified. Please login."}

    # Create new token and send email
    token = await create_verification_token(user["id"])
    if send_verification_email(email, user["username"], token):
        return {"success": True, "message": "Verification email sent. Please check your inbox."}
    else:
        return {"success": False, "message": "Failed to send verification email. Please try again later."}
