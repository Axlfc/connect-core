import time
import logging
import uuid
from typing import List, Optional, Dict, Any
from app.models.domain import Fact
from app.models.db import DBFact
from app.core.database import get_db_sync_session

logger = logging.getLogger("cognito.backend.fact_memory")

class FactMemoryManager:
    """
    Structured Fact Memory Store (AUD-014 MVP).
    Persists structured facts (preferences, style rules, project facts) per User/Project/Org
    in the shared database storage (PostgreSQL / SQLite).
    """

    def save_fact(
        self,
        fact_text: str,
        category: str = "general",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> Fact:
        """
        Saves or updates a fact tied to a user, project, or organization scope.
        """
        clean_text = fact_text.strip()
        if not clean_text:
            raise ValueError("Fact text cannot be empty.")

        now = time.time()
        db = get_db_sync_session()
        try:
            # Check if identical fact exists for the given scope
            query = db.query(DBFact).filter(DBFact.fact_text == clean_text)
            if user_id:
                query = query.filter(DBFact.user_id == user_id)
            if project_id:
                query = query.filter(DBFact.project_id == project_id)
            if org_id:
                query = query.filter(DBFact.org_id == org_id)

            existing = query.first()
            if existing:
                existing.category = category or existing.category
                existing.updated_at = now
                db.commit()
                return Fact(
                    fact_id=existing.fact_id,
                    org_id=existing.org_id,
                    project_id=existing.project_id,
                    user_id=existing.user_id,
                    category=existing.category,
                    fact_text=existing.fact_text,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                )

            fact_id = f"fact-{uuid.uuid4().hex[:12]}"
            db_item = DBFact(
                fact_id=fact_id,
                org_id=org_id,
                project_id=project_id,
                user_id=user_id,
                category=category or "general",
                fact_text=clean_text,
                created_at=now,
                updated_at=now,
            )
            db.add(db_item)
            db.commit()
            return Fact(
                fact_id=db_item.fact_id,
                org_id=db_item.org_id,
                project_id=db_item.project_id,
                user_id=db_item.user_id,
                category=db_item.category,
                fact_text=db_item.fact_text,
                created_at=db_item.created_at,
                updated_at=db_item.updated_at,
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save fact to DB: {e}")
            raise
        finally:
            db.close()

    def get_facts_for_context(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[Fact]:
        """
        Retrieves relevant facts matching user_id, project_id, or org_id scope.
        """
        db = get_db_sync_session()
        try:
            from sqlalchemy import or_

            conditions = []
            if user_id:
                conditions.append(DBFact.user_id == user_id)
            if project_id:
                conditions.append(DBFact.project_id == project_id)
            if org_id:
                conditions.append(DBFact.org_id == org_id)

            if not conditions:
                return []

            rows = db.query(DBFact).filter(or_(*conditions)).order_by(DBFact.category, DBFact.created_at).all()
            return [
                Fact(
                    fact_id=row.fact_id,
                    org_id=row.org_id,
                    project_id=row.project_id,
                    user_id=row.user_id,
                    category=row.category,
                    fact_text=row.fact_text,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Error querying facts from DB: {e}")
            return []
        finally:
            db.close()

    def format_facts_for_prompt(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> str:
        """
        Formats facts into a Markdown block ready to be appended to system prompt.
        """
        facts = self.get_facts_for_context(user_id=user_id, project_id=project_id, org_id=org_id)
        if not facts:
            return ""

        lines = ["Hechos recordados (User / Project Memory):"]
        for fact in facts:
            scope_info = []
            if fact.user_id:
                scope_info.append("Usuario")
            if fact.project_id:
                scope_info.append("Proyecto")
            scope_str = f" [{', '.join(scope_info)}]" if scope_info else ""
            lines.append(f"- [{fact.category.capitalize()}]{scope_str}: {fact.fact_text}")

        return "\n".join(lines)


fact_memory_manager = FactMemoryManager()
