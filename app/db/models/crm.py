from datetime import date, datetime, time

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class ContactChannelAccount(Base):
    __tablename__ = "contact_channel_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    external_user_id: Mapped[str] = mapped_column(String(255), index=True)
    external_chat_id: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Animal(TimestampMixin, Base):
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    name: Mapped[str | None] = mapped_column(String(255))
    animal_type: Mapped[str | None] = mapped_column(String(128))
    breed: Mapped[str | None] = mapped_column(String(255))
    age: Mapped[str | None] = mapped_column(String(128))
    sex: Mapped[str | None] = mapped_column(String(64))
    is_neutered: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    status: Mapped[str] = mapped_column(String(64), default="idle")
    current_intent: Mapped[str | None] = mapped_column(String(64))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender_type: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    llm_context: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntakeForm(TimestampMixin, Base):
    __tablename__ = "intake_forms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"))
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    client_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    animal_type: Mapped[str | None] = mapped_column(String(128))
    animal_name: Mapped[str | None] = mapped_column(String(255))
    breed: Mapped[str | None] = mapped_column(String(255))
    age: Mapped[str | None] = mapped_column(String(128))
    sex: Mapped[str | None] = mapped_column(String(64))
    complaint: Mapped[str | None] = mapped_column(Text)
    symptoms_started_at_text: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(32), default="normal")
    preferred_callback_time: Mapped[str | None] = mapped_column(String(255))
    source_channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(64), default="collecting")


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    intake_form_id: Mapped[int | None] = mapped_column(ForeignKey("intake_forms.id"))
    source_channel: Mapped[str] = mapped_column(String(32))
    interest: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="new", index=True)
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    assigned_to: Mapped[str | None] = mapped_column(String(255))


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))
    appointment_date: Mapped[date | None] = mapped_column(Date)
    appointment_time: Mapped[time | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(64), default="planned")
    comment: Mapped[str | None] = mapped_column(Text)


class HandoffTask(TimestampMixin, Base):
    __tablename__ = "handoff_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"))
    reason: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    status: Mapped[str] = mapped_column(String(64), default="open")
    assigned_to: Mapped[str | None] = mapped_column(String(255))
