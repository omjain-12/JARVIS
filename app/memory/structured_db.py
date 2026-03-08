"""
Structured Database — SQLAlchemy-based relational storage for JARVIS.

Manages all structured entities: users, documents, tasks, reminders,
habits, contacts, calendar events, preferences, goals, and conversations.

Uses async SQLAlchemy with aiosqlite (local) or asyncpg (production PostgreSQL).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("structured_db")


# ── ORM Base ──


class Base(DeclarativeBase):
    pass


# ── ORM Models ──


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    habits = relationship("Habit", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50))  # pdf, docx, txt, md
    blob_url = Column(Text)
    status = Column(String(50), default="uploaded")  # uploaded | parsing | chunking | embedding | indexed | failed
    chunk_count = Column(Integer, default=0)
    metadata_ = Column("metadata", JSON, default=dict)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="documents")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    priority = Column(Integer, default=0)  # 0=low, 1=medium, 2=high
    status = Column(String(50), default="pending")  # pending | in_progress | completed | cancelled
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="tasks")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, default="")
    remind_at = Column(DateTime, nullable=False)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="reminders")


class Habit(Base):
    __tablename__ = "habits"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    frequency = Column(String(50), default="daily")  # daily | weekly | monthly
    streak = Column(Integer, default=0)
    total_completions = Column(Integer, default=0)
    last_completed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    habit_id = Column(String, ForeignKey("habits.id"), nullable=False)
    completed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, default="")

    habit = relationship("Habit", back_populates="logs")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    relationship_ = Column("relationship", String(100), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="contacts")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_rule = Column(String(255), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="calendar_events")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    target_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="active")  # active | completed | abandoned
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="goals")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    summary = Column(Text, default="")
    messages = Column(JSON, default=list)

    user = relationship("User", back_populates="sessions")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    session_id = Column(String, nullable=True)
    role = Column(String(50), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_ = Column("metadata", JSON, default=dict)


# ── Database Engine & Session Factory ──


class StructuredDB:
    """
    Async database manager for structured storage.
    Provides methods for CRUD operations on all entities.
    """

    def __init__(self, database_url: str = ""):
        self.database_url = database_url or settings.database.database_url
        self.engine = create_async_engine(self.database_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def initialize(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Structured database initialized", event_type="db_init")

    async def close(self):
        """Close the engine."""
        await self.engine.dispose()

    # ── User Operations ──

    async def create_user(self, name: str, email: str, password_hash: str) -> Dict[str, Any]:
        async with self.async_session() as session:
            user = User(name=name, email=email, password_hash=password_hash)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return {"id": user.id, "name": user.name, "email": user.email}

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                return {
                    "id": user.id, "name": user.name, "email": user.email,
                    "password_hash": user.password_hash, "preferences": user.preferences,
                }
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                return {
                    "id": user.id, "name": user.name, "email": user.email,
                    "preferences": user.preferences,
                }
            return None

    # ── Document Operations ──

    async def create_document(self, user_id: str, filename: str, file_type: str, blob_url: str = "") -> Dict[str, Any]:
        async with self.async_session() as session:
            doc = Document(user_id=user_id, filename=filename, file_type=file_type, blob_url=blob_url)
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            return {"id": doc.id, "filename": doc.filename, "status": doc.status}

    async def update_document_status(self, document_id: str, status: str, chunk_count: int = 0):
        from sqlalchemy import update
        async with self.async_session() as session:
            stmt = update(Document).where(Document.id == document_id).values(
                status=status,
                chunk_count=chunk_count,
                processed_at=datetime.now(timezone.utc) if status == "indexed" else None,
            )
            await session.execute(stmt)
            await session.commit()

    async def get_documents(self, user_id: str) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(
                select(Document).where(Document.user_id == user_id).order_by(Document.uploaded_at.desc())
            )
            docs = result.scalars().all()
            return [
                {
                    "id": d.id, "filename": d.filename, "file_type": d.file_type,
                    "status": d.status, "chunk_count": d.chunk_count,
                    "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else "",
                }
                for d in docs
            ]

    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(select(Document).where(Document.id == document_id))
            d = result.scalar_one_or_none()
            if d:
                return {
                    "id": d.id, "user_id": d.user_id, "filename": d.filename,
                    "file_type": d.file_type, "blob_url": d.blob_url, "status": d.status,
                    "chunk_count": d.chunk_count,
                    "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else "",
                }
            return None

    # ── Task Operations ──

    async def create_task(self, user_id: str, title: str, description: str = "",
                          priority: int = 0, due_date: Optional[datetime] = None) -> Dict[str, Any]:
        async with self.async_session() as session:
            task = Task(user_id=user_id, title=title, description=description,
                        priority=priority, due_date=due_date)
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return {"id": task.id, "title": task.title, "status": task.status}

    async def get_tasks(self, user_id: str, status: str = "") -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            query = select(Task).where(Task.user_id == user_id)
            if status:
                query = query.where(Task.status == status)
            result = await session.execute(query.order_by(Task.priority.desc(), Task.created_at.desc()))
            tasks = result.scalars().all()
            return [
                {
                    "id": t.id, "title": t.title, "description": t.description,
                    "priority": t.priority, "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else "",
                }
                for t in tasks
            ]

    async def update_task_status(self, task_id: str, status: str):
        from sqlalchemy import update
        async with self.async_session() as session:
            values = {"status": status}
            if status == "completed":
                values["completed_at"] = datetime.now(timezone.utc)
            await session.execute(update(Task).where(Task.id == task_id).values(**values))
            await session.commit()

    # ── Reminder Operations ──

    async def create_reminder(self, user_id: str, title: str, message: str,
                              remind_at: datetime) -> Dict[str, Any]:
        async with self.async_session() as session:
            reminder = Reminder(user_id=user_id, title=title, message=message, remind_at=remind_at)
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            return {"id": reminder.id, "title": reminder.title, "remind_at": reminder.remind_at.isoformat()}

    async def get_reminders(self, user_id: str, include_sent: bool = False) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            query = select(Reminder).where(Reminder.user_id == user_id)
            if not include_sent:
                query = query.where(Reminder.is_sent.is_(False))
            result = await session.execute(query.order_by(Reminder.remind_at))
            reminders = result.scalars().all()
            return [
                {
                    "id": r.id, "title": r.title, "message": r.message,
                    "remind_at": r.remind_at.isoformat(), "is_sent": r.is_sent,
                }
                for r in reminders
            ]

    # ── Habit Operations ──

    async def create_habit(self, user_id: str, name: str, description: str = "",
                           frequency: str = "daily") -> Dict[str, Any]:
        async with self.async_session() as session:
            habit = Habit(user_id=user_id, name=name, description=description, frequency=frequency)
            session.add(habit)
            await session.commit()
            await session.refresh(habit)
            return {"id": habit.id, "name": habit.name, "frequency": habit.frequency}

    async def log_habit(self, habit_id: str, notes: str = "") -> Dict[str, Any]:
        from sqlalchemy import update, select
        async with self.async_session() as session:
            log = HabitLog(habit_id=habit_id, notes=notes)
            session.add(log)
            # Update streak and totals
            result = await session.execute(select(Habit).where(Habit.id == habit_id))
            habit = result.scalar_one_or_none()
            if habit:
                habit.streak += 1
                habit.total_completions += 1
                habit.last_completed = datetime.now(timezone.utc)
            await session.commit()
            return {"logged": True, "habit_id": habit_id}

    async def get_habits(self, user_id: str) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(select(Habit).where(Habit.user_id == user_id))
            habits = result.scalars().all()
            return [
                {
                    "id": h.id, "name": h.name, "description": h.description,
                    "frequency": h.frequency, "streak": h.streak,
                    "total_completions": h.total_completions,
                    "last_completed": h.last_completed.isoformat() if h.last_completed else "",
                }
                for h in habits
            ]

    # ── Contact Operations ──

    async def get_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(select(Contact).where(Contact.user_id == user_id))
            contacts = result.scalars().all()
            return [
                {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone}
                for c in contacts
            ]

    # ── Calendar Operations ──

    async def get_calendar_events(self, user_id: str) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(
                select(CalendarEvent).where(CalendarEvent.user_id == user_id)
                .order_by(CalendarEvent.start_time)
            )
            events = result.scalars().all()
            return [
                {
                    "id": e.id, "title": e.title, "description": e.description,
                    "start_time": e.start_time.isoformat(), "end_time": e.end_time.isoformat() if e.end_time else "",
                }
                for e in events
            ]

    # ── Goal Operations ──

    async def get_goals(self, user_id: str) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(
                select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at.desc())
            )
            goals = result.scalars().all()
            return [
                {
                    "id": g.id, "title": g.title, "description": g.description,
                    "status": g.status, "progress": g.progress,
                    "target_date": g.target_date.isoformat() if g.target_date else "",
                }
                for g in goals
            ]

    # ── Session & Conversation Operations ──

    async def save_conversation(self, user_id: str, session_id: str,
                                 role: str, content: str, metadata: dict = None):
        async with self.async_session() as session:
            entry = ConversationHistory(
                user_id=user_id, session_id=session_id,
                role=role, content=content, metadata_=metadata or {},
            )
            session.add(entry)
            await session.commit()

    async def get_conversation_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        async with self.async_session() as session:
            result = await session.execute(
                select(ConversationHistory)
                .where(ConversationHistory.user_id == user_id)
                .order_by(ConversationHistory.timestamp.desc())
                .limit(limit)
            )
            entries = result.scalars().all()
            return [
                {
                    "role": e.role, "content": e.content,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in reversed(entries)
            ]

    # ── Preferences ──

    async def get_preferences(self, user_id: str) -> List[Dict[str, Any]]:
        user = await self.get_user_by_id(user_id)
        if user and user.get("preferences"):
            return [user["preferences"]]
        return []

    async def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the user's preferences JSON with an updated dictionary."""
        from sqlalchemy import select

        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"User not found: {user_id}")

            user.preferences = preferences
            user.updated_at = datetime.now(timezone.utc)
            await session.commit()

            return {"user_id": user_id, "preferences": user.preferences}
