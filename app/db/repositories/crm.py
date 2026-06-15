from datetime import UTC, datetime

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import UnifiedMessage
from app.db.models import (
    Animal,
    AuditLog,
    Channel,
    Contact,
    ContactChannelAccount,
    Conversation,
    HandoffTask,
    IntakeForm,
    Lead,
    Message,
)


class CRMRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_channel(self, business_id: int, channel_type: str) -> Channel:
        result = await self.session.execute(
            select(Channel).where(Channel.business_id == business_id, Channel.channel_type == channel_type)
        )
        channel = result.scalars().first()
        if channel:
            return channel
        channel = Channel(
            business_id=business_id,
            channel_type=channel_type,
            name=channel_type.title(),
            external_id=None,
            token_ref=None,
            webhook_secret=None,
            is_active=True,
        )
        self.session.add(channel)
        await self.session.flush()
        return channel

    async def get_or_create_contact(self, message: UnifiedMessage, channel: Channel) -> tuple[Contact, bool]:
        result = await self.session.execute(
            select(ContactChannelAccount).where(
                ContactChannelAccount.channel_id == channel.id,
                ContactChannelAccount.external_user_id == message.external_user_id,
            )
        )
        account = result.scalars().first()
        if account:
            contact = await self.session.get(Contact, account.contact_id)
            if contact and not contact.full_name and message.display_name:
                contact.full_name = message.display_name
            return contact, False

        contact = Contact(business_id=message.business_id, full_name=message.display_name)
        self.session.add(contact)
        await self.session.flush()
        account = ContactChannelAccount(
            contact_id=contact.id,
            channel_id=channel.id,
            external_user_id=message.external_user_id,
            external_chat_id=message.external_chat_id,
            username=message.username,
            display_name=message.display_name,
            created_at=datetime.now(UTC),
        )
        self.session.add(account)
        await self.session.flush()
        return contact, True

    async def get_or_create_conversation(self, business_id: int, contact_id: int, channel_id: int) -> tuple[Conversation, bool]:
        result = await self.session.execute(
            select(Conversation)
            .where(
                and_(
                    Conversation.business_id == business_id,
                    Conversation.contact_id == contact_id,
                    Conversation.channel_id == channel_id,
                    Conversation.status != "closed",
                )
            )
            .order_by(desc(Conversation.id))
        )
        conversation = result.scalars().first()
        if conversation:
            return conversation, False
        conversation = Conversation(
            business_id=business_id,
            contact_id=contact_id,
            channel_id=channel_id,
            status="idle",
            last_message_at=datetime.now(UTC),
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation, True

    async def add_message(self, conversation_id: int, sender_type: str, text: str, raw_payload: dict | None = None, llm_context: dict | None = None) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            text=text,
            raw_payload=raw_payload,
            llm_context=llm_context,
            created_at=datetime.now(UTC),
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def recent_messages(self, conversation_id: int, limit: int = 8) -> list[Message]:
        result = await self.session.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(desc(Message.id)).limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def create_or_update_intake(self, *, business_id: int, contact_id: int, conversation_id: int, source_channel: str, data: dict, urgency: str) -> IntakeForm:
        result = await self.session.execute(
            select(IntakeForm).where(
                IntakeForm.conversation_id == conversation_id,
                IntakeForm.status.in_(["collecting", "ready"]),
            )
        )
        form = result.scalars().first()
        if not form:
            form = IntakeForm(
                business_id=business_id,
                contact_id=contact_id,
                conversation_id=conversation_id,
                animal_id=None,
                source_channel=source_channel,
                urgency=urgency,
                status="collecting",
            )
            self.session.add(form)
        for key in ["client_name", "phone", "animal_type", "animal_name", "breed", "age", "sex", "complaint"]:
            value = data.get(key)
            if value and not getattr(form, key):
                setattr(form, key, value)
        form.urgency = urgency
        await self.session.flush()
        return form

    async def get_active_intake(self, conversation_id: int) -> IntakeForm | None:
        result = await self.session.execute(
            select(IntakeForm)
            .where(IntakeForm.conversation_id == conversation_id, IntakeForm.status.in_(["collecting", "ready"]))
            .order_by(desc(IntakeForm.id))
        )
        return result.scalars().first()

    async def update_contact_from_intake(self, contact_id: int, form: IntakeForm) -> Contact | None:
        contact = await self.session.get(Contact, contact_id)
        if not contact:
            return None
        if form.client_name and not contact.full_name:
            contact.full_name = form.client_name
        if form.phone and not contact.phone:
            contact.phone = form.phone
        await self.session.flush()
        return contact

    async def ensure_animal_from_intake(self, form: IntakeForm) -> Animal | None:
        if not form.animal_type and not form.animal_name:
            return None
        if form.animal_id:
            animal = await self.session.get(Animal, form.animal_id)
        else:
            animal = None
        if not animal:
            animal = Animal(contact_id=form.contact_id)
            self.session.add(animal)
            await self.session.flush()
            form.animal_id = animal.id
        for key, value in {
            "name": form.animal_name,
            "animal_type": form.animal_type,
            "breed": form.breed,
            "age": form.age,
            "sex": form.sex,
        }.items():
            if value and not getattr(animal, key):
                setattr(animal, key, value)
        await self.session.flush()
        return animal

    async def find_lead_for_intake(self, intake_form_id: int) -> Lead | None:
        result = await self.session.execute(select(Lead).where(Lead.intake_form_id == intake_form_id).order_by(desc(Lead.id)))
        return result.scalars().first()

    async def create_lead(self, *, business_id: int, contact_id: int, conversation_id: int, intake_form_id: int | None, source_channel: str, interest: str, priority: str = "normal") -> Lead:
        lead = Lead(
            business_id=business_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            intake_form_id=intake_form_id,
            source_channel=source_channel,
            interest=interest,
            status="new",
            priority=priority,
            created_at=datetime.now(UTC),
        )
        self.session.add(lead)
        await self.session.flush()
        return lead

    async def create_handoff(self, *, business_id: int, conversation_id: int, lead_id: int | None, reason: str, priority: str) -> HandoffTask:
        handoff = HandoffTask(
            business_id=business_id,
            conversation_id=conversation_id,
            lead_id=lead_id,
            reason=reason,
            priority=priority,
            status="open",
        )
        self.session.add(handoff)
        await self.session.flush()
        return handoff

    async def list_leads(self, business_id: int = 1, limit: int = 20) -> list[Lead]:
        result = await self.session.execute(
            select(Lead).where(Lead.business_id == business_id).order_by(desc(Lead.id)).limit(limit)
        )
        return list(result.scalars())

    async def set_lead_status(self, lead_id: int, status: str) -> Lead | None:
        lead = await self.session.get(Lead, lead_id)
        if not lead:
            return None
        lead.status = status
        await self.session.flush()
        return lead

    async def list_contacts(self, business_id: int = 1, limit: int = 20) -> list[Contact]:
        result = await self.session.execute(
            select(Contact).where(Contact.business_id == business_id).order_by(desc(Contact.id)).limit(limit)
        )
        return list(result.scalars())

    async def stuck_leads(self, business_id: int = 1, limit: int = 20) -> list[Lead]:
        result = await self.session.execute(
            select(Lead)
            .where(Lead.business_id == business_id, Lead.status.in_(["new", "waiting_for_doctor", "callback_needed", "in_progress"]))
            .order_by(desc(Lead.priority), Lead.created_at)
            .limit(limit)
        )
        return list(result.scalars())

    async def add_audit_log(self, *, business_id: int, action: str, payload: dict | None = None) -> AuditLog:
        log = AuditLog(business_id=business_id, action=action, payload=payload or {}, created_at=datetime.now(UTC))
        self.session.add(log)
        await self.session.flush()
        return log
