"""
DOB Data Fetcher Service

Async service for connecting to external caller data source and fetching
DOB training data with parameterized queries and privacy safeguards.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.dob_pipeline import DOBAttemptData, DOBDataQueryParams, DOBPipelineStats
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DOBDataFetcher:
    """
    Service for fetching DOB training data from external caller database.

    Handles connection to external PostgreSQL database, executes parameterized
    queries for DOB data extraction, and ensures data privacy through filtering.
    """

    def __init__(self):
        self._engine = None
        self._session_maker = None
        self._connected = False

    async def connect(self) -> None:
        """
        Establish connection to external caller data database.

        Raises:
            ValueError: If CALLER_SOURCE_DATA environment variable is not set
            Exception: If database connection fails
        """
        if not settings.caller_source_data:
            raise ValueError("CALLER_SOURCE_DATA environment variable must be set to connect to external database")

        if self._connected:
            logger.debug("External database connection already established")
            return

        try:
            # Convert PostgreSQL URL to async format if needed
            db_url = settings.caller_source_data
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

            self._engine = create_async_engine(
                db_url,
                echo=False,  # Disable SQL logging for privacy
                pool_pre_ping=True,  # Test connections before use
                pool_size=5,
                max_overflow=10,
            )

            self._session_maker = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)

            # Test connection
            async with self._session_maker() as session:
                await session.execute(text("SELECT 1"))
                logger.info("Successfully connected to external caller data database")

            self._connected = True

        except Exception as e:
            logger.error(f"Failed to connect to external database: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection to external database."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
            self._connected = False
            logger.info("Disconnected from external caller data database")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for database sessions.

        Ensures proper session cleanup and error handling.
        """
        if not self._connected or not self._session_maker:
            raise RuntimeError("Database connection not established. Call connect() first.")

        session = self._session_maker()
        try:
            yield session
        finally:
            await session.close()

    async def fetch_dob_attempts(self, params: DOBDataQueryParams) -> List[DOBAttemptData]:
        """
        Fetch DOB attempts from external database using parameterized query.

        Executes the complex SQL query to extract DOB data from JSONB fields
        with proper filtering for privacy and data quality.

        Args:
            params: Query parameters including date range and limits

        Returns:
            List of DOB attempt data models

        Raises:
            ValueError: If date range is invalid
            Exception: If database query fails
        """
        params.validate_date_range()

        # Build the parameterized SQL query based on the request specification
        query = """
        WITH dob_attempts AS (
          SELECT
            v.id,
            v.caller_responses,
            (v.caller_responses -> 'dob' ->> 'value') AS dob_value,
            (v.caller_responses -> 'patient' ->> 'id') AS patient_id,
            jsonb_array_elements(v.caller_responses -> 'dob' -> 'attempts') AS attempt
          FROM voice v
          WHERE v.caller_responses ? 'dob'
            AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(v.caller_responses -> 'dob' -> 'attempts') a
              WHERE a ->> 'input' ~ '[A-Za-z]'
            )
            AND call_start_time >= :start_date
            AND call_end_time <= :end_date
            AND (v.caller_responses -> 'patient' ->> 'id') IS NULL
        )
        SELECT
          da.id,
          da.dob_value::date,
          da.patient_id,
          da.attempt ->> 'input' AS dob_input,
          (da.attempt ->> 'attempt')::int AS attempt_num,
          CASE
            WHEN da.attempt ->> 'input' ~ '[A-Za-z]' THEN 'spoken'
            ELSE 'dtmf'
          END AS input_type,
          CASE
            WHEN jsonb_array_length(da.caller_responses -> 'dob' -> 'attempts') > 1 THEN 'multiple_attempts'
            WHEN (da.attempt ->> 'input' ~ '[A-Za-z]') AND ((da.attempt ->> 'input') != da.dob_value) THEN 'spoken_candidate'
            WHEN da.dob_value IS NULL THEN 'failure'
            ELSE 'clean'
          END AS classification
        FROM dob_attempts da
        ORDER BY da.id, attempt_num DESC
        """

        # Add LIMIT clause if max_records is specified
        if params.max_records:
            query += " LIMIT :max_records"

        logger.info(f"Executing DOB data query for date range: {params.start_date} to {params.end_date}")

        async with self.session() as session:
            try:
                result = await session.execute(
                    text(query),
                    {
                        "start_date": params.start_date,
                        "end_date": params.end_date,
                        "max_records": params.max_records,
                    },
                )

                rows = result.fetchall()
                logger.info(f"Retrieved {len(rows)} DOB attempt records")

                # Convert to Pydantic models
                attempts = []
                for row in rows:
                    attempt_data = DOBAttemptData(
                        id=row.id,
                        dob_value=row.dob_value,
                        patient_id=row.patient_id,
                        dob_input=row.dob_input,
                        attempt_num=row.attempt_num,
                        input_type=row.input_type,
                        classification=row.classification,
                    )
                    attempts.append(attempt_data)

                return attempts

            except Exception as e:
                logger.error(f"Failed to fetch DOB attempts: {e}")
                raise

    async def get_data_stats(self, params: DOBDataQueryParams) -> DOBPipelineStats:
        """
        Get statistics about available DOB data without fetching full records.

        Useful for planning and monitoring data extraction.

        Args:
            params: Query parameters for the date range

        Returns:
            Statistics about the data that would be retrieved
        """
        params.validate_date_range()

        # Simplified query to get statistics
        stats_query = """
        WITH dob_attempts AS (
          SELECT
            v.caller_responses,
            jsonb_array_elements(v.caller_responses -> 'dob' -> 'attempts') AS attempt
          FROM voice v
          WHERE v.caller_responses ? 'dob'
            AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(v.caller_responses -> 'dob' -> 'attempts') a
              WHERE a ->> 'input' ~ '[A-Za-z]'
            )
            AND call_start_time >= :start_date
            AND call_end_time <= :end_date
            AND (v.caller_responses -> 'patient' ->> 'id') IS NULL
        )
        SELECT
          COUNT(*) as total_records,
          COUNT(CASE WHEN (caller_responses -> 'dob' ->> 'value') IS NOT NULL THEN 1 END) as with_existing_dob,
          COUNT(CASE WHEN (caller_responses -> 'dob' ->> 'value') IS NULL THEN 1 END) as failed_conversion,
          COUNT(CASE WHEN attempt ->> 'input' ~ '[A-Za-z]' THEN 1 END) as spoken_attempts,
          COUNT(CASE WHEN attempt ->> 'input' ~ '^[0-9]+$' THEN 1 END) as dtmf_attempts
        FROM dob_attempts
        """

        async with self.session() as session:
            try:
                result = await session.execute(
                    text(stats_query),
                    {
                        "start_date": params.start_date,
                        "end_date": params.end_date,
                    },
                )

                row = result.fetchone()

                if row:
                    return DOBPipelineStats(
                        total_records_processed=row.total_records,
                        records_with_existing_dob=row.with_existing_dob,
                        records_failed_conversion=row.failed_conversion,
                        spoken_attempts=row.spoken_attempts,
                        dtmf_attempts=row.dtmf_attempts,
                        query_start_date=params.start_date,
                        query_end_date=params.end_date,
                    )
                else:
                    # No data found
                    return DOBPipelineStats(
                        total_records_processed=0,
                        records_with_existing_dob=0,
                        records_failed_conversion=0,
                        spoken_attempts=0,
                        dtmf_attempts=0,
                        query_start_date=params.start_date,
                        query_end_date=params.end_date,
                    )

            except Exception as e:
                logger.error(f"Failed to get data statistics: {e}")
                raise

    async def health_check(self) -> dict:
        """
        Perform health check on external database connection.

        Returns:
            Dictionary with health status information
        """
        if not self._connected:
            return {"status": "disconnected", "database": "external_caller_data", "connected": False}

        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
                return {"status": "healthy", "database": "external_caller_data", "connected": True}
        except Exception as e:
            logger.error(f"External database health check failed: {e}")
            return {"status": "unhealthy", "database": "external_caller_data", "connected": False, "error": str(e)}


# Global instance for dependency injection
dob_data_fetcher = DOBDataFetcher()
