"""
Dream Memory System - ثنائي المرحلة.
مستوحى من Nanobot (agent/memory.py) معاد كتابته بـ PostgreSQL backend.

المرحلة 1 (Consolidator): real-time - يلخّص الجلسات الطويلة
المرحلة 2 (Dream): lazy - ينظّم الذاكرة طويلة المدى (يُستدعى دورياً)

MECE Classification (من Nanobot):
- USER: معلومات عن المستخدم (من هو، تفضيلاته)
- MEMORY: حقائق مهمة من المحادثات
- SOUL: سلوك الوكيل (كيف يجب أن يتصرف)
- SKILL: مهارات/workflows قابلة لإعادة الاستخدام
"""
import logging
import hashlib
import json
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry, LongTermMemory
from app.llm import LLMMessage, llm_gateway

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MAX_SHORT_TERM_ENTRIES = 15  # قبل بدء الـ consolidation
CONSOLIDATION_BATCH_SIZE = 10  # كم entry يُلخّص في كل مرة
MAX_LONG_TERM_ITEMS = 20  # حد أقصى للذاكرة طويلة المدى لكل نوع
DREAM_TRIGGER_INTERVAL = 5  # كل كم رسالة نشغّل Dream


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Prompts (MECE - من Nanobot)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONSOLIDATOR_PROMPT = """أنت مساعد ذكي متخصص في تلخيص المحادثات.

ستحصل على محادثة بين مستخدم ومساعد ذكي (NorX). مهمتك:
1. تلخيص المحادثة في 3-5 جمل
2. استخراج أي معلومات مهمة عن المستخدم (اسمه، اهتماماته، تفضيلاته)
3. استخراج أي حقائق مهمة تم مناقشتها

اكتب التلخيص بالعربية. كن مختصراً ودقيقاً.

المحادثة:
{conversation}

اكتب التلخيص فقط بدون مقدمة:"""


DREAM_PROMPT = """أنت مساعد ذكي متخصص في تنظيم الذاكرة طويلة المدى.

مهمتك: تحديث ملفات الذاكرة بناءً على أحداث جديدة.

## ملفات الذاكرة الحالية:

### USER (معلومات المستخدم):
{user_memory}

### MEMORY (حقائق مهمة):
{facts_memory}

### SOUL (سلوك الوكيل):
{soul_memory}

### SKILL (مهارات قابلة لإعادة الاستخدام):
{skill_memory}

## أحداث جديدة (مُلخّصة):
{new_events}

## التعليمات:

حدّث الملفات بناءً على الأحداث الجديدة. قواعد:
1. **USER**: معلومات عن المستخدم (اسم، مهنة، اهتمامات، تفضيلات)
2. **MEMORY**: حقائق مهمة تم مناقشتها (ليست معرفة عامة)
3. **SOUL**: كيف يجب أن يتصرف الوكيل مع هذا المستخدم بالذات
4. **SKILL**: workflows أو حلول قابلة لإعادة الاستخدام

قواعد التحديث:
- **لا تحذف** المعلومات الموجودة ما لم تكن خاطئة
- **أضف** المعلومات الجديدة في المكان المناسب
- **حدّث** المعلومات القديمة إذا تغيرت
- **كن مختصراً** - كل ملف لا يتجاوز 500 كلمة
- **استخدم التنسيق**: عناوين فرعية + نقاط

## الصيغة المطلوبة:

أعد الملفات بالصيغة التالية (JSON):
```json
{{
  "user": "محتوى الملف المحدّث",
  "memory": "محتوى الملف المحدّث",
  "soul": "محتوى الملف المحدّث",
  "skill": "محتوى الملف المحدّث"
}}
```

إذا لم يتغير ملف، أعده كما هو. اكتب JSON فقط بدون شرح."""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Memory Store
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MemoryStore:
    """يدير الذاكرة قصيرة وطويلة المدى."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_context_for_agent(
        self,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID,
        query: Optional[str] = None,
    ) -> str:
        """
        يجلب السياق الكامل للوكيل:
        - الذاكرة طويلة المدى (USER + MEMORY + SOUL + SKILL)
        - آخر entries من الذاكرة قصيرة المدى

        يُرجع نص يُضاف للـ system prompt.
        """
        # 1. Long-term memory
        long_term = await self._get_long_term(tenant_id, user_id, agent_id)

        # 2. Recent short-term entries (last 5)
        recent = await self._get_recent_entries(tenant_id, user_id, limit=5)

        # Build context
        parts = []

        if long_term:
            parts.append("## ذاكرتي عنك")
            if long_term.get("user"):
                parts.append(f"### عن المستخدم:\n{long_term['user']}")
            if long_term.get("memory"):
                parts.append(f"### حقائق مهمة:\n{long_term['memory']}")
            if long_term.get("soul"):
                parts.append(f"### كيف أتعامل معك:\n{long_term['soul']}")
            if long_term.get("skill"):
                parts.append(f"### مهارات تعلمتها:\n{long_term['skill']}")

        if recent:
            parts.append("\n## آخر ما تحدثنا عنه:")
            for entry in recent:
                parts.append(f"- {entry['content'][:150]}")

        if not parts:
            return ""

        return "\n\n".join(parts)

    async def add_entry(
        self,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID,
        content: str,
        session_id: Optional[UUID] = None,
        entry_type: str = "message",
    ) -> MemoryEntry:
        """يضيف entry للذاكرة قصيرة المدى."""
        # Get next cursor
        last_entry = await self.db.execute(
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
            )
            .order_by(desc(MemoryEntry.cursor))
            .limit(1)
        )
        last = last_entry.scalar_one_or_none()
        next_cursor = (last.cursor + 1) if last else 0

        entry = MemoryEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            cursor=next_cursor,
            content=content,
            entry_metadata={"type": entry_type},
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def maybe_consolidate(
        self,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID,
    ) -> bool:
        """
        المرحلة 1: Consolidator - يلخّص الذاكرة قصيرة المدى إذا تجاوزت الحد.

        يُستدعى بعد كل رسالة. يُرجع True إذا تم consolidation.
        """
        # Count unconsolidated entries
        count_result = await self.db.execute(
            select(func.count(MemoryEntry.id)).where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
                MemoryEntry.is_consolidated == False,
            )
        )
        count = count_result.scalar() or 0

        if count < MAX_SHORT_TERM_ENTRIES:
            return False

        logger.info(f"🧠 Consolidating {count} memory entries...")

        # Get oldest unconsolidated entries
        entries_result = await self.db.execute(
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
                MemoryEntry.is_consolidated == False,
            )
            .order_by(MemoryEntry.cursor.asc())
            .limit(CONSOLIDATION_BATCH_SIZE)
        )
        entries = entries_result.scalars().all()

        if not entries:
            return False

        # Build conversation text
        conversation = "\n".join([e.content for e in entries])

        # Generate summary
        try:
            prompt = CONSOLIDATOR_PROMPT.format(conversation=conversation[:4000])
            summary = await llm_gateway.chat_complete(
                messages=[LLMMessage(role="user", content=prompt)],
                model="meta/llama-3.1-70b-instruct",
                provider="nvidia",
                max_tokens=500,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Consolidation LLM call failed: {e}")
            return False

        if not summary:
            return False

        # Save summary as new entry + mark old entries as consolidated
        last_cursor = entries[-1].cursor
        summary_entry = MemoryEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            cursor=last_cursor + 1,
            content=f"[ملخص محادثة سابقة]: {summary}",
            summary=summary,
            is_consolidated=True,
            entry_metadata={
                "type": "consolidation",
                "consolidated_from": [str(e.id) for e in entries],
            },
        )
        self.db.add(summary_entry)

        # Mark old entries as consolidated
        for entry in entries:
            entry.is_consolidated = True

        await self.db.flush()
        logger.info(f"✅ Consolidated {len(entries)} entries into summary")
        return True

    async def maybe_dream(
        self,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID,
    ) -> bool:
        """
        المرحلة 2: Dream - ينظّم الذاكرة طويلة المدى.

        يُستدعى كل DREAM_TRIGGER_INTERVAL رسالة. يُرجع True إذا تم dream.
        """
        # Count messages since last dream
        count_result = await self.db.execute(
            select(func.count(MemoryEntry.id)).where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
            )
        )
        total_count = count_result.scalar() or 0

        # Get last dream time
        last_dream = await self.db.execute(
            select(LongTermMemory.last_dream_at)
            .where(
                LongTermMemory.tenant_id == tenant_id,
                LongTermMemory.user_id == user_id,
                LongTermMemory.agent_id == agent_id,
            )
            .order_by(desc(LongTermMemory.last_dream_at))
            .limit(1)
        )
        last_dream_at = last_dream.scalar_one_or_none()

        # Check if we should dream
        # Count entries since last dream
        if last_dream_at:
            since_dream = await self.db.execute(
                select(func.count(MemoryEntry.id)).where(
                    MemoryEntry.tenant_id == tenant_id,
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.timestamp > last_dream_at,
                )
            )
            new_count = since_dream.scalar() or 0
        else:
            new_count = total_count

        if new_count < DREAM_TRIGGER_INTERVAL:
            return False

        logger.info(f"💤 Dreaming: organizing {new_count} new entries...")

        # Get new consolidated entries (the summaries)
        new_entries_result = await self.db.execute(
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
                MemoryEntry.is_consolidated == True,
            )
            .order_by(MemoryEntry.cursor.desc())
            .limit(10)
        )
        new_entries = new_entries_result.scalars().all()

        if not new_entries:
            return False

        # Get existing long-term memory
        long_term = await self._get_long_term_raw(tenant_id, user_id, agent_id)

        # Build dream prompt
        new_events = "\n".join([
            e.summary or e.content for e in reversed(new_entries)
        ][:5])  # last 5 summaries

        prompt = DREAM_PROMPT.format(
            user_memory=long_term.get("user", "فارغ"),
            facts_memory=long_term.get("memory", "فارغ"),
            soul_memory=long_term.get("soul", "فارغ"),
            skill_memory=long_term.get("skill", "فارغ"),
            new_events=new_events[:3000],
        )

        # Call LLM
        try:
            result = await llm_gateway.chat_complete(
                messages=[LLMMessage(role="user", content=prompt)],
                model="meta/llama-3.1-70b-instruct",
                provider="nvidia",
                max_tokens=2000,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Dream LLM call failed: {e}")
            return False

        if not result:
            return False

        # Parse JSON response
        updates = self._parse_dream_result(result)
        if not updates:
            logger.warning("Dream: failed to parse LLM response")
            return False

        # Update long-term memory
        now = datetime.utcnow()
        for memory_type, new_content in updates.items():
            if memory_type not in ("user", "memory", "soul", "skill"):
                continue
            if not new_content or not new_content.strip():
                continue

            new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

            # Get existing
            existing_result = await self.db.execute(
                select(LongTermMemory).where(
                    LongTermMemory.tenant_id == tenant_id,
                    LongTermMemory.user_id == user_id,
                    LongTermMemory.agent_id == agent_id,
                    LongTermMemory.memory_type == memory_type,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Update (versioned)
                existing.version += 1
                existing.parent_hash = existing.content_hash
                existing.content_hash = new_hash
                existing.content = new_content
                existing.last_dream_at = now
            else:
                # Create new
                new_mem = LongTermMemory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    memory_type=memory_type,
                    content=new_content,
                    content_hash=new_hash,
                    last_dream_at=now,
                )
                self.db.add(new_mem)

        await self.db.flush()
        logger.info("✅ Dream completed: updated long-term memory")
        return True

    async def _get_long_term(
        self, tenant_id: UUID, user_id: UUID, agent_id: UUID
    ) -> Dict[str, str]:
        """يجلب الذاكرة طويلة المدى كـ dict."""
        result = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.tenant_id == tenant_id,
                LongTermMemory.user_id == user_id,
                LongTermMemory.agent_id == agent_id,
            )
        )
        items = result.scalars().all()
        return {item.memory_type: item.content for item in items}

    async def _get_long_term_raw(
        self, tenant_id: UUID, user_id: UUID, agent_id: UUID
    ) -> Dict[str, str]:
        """Same as _get_long_term (alias)."""
        return await self._get_long_term(tenant_id, user_id, agent_id)

    async def _get_recent_entries(
        self, tenant_id: UUID, user_id: UUID, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """يجلب آخر entries من الذاكرة قصيرة المدى."""
        result = await self.db.execute(
            select(MemoryEntry)
            .where(
                MemoryEntry.tenant_id == tenant_id,
                MemoryEntry.user_id == user_id,
            )
            .order_by(desc(MemoryEntry.cursor))
            .limit(limit)
        )
        entries = result.scalars().all()
        return [
            {
                "content": e.content,
                "summary": e.summary,
                "is_consolidated": e.is_consolidated,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in reversed(entries)
        ]

    def _parse_dream_result(self, result: str) -> Dict[str, str]:
        """يحلّل نتيجة Dream (JSON) من الـ LLM."""
        # Try to extract JSON from the response
        try:
            # Find JSON block
            if "```json" in result:
                start = result.index("```json") + 7
                end = result.index("```", start)
                json_str = result[start:end].strip()
            elif "```" in result:
                start = result.index("```") + 3
                end = result.index("```", start)
                json_str = result[start:end].strip()
            elif "{" in result:
                start = result.index("{")
                end = result.rindex("}") + 1
                json_str = result[start:end]
            else:
                return {}

            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse dream JSON: {e}")
            return {}
