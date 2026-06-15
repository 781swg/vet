from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BusinessRule, DoctorCapability, KnowledgeChunk, Service


def keyword_score(query: str, text: str) -> int:
    query_tokens = [token for token in query.lower().replace("?", " ").split() if len(token) > 2]
    text_lower = text.lower()
    return sum(1 for token in query_tokens if token in text_lower)


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, business_id: int, query: str, limit: int = 5) -> list[dict]:
        chunks = (await self.session.execute(select(KnowledgeChunk).where(KnowledgeChunk.business_id == business_id))).scalars().all()
        scored = [
            {"type": "knowledge_chunk", "id": chunk.id, "content": chunk.content, "score": keyword_score(query, chunk.content)}
            for chunk in chunks
        ]
        return [item for item in sorted(scored, key=lambda item: item["score"], reverse=True) if item["score"] > 0][:limit]

    async def business_rules(self, business_id: int) -> list[dict]:
        rules = (await self.session.execute(select(BusinessRule).where(BusinessRule.business_id == business_id, BusinessRule.is_active.is_(True)))).scalars().all()
        return [{"rule_key": rule.rule_key, "title": rule.title, "content": rule.content} for rule in rules]

    async def capability_matches(self, business_id: int, query: str, limit: int = 5) -> list[dict]:
        capabilities = (await self.session.execute(select(DoctorCapability).where(DoctorCapability.business_id == business_id))).scalars().all()
        scored = []
        for item in capabilities:
            text = f"{item.capability_key} {item.title} {item.description or ''}"
            scored.append(
                {
                    "capability_key": item.capability_key,
                    "title": item.title,
                    "description": item.description,
                    "is_available": item.is_available,
                    "answer_template": item.answer_template,
                    "fallback_text": item.fallback_text,
                    "score": keyword_score(query, text),
                }
            )
        return [item for item in sorted(scored, key=lambda item: item["score"], reverse=True) if item["score"] > 0][:limit]

