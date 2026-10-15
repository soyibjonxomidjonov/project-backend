import asyncio
import random
import smtplib
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


async def send_verification_email(to_email: str, code: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to_email
    msg["Subject"] = f"{settings.APP_NAME} — Tasdiqlash kodi: {code}"

    body = f"""Assalomu alaykum!

Sizning tasdiqlash kodingiz: {code}

Bu kod 5 daqiqa ichida amal qiladi.
Agar siz bu kodni so'ramagan bo'lsangiz, ushbu xabarni e'tiborsiz qoldiring.

— {settings.APP_NAME}"""

    msg.attach(MIMEText(body, "plain", "utf-8"))

    def _send():
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)

    await asyncio.to_thread(_send)
