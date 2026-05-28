import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _send(subject: str, to: str, body_text: str, body_html: str, settings) -> None:
    if not settings.email_enabled:
        logger.info("EMAIL_ENABLED=false — skipping send to %s | %s", to, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.ehlo()
        server.starttls(context=context)
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())
    logger.info("Email sent to %s: %s", to, subject)


def send_verification_email(to_email: str, token: str, settings) -> None:
    url = f"{settings.app_base_url}/verify-email?token={token}"
    _send(
        subject="Verify your Cipher account",
        to=to_email,
        body_text=f"Verify your email address:\n\n{url}\n\nExpires in 24 hours.",
        body_html=f"""
<p>Welcome to Cipher. Click the link below to verify your email address.</p>
<p><a href="{url}">{url}</a></p>
<p>This link expires in 24 hours. If you didn't sign up, ignore this email.</p>
""",
        settings=settings,
    )


def send_reset_email(to_email: str, token: str, settings) -> None:
    url = f"{settings.app_base_url}/reset-password?token={token}"
    _send(
        subject="Reset your Cipher password",
        to=to_email,
        body_text=f"Reset your password:\n\n{url}\n\nExpires in 1 hour. If you didn't request this, ignore this email.",
        body_html=f"""
<p>Click the link below to reset your Cipher password.</p>
<p><a href="{url}">{url}</a></p>
<p>This link expires in 1 hour. If you didn't request a password reset, ignore this email.</p>
""",
        settings=settings,
    )
