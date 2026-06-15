from datetime import datetime

from pydantic import BaseModel, Field


class ReportData(BaseModel):
    report_type: str
    period_start: datetime
    period_end: datetime
    total_messages: int = 0
    client_messages: int = 0
    bot_messages: int = 0
    new_contacts: int = 0
    new_leads: int = 0
    emergency_leads: int = 0
    high_priority_leads: int = 0
    leads_by_channel: dict[str, int] = Field(default_factory=dict)
    leads_by_status: dict[str, int] = Field(default_factory=dict)
    top_services: list[tuple[str, int]] = Field(default_factory=list)
    top_animal_types: list[tuple[str, int]] = Field(default_factory=list)
    appointments_created: int = 0
    handoffs_created: int = 0
    waiting_for_doctor_count: int = 0
    lost_leads_count: int = 0
    latest_leads: list[dict] = Field(default_factory=list)

