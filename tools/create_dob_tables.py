#!/usr/bin/env python3
"""
Create DOB training data tables in the local database.

This script creates the DOBTrainingData and DOBPipelineRun tables
in the local PostgreSQL database using SQLAlchemy's create_all().
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.db import create_all
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_dob_tables():
    """Create DOB training data tables in the local database."""
    try:
        logger.info("Creating DOB training data tables...")

        # Import models module to ensure DOB models are registered with SQLAlchemy
        import app.models  # noqa: F401

        # Create all tables
        await create_all()

        logger.info("DOB training data tables created successfully")
        print("✅ DOB training data tables created successfully")

    except Exception as e:
        logger.error(f"Failed to create DOB tables: {e}")
        print(f"❌ Failed to create DOB tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(create_dob_tables())
