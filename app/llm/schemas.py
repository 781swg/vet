from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class AnimalUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    animal_type: str | None = None
    breed: str | None = None
    age: str | None = None
    sex: str | None = None
    is_neutered: bool | None = None
    notes: str | None = None


class IntakeFormUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_name: str | None = None
    phone: str | None = None
    animal_type: str | None = None
    animal_name: str | None = None
    breed: str | None = None
    age: str | None = None
    sex: str | None = None
    complaint: str | None = None
    symptoms_started_at_text: str | None = None
    urgency: Literal["low", "normal", "high", "emergency"] | None = None
    preferred_callback_time: str | None = None


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    interest: str | None = None
    priority: Literal["normal", "high", "emergency"] | None = None
    status: str | None = None


class HandoffUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reason: str | None = None
    priority: Literal["normal", "high", "emergency"] | None = None


class DatabaseUpdates(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contact: ContactUpdate = Field(default_factory=ContactUpdate)
    animal: AnimalUpdate = Field(default_factory=AnimalUpdate)
    intake_form: IntakeFormUpdate = Field(default_factory=IntakeFormUpdate)
    lead: LeadUpdate = Field(default_factory=LeadUpdate)
    handoff_task: HandoffUpdate = Field(default_factory=HandoffUpdate)


class DoctorNotificationDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = None
    key_facts: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    recommended_action: str | None = None


class LLMAgentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: str
    answer_to_client: str
    need_handoff: bool = False
    handoff_reason: str | None = None
    urgency: Literal["low", "normal", "high", "emergency"] = "normal"
    service_found: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    collected_data: dict = Field(default_factory=dict)
    next_action: str = "answer_only"
    database_updates: DatabaseUpdates = Field(default_factory=DatabaseUpdates)
    doctor_notification: DoctorNotificationDraft = Field(default_factory=DoctorNotificationDraft)

    def database_intake_data(self) -> dict:
        data: dict = {}
        contact = self.database_updates.contact
        animal = self.database_updates.animal
        intake = self.database_updates.intake_form

        if contact.full_name:
            data["client_name"] = contact.full_name
        if contact.phone:
            data["phone"] = contact.phone

        for source_key, target_key in {
            "name": "animal_name",
            "animal_type": "animal_type",
            "breed": "breed",
            "age": "age",
            "sex": "sex",
        }.items():
            value = getattr(animal, source_key)
            if value:
                data[target_key] = value

        for key, value in intake.model_dump(exclude_none=True).items():
            if key != "urgency":
                data[key] = value

        return data
