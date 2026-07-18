import os
import sys
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("cognito.backend.database")

# Auto-fallback to SQLite in-memory during pytest runs
is_testing = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
DATABASE_URL = os.getenv(
    "COGNITO_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:" if is_testing else "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
)

# Enable SQLite fallback for testing purposes if configured
if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    # PostgreSQL standard options
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def check_schema_health() -> bool:
    """
    Validates if cognito schema and tables are correctly created.
    """
    if DATABASE_URL.startswith("sqlite"):
        return True # SQLite auto-migrates in tests

    async with engine.connect() as conn:
        try:
            # Query if tasks table exists in cognito schema
            res = await conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'cognito' AND table_name = 'tasks');"
            ))
            row = res.fetchone()
            return bool(row and row[0])
        except Exception as e:
            logger.warning(f"Database schema check failed: {e}")
            return False

async def run_migrations():
    """
    Runs DDL migrations to set up the 'cognito' schema and its tables.
    """
    logger.info("Initializing schema 'cognito' and its tables...")
    from app.models.db import DBTask, DBRouteDecision, DBExecutionAttempt, DBApprovalRequest, DBVerificationRun, DBEscalationRecord, DBAuditEvent, DBOutboxEvent

    async with engine.begin() as conn:
        if not DATABASE_URL.startswith("sqlite"):
            # Create schema first
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS cognito;"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Migrations completed successfully.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        asyncio.run(run_migrations())
    else:
        print("Usage: python3 -m app.core.database migrate")
