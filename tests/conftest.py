import os
import tempfile
from pathlib import Path

# Configure isolated test database in env before any backend imports occur
test_db_file = Path(tempfile.gettempdir()) / "aetherpub_test_suite_isolated.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_file.as_posix()}"

import asyncio
import pytest
from backend.app.core.database import Base, engine

@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Initializes schema on isolated test DB."""
    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init())

    yield

    if test_db_file.exists():
        try:
            test_db_file.unlink()
        except Exception:
            pass
