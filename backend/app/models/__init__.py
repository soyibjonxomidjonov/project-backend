from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.user import User
from app.models.entity import Entity
from app.models.document import Document, DocumentChunk
from app.models.chat import ChatSession, ChatMessage
from app.models.verification import VerificationCode

__all__ = [
    "Base", "User", "Entity", "Document", "DocumentChunk",
    "ChatSession", "ChatMessage", "VerificationCode",
]
