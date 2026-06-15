import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.models import AnimalType, Business, BusinessRule, Channel, DoctorCapability, DoctorUser, Price, PromptConfig, Service
from app.db.session import SessionLocal
from app.llm.prompts import SYSTEM_PROMPT


async def seed() -> None:
    settings = get_settings()
    business_id = settings.default_business_id
    async with SessionLocal() as session:
        business = await session.get(Business, business_id)
        if not business:
            business = Business(
                id=business_id,
                name="Ветклиника Дениса",
                phone="+7 (383) 271-09-01",
                address="ул. Богдана Хмельницкого, 39",
                timezone=settings.business_timezone,
                description="Небольшая семейная ветеринарная клиника. Один внимательный доктор, которому помогает семья.",
                working_hours={"comment": "Ночной прием и прием в выходные дни — по согласованию с врачом."},
            )
            session.add(business)
            await session.flush()
        else:
            business.phone = "+7 (383) 271-09-01"
            business.address = "ул. Богдана Хмельницкого, 39"
            business.timezone = settings.business_timezone
            business.working_hours = {"comment": "Ночной прием и прием в выходные дни — по согласованию с врачом."}

        channel_names = {
            "telegram": f"Telegram @{settings.telegram_client_bot_username}",
            "site": "Сайт клиники",
            "whatsapp": "WhatsApp",
            "max": "MAX",
            "vk": "VK",
        }
        channel_external_ids = {
            "telegram": settings.telegram_client_bot_username,
            "site": settings.public_base_url,
            "whatsapp": None,
            "max": None,
            "vk": None,
        }
        for channel_type, channel_name in channel_names.items():
            exists = await session.scalar(select(Channel).where(Channel.business_id == business.id, Channel.channel_type == channel_type))
            if not exists:
                session.add(
                    Channel(
                        business_id=business.id,
                        channel_type=channel_type,
                        name=channel_name,
                        external_id=channel_external_ids[channel_type],
                        is_active=True,
                    )
                )
            else:
                exists.name = channel_name
                exists.external_id = channel_external_ids[channel_type]

        animals = [
            ("кошка", True, None),
            ("собака", True, None),
            ("кролик", True, "Доктор принимает кроликов, детали состояния лучше уточнять."),
            ("грызун", True, None),
            ("птица", True, "Прием птиц нужно уточнять по ситуации."),
            ("рептилия", False, "Сейчас рептилии не принимаются."),
        ]
        for name, supported, comment in animals:
            item = await session.scalar(select(AnimalType).where(AnimalType.business_id == business.id, AnimalType.name == name))
            if not item:
                session.add(AnimalType(business_id=business.id, name=name, is_supported=supported, comment=comment))

        services_data = [
            ("первичная консультация", "прием", "Первичный осмотр животного врачом."),
            ("повторный прием", "прием", "Повторный прием после первичного осмотра."),
            ("вакцинация", "профилактика", "Вакцинация животных, требуется подтверждение врачом."),
            ("обработка от паразитов", "профилактика", "Подбор обработки подтверждает врач."),
            ("стерилизация кошки", "хирургия", "Плановая стерилизация кошки после консультации."),
            ("кастрация кота", "хирургия", "Плановая кастрация кота после консультации."),
            ("осмотр кролика", "прием", "Осмотр кролика и сбор первичной информации."),
            ("ночной выезд", "выезд", "Ночной выезд возможен только по подтверждению врача."),
            ("ветмагазин", "магазин", "Ветмагазин при клинике."),
            ("консультация по уходу", "консультация", "Общие вопросы ухода без назначения лечения."),
        ]
        services: list[Service] = []
        for name, category, description in services_data:
            service = await session.scalar(select(Service).where(Service.business_id == business.id, Service.name == name))
            if not service:
                service = Service(
                    business_id=business.id,
                    name=name,
                    category=category,
                    description=description,
                    is_active=True,
                    requires_doctor_confirmation=True,
                )
                session.add(service)
                await session.flush()
            services.append(service)

        for service in services:
            price = await session.scalar(select(Price).where(Price.service_id == service.id, Price.is_active.is_(True)))
            if not price:
                session.add(
                    Price(
                        service_id=service.id,
                        price_from=Decimal("500.00"),
                        price_to=Decimal("3000.00"),
                        currency="RUB",
                        comment="Цена требует подтверждения врачом.",
                        is_active=True,
                    )
                )

        capabilities = [
            ("treats_rabbits", "Прием кроликов", "Доктор принимает кроликов.", True, "Да, доктор принимает кроликов.", None),
            ("has_vet_store", "Ветмагазин", "При клинике есть ветмагазин.", True, "Да, у нас есть ветмагазин.", None),
            ("night_call", "Ночной выезд", "Ночной выезд возможен по подтверждению врача.", True, "Ночной выезд нужно подтвердить у врача.", None),
            ("xray", "Рентген", "Рентген сейчас не предоставляется.", False, None, "Рентген сейчас не предоставляется."),
            ("ultrasound", "УЗИ", "УЗИ нужно уточнять.", False, None, "УЗИ сейчас нужно уточнять у врача."),
            ("lab_tests", "Анализы", "Лабораторные анализы нужно уточнять.", False, None, "Анализы нужно уточнять у врача."),
        ]
        for key, title, description, available, template, fallback in capabilities:
            item = await session.scalar(select(DoctorCapability).where(DoctorCapability.business_id == business.id, DoctorCapability.capability_key == key))
            if not item:
                session.add(
                    DoctorCapability(
                        business_id=business.id,
                        capability_key=key,
                        title=title,
                        description=description,
                        is_available=available,
                        answer_template=template,
                        fallback_text=fallback,
                    )
                )

        rules = [
            ("no_treatment", "AI не назначает лечение", "AI не назначает лечение и дозировки."),
            ("no_diagnosis", "AI не ставит диагноз", "AI не ставит диагнозы и не заменяет врача."),
            ("emergency_handoff", "Срочность передавать врачу", "При срочных симптомах создавать handoff врачу."),
            ("doctor_busy", "Врач может быть занят", "Если врач не отвечает, мягко объяснять, что он может помогать текущему пациенту."),
        ]
        for key, title, content in rules:
            item = await session.scalar(select(BusinessRule).where(BusinessRule.business_id == business.id, BusinessRule.rule_key == key))
            if not item:
                session.add(BusinessRule(business_id=business.id, rule_key=key, title=title, content=content, is_active=True))

        prompt = await session.scalar(select(PromptConfig).where(PromptConfig.business_id == business.id))
        if not prompt:
            session.add(
                PromptConfig(
                    business_id=business.id,
                    system_prompt=SYSTEM_PROMPT,
                    tone="теплый, добрый, аккуратный",
                    forbidden_topics={"medical": ["diagnosis", "treatment", "dosage"]},
                    escalation_rules={"emergency": True},
                )
            )

        if settings.doctor_telegram_user_id:
            doctor = await session.scalar(
                select(DoctorUser).where(
                    DoctorUser.business_id == business.id,
                    DoctorUser.telegram_user_id == settings.doctor_telegram_user_id,
                )
            )
            if not doctor:
                session.add(
                    DoctorUser(
                        business_id=business.id,
                        telegram_user_id=settings.doctor_telegram_user_id,
                        full_name="Доктор Денис",
                        role="doctor",
                        is_active=True,
                    )
                )

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
