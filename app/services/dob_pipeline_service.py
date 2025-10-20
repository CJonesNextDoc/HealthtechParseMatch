"""
DOB Pipeline Service

Orchestrates the complete DOB training data pipeline: fetching from external
source, processing with privacy safeguards, and storing in local database.
"""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.db import get_db_session
from app.models.dob_pipeline import (
    DOBAttemptData,
    DOBDataQueryParams,
    DOBPipelineRunResponse,
    DOBPipelineStats,
    DOBTrainingRecord,
    DOBValidationResult,
    DOBValidationSummary,
    ValidationMatchType,
)
from app.models.dob_training_db import DOBPipelineRun, DOBTrainingData
from app.services.dob_data_fetcher import dob_data_fetcher
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DOBPipelineService:
    """
    Service for orchestrating the complete DOB training data pipeline.

    Fetches data from external source, applies privacy transformations,
    and stores processed records in local database for training.
    """

    def __init__(self):
        self.data_fetcher = dob_data_fetcher

    async def run_pipeline(self, params: DOBDataQueryParams, batch_size: int = 1000) -> DOBPipelineStats:
        """
        Execute the complete DOB training data pipeline.

        Args:
            params: Query parameters for data extraction
            batch_size: Number of records to process in each batch

        Returns:
            Statistics about the pipeline run
        """
        start_time = datetime.now()
        logger.info(f"Starting DOB pipeline run for date range: {params.start_date} to {params.end_date}")

        # Initialize pipeline run tracking
        pipeline_run = DOBPipelineRun(
            query_start_date=params.start_date,
            query_end_date=params.end_date,
            total_records_processed=0,
            records_with_existing_dob=0,
            records_failed_conversion=0,
            spoken_attempts=0,
            dtmf_attempts=0,
            processing_duration_seconds=0,
            success=True,
        )

        db_session = await get_db_session()
        try:
            # Save initial pipeline run record
            db_session.add(pipeline_run)
            await db_session.commit()
            await db_session.refresh(pipeline_run)

            # Connect to external database
            await self.data_fetcher.connect()

            # Get data statistics first
            stats = await self.data_fetcher.get_data_stats(params)
            logger.info(f"Found {stats.total_records_processed} DOB records to process")

            # Process data in batches
            total_processed = 0
            batch_num = 0

            while True:
                # Create batch parameters
                batch_params = DOBDataQueryParams(
                    start_date=params.start_date, end_date=params.end_date, max_records=batch_size
                )

                # Fetch batch from external source
                attempts = await self.data_fetcher.fetch_dob_attempts(batch_params)

                if not attempts:
                    break  # No more data

                batch_num += 1
                logger.info(f"Processing batch {batch_num} with {len(attempts)} records")

                # Process and store batch
                batch_stats = await self._process_batch(db_session, attempts)
                total_processed += batch_stats.total_records_processed

                # Update pipeline run progress
                pipeline_run.total_records_processed = total_processed
                await db_session.commit()

                # If we got fewer records than batch size, we're done
                if len(attempts) < batch_size:
                    break

            # Update final statistics
            end_time = datetime.now()
            processing_duration = (end_time - start_time).total_seconds()

            final_stats = DOBPipelineStats(
                total_records_processed=total_processed,
                records_with_existing_dob=stats.records_with_existing_dob,
                records_failed_conversion=stats.records_failed_conversion,
                spoken_attempts=stats.spoken_attempts,
                dtmf_attempts=stats.dtmf_attempts,
                processing_duration_seconds=processing_duration,
                query_start_date=params.start_date,  # Added this
                query_end_date=params.end_date,  # Added this
            )

            # Update pipeline run record
            pipeline_run.completed_at = end_time  # type: ignore[assignment]
            pipeline_run.success = True
            pipeline_run.total_records_processed = total_processed
            pipeline_run.processing_duration_seconds = processing_duration

            await db_session.commit()

            logger.info(
                f"DOB pipeline completed successfully. Processed {total_processed} " f"records in {processing_duration:.2f}s"
            )
            return final_stats

        except Exception as e:
            # Update pipeline run with error status
            pipeline_run.success = False
            pipeline_run.error_message = str(e)
            pipeline_run.completed_at = datetime.now()  # type: ignore[assignment]
            await db_session.commit()

            logger.error(f"DOB pipeline failed: {e}")
            raise

        finally:
            # Always disconnect from external database
            try:
                await self.data_fetcher.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting from external database: {e}")
            # Close the database session
            await db_session.close()

    async def _process_batch(self, db_session: AsyncSession, attempts: List[DOBAttemptData]) -> DOBPipelineStats:
        """
        Process a batch of DOB attempts and store in local database.

        Args:
            db_session: Local database session
            attempts: List of DOB attempt data from external source

        Returns:
            Statistics for this batch
        """
        training_records = []
        stats = DOBPipelineStats(
            query_start_date=None,  # Will be set in run_pipeline
            query_end_date=None,  # Will be set in run_pipeline
        )

        for attempt in attempts:
            # Create de-identified training record
            record_hash = DOBTrainingData.generate_record_hash(attempt.id, attempt.attempt_num)

            training_record = DOBTrainingData(
                record_hash=record_hash,
                dob_input=attempt.dob_input,
                existing_dob=attempt.dob_value,
                attempt_number=attempt.attempt_num,
                input_type=attempt.input_type,
                classification=attempt.classification,
                processed_at=datetime.now().date(),
                source_table="voice",
                extraction_query_version="1.0",
            )

            training_records.append(training_record)

            # Update statistics
            stats.total_records_processed += 1
            if attempt.dob_value:
                stats.records_with_existing_dob += 1
            else:
                stats.records_failed_conversion += 1

            if attempt.input_type == "spoken":
                stats.spoken_attempts += 1
            else:
                stats.dtmf_attempts += 1

        # Check for existing records to avoid duplicates
        existing_hashes = set()
        if training_records:
            from sqlalchemy import select

            hash_list = [record.record_hash for record in training_records]
            stmt = select(DOBTrainingData.record_hash).where(DOBTrainingData.record_hash.in_(hash_list))
            result = await db_session.execute(stmt)
            existing_hashes = {row.record_hash for row in result.fetchall()}

        # Filter out records that already exist
        new_records = [record for record in training_records if record.record_hash not in existing_hashes]

        # Bulk insert only new training records
        if new_records:
            db_session.add_all(new_records)
            await db_session.commit()
            logger.info(f"Stored {len(new_records)} new training records in local database")
        else:
            logger.info("No new training records to store (all already exist)")

        # Stats already reflect all records processed in the loop above
        return stats

    async def get_recent_runs(self, limit: int = 10) -> List[DOBPipelineRunResponse]:
        """
        Get recent pipeline run history.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of recent pipeline runs
        """
        db_session = await get_db_session()
        try:
            sql_text = f"SELECT * FROM dob_pipeline_runs ORDER BY started_at DESC LIMIT {limit}"
            result = await db_session.execute(text(sql_text))
            runs = result.fetchall()

            return [
                DOBPipelineRunResponse(
                    id=row.id,
                    run_start_time=row.started_at,
                    run_end_time=row.completed_at,
                    query_start_date=row.query_start_date,
                    query_end_date=row.query_end_date,
                    records_processed=row.total_records_processed,
                    status="completed" if row.success else "failed",
                    processing_duration_seconds=row.processing_duration_seconds,
                    error_message=row.error_message,
                )
                for row in runs
            ]
        finally:
            await db_session.close()

    async def get_training_data_sample(self, limit: int = 100) -> List[DOBTrainingRecord]:
        """
        Get a sample of training data for inspection.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of training data records
        """
        db_session = await get_db_session()
        try:
            sql_text = f"SELECT * FROM dob_training_data ORDER BY processed_at DESC LIMIT {limit}"
            result = await db_session.execute(text(sql_text))
            records = result.fetchall()

            return [
                DOBTrainingRecord(
                    record_hash=row.record_hash,
                    dob_input=row.dob_input,
                    existing_dob=row.existing_dob,
                    attempt_number=row.attempt_number,
                    input_type=row.input_type,
                    classification=row.classification,
                    processed_at=row.processed_at,
                    source_table=row.source_table,
                    extraction_query_version=row.extraction_query_version,
                )
                for row in records
            ]
        finally:
            await db_session.close()

    async def health_check(self) -> dict:
        """
        Perform comprehensive health check of the DOB pipeline.

        Returns:
            Dictionary with health status information
        """
        health_status = {
            "pipeline": "dob_training",
            "external_db": await self.data_fetcher.health_check(),
            "local_db": {"status": "unknown", "connected": False},
            "overall_status": "unknown",
        }

        # Check local database connection
        try:
            db_session = await get_db_session()
            try:
                await db_session.execute(text("SELECT 1"))
                health_status["local_db"] = {"status": "healthy", "database": "local_pipeline", "connected": True}
            finally:
                await db_session.close()
        except Exception as e:
            health_status["local_db"] = {
                "status": "unhealthy",
                "database": "local_pipeline",
                "connected": False,
                "error": str(e),
            }

        # Determine overall status
        external_healthy = health_status["external_db"]["status"] == "healthy"
        local_healthy = health_status["local_db"]["status"] == "healthy"

        if external_healthy and local_healthy:
            health_status["overall_status"] = "healthy"
        elif external_healthy or local_healthy:
            health_status["overall_status"] = "degraded"
        else:
            health_status["overall_status"] = "unhealthy"

        return health_status

    async def validate_parser_batch(
        self,
        limit: int = 100,
        offset: int = 0,
        input_type: Optional[str] = None,
        classification: Optional[str] = None,
    ) -> tuple[List[DOBValidationResult], DOBValidationSummary]:
        """
        Validate DOB parser against a batch of training data.

        Args:
            limit: Maximum number of records to validate
            offset: Pagination offset
            input_type: Filter by input type ('spoken', 'dtmf', or None for all)
            classification: Filter by classification (or None for all)

        Returns:
            Tuple of (validation_results, summary_statistics)
        """
        from app.services.dob_parser import parse_spoken_date

        db_session = await get_db_session()
        try:
            # Build query with filters
            query = "SELECT * FROM dob_training_data WHERE 1=1"
            params = {}

            if input_type:
                query += " AND input_type = :input_type"
                params["input_type"] = input_type

            if classification:
                query += " AND classification = :classification"
                params["classification"] = classification

            query += " ORDER BY processed_at DESC LIMIT :limit OFFSET :offset"
            params["limit"] = str(limit)  # Convert to string
            params["offset"] = str(offset)  # Convert to string

            result = await db_session.execute(text(query), params)
            records = result.fetchall()

            # Get total count for summary
            count_query = "SELECT COUNT(*) as total FROM dob_training_data WHERE 1=1"
            count_params = {}
            if input_type:
                count_query += " AND input_type = :input_type"
                count_params["input_type"] = input_type
            if classification:
                count_query += " AND classification = :classification"
                count_params["classification"] = classification

            count_result = await db_session.execute(text(count_query), count_params)
            count_row = count_result.fetchone()
            total_count = count_row.total if count_row else 0  # Added null check

            # Validate each record
            validation_results = []
            total_processing_time = 0.0

            for record in records:
                start_time = datetime.now()

                try:
                    # Run parser on the input
                    parser_dict = parse_spoken_date(record.dob_input)
                    # Convert dict to date object
                    parser_result = None
                    if parser_dict and "year" in parser_dict and "month" in parser_dict and "day" in parser_dict:
                        try:
                            parser_result = date(parser_dict["year"], parser_dict["month"], parser_dict["day"])
                        except ValueError:
                            parser_result = None  # Invalid date
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000  # Convert to ms

                    # Determine match type
                    match_type = self._determine_match_type(record.existing_dob, parser_result)

                    validation_result = DOBValidationResult(
                        record_hash=record.record_hash,
                        dob_input=record.dob_input,
                        existing_dob=record.existing_dob,
                        parser_result=parser_result,
                        match_type=match_type,
                        processing_time_ms=processing_time,
                        parser_confidence=0.95,
                        input_type=record.input_type,
                        classification=record.classification,
                        attempt_number=record.attempt_number,
                        error_message=None,  # Added this
                    )

                except Exception as e:
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000

                    validation_result = DOBValidationResult(
                        record_hash=record.record_hash,
                        dob_input=record.dob_input,
                        existing_dob=record.existing_dob,
                        parser_result=None,
                        match_type=ValidationMatchType.PARSER_FAILURE,
                        processing_time_ms=processing_time,
                        parser_confidence=None,
                        error_message=str(e),
                        input_type=record.input_type,
                        classification=record.classification,
                        attempt_number=record.attempt_number,
                    )

                validation_results.append(validation_result)
                total_processing_time += processing_time

            # Generate summary statistics
            summary = self._generate_validation_summary(
                validation_results, total_count, total_processing_time, limit, offset, input_type, classification
            )

            return validation_results, summary

        finally:
            await db_session.close()

    async def validate_single_record(self, record_hash: str) -> DOBValidationResult:
        """
        Validate a single training record by its hash.

        Args:
            record_hash: SHA-256 hash of the training record

        Returns:
            Validation result for this specific record

        Raises:
            HTTPException: If record not found
        """
        from fastapi import HTTPException

        from app.services.dob_parser import parse_spoken_date

        db_session = await get_db_session()
        try:
            query = "SELECT * FROM dob_training_data WHERE record_hash = :record_hash"
            result = await db_session.execute(text(query), {"record_hash": record_hash})
            record = result.fetchone()

            if not record:
                raise HTTPException(status_code=404, detail="Training record not found")  # Changed from return None

            # Validate the record
            start_time = datetime.now()

            try:
                parser_dict = parse_spoken_date(record.dob_input)
                # Convert dict to date object
                parser_result = None
                if parser_dict and "year" in parser_dict and "month" in parser_dict and "day" in parser_dict:
                    try:
                        parser_result = date(parser_dict["year"], parser_dict["month"], parser_dict["day"])
                    except ValueError:
                        parser_result = None  # Invalid date
                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                match_type = self._determine_match_type(record.existing_dob, parser_result)

                return DOBValidationResult(
                    record_hash=record.record_hash,
                    dob_input=record.dob_input,
                    existing_dob=record.existing_dob,
                    parser_result=parser_result,
                    match_type=match_type,
                    processing_time_ms=processing_time,
                    parser_confidence=0.95,  # Placeholder
                    input_type=record.input_type,
                    classification=record.classification,
                    attempt_number=record.attempt_number,
                    error_message=None,  # Added
                )

            except Exception as e:
                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                return DOBValidationResult(
                    record_hash=record.record_hash,
                    dob_input=record.dob_input,
                    existing_dob=record.existing_dob,
                    parser_result=None,
                    match_type=ValidationMatchType.PARSER_FAILURE,
                    processing_time_ms=processing_time,
                    parser_confidence=None,
                    error_message=str(e),
                    input_type=record.input_type,
                    classification=record.classification,
                    attempt_number=record.attempt_number,
                )

        finally:
            await db_session.close()

    def _determine_match_type(self, existing_dob: Optional[date], parser_result: Optional[date]) -> ValidationMatchType:
        """
        Determine the type of match between existing DOB and parser result.

        Args:
            existing_dob: What the source system produced (can be None)
            parser_result: What our parser produced (can be None)

        Returns:
            Classification of the match type
        """
        # Source system failed
        if existing_dob is None:
            if parser_result is None:
                return ValidationMatchType.SOURCE_FAILURE  # Both failed
            else:
                return ValidationMatchType.IMPROVEMENT_OPPORTUNITY  # Parser succeeded where source failed

        # Source system succeeded
        if parser_result is None:
            return ValidationMatchType.PARSER_FAILURE  # Parser failed but source succeeded

        # Both succeeded - check for exact match
        if existing_dob == parser_result:
            return ValidationMatchType.EXACT_MATCH

        # Check for partial match (same date, different format)
        # This could be enhanced to handle different date representations
        if existing_dob == parser_result:
            return ValidationMatchType.PARTIAL_MATCH

        return ValidationMatchType.NO_MATCH

    def _generate_validation_summary(
        self,
        results: List[DOBValidationResult],
        total_records: int,
        total_processing_time: float,
        limit: int,
        offset: int,
        input_type: Optional[str],
        classification: Optional[str],
    ) -> DOBValidationSummary:
        """
        Generate summary statistics from validation results.

        Args:
            results: List of validation results
            total_records: Total records in the filtered dataset
            total_processing_time: Total processing time in milliseconds
            limit: Query limit used
            offset: Query offset used
            input_type: Input type filter used
            classification: Classification filter used

        Returns:
            Summary statistics
        """
        exact_matches = sum(1 for r in results if r.match_type == ValidationMatchType.EXACT_MATCH)
        partial_matches = sum(1 for r in results if r.match_type == ValidationMatchType.PARTIAL_MATCH)
        no_matches = sum(1 for r in results if r.match_type == ValidationMatchType.NO_MATCH)
        parser_failures = sum(1 for r in results if r.match_type == ValidationMatchType.PARSER_FAILURE)
        source_failures = sum(1 for r in results if r.match_type == ValidationMatchType.SOURCE_FAILURE)
        improvement_opportunities = sum(1 for r in results if r.match_type == ValidationMatchType.IMPROVEMENT_OPPORTUNITY)

        processed = len(results)
        avg_processing_time = total_processing_time / processed if processed > 0 else 0.0

        # Calculate rates
        exact_match_rate = exact_matches / processed if processed > 0 else 0.0
        parser_success_rate = (processed - parser_failures) / processed if processed > 0 else 0.0
        source_success_rate = (processed - source_failures) / processed if processed > 0 else 0.0

        # Build filters dict
        filters = {}
        if input_type:
            filters["input_type"] = input_type
        if classification:
            filters["classification"] = classification

        return DOBValidationSummary(
            total_records=total_records,
            processed=processed,
            exact_matches=exact_matches,
            partial_matches=partial_matches,
            no_matches=no_matches,
            parser_failures=parser_failures,
            source_failures=source_failures,
            improvement_opportunities=improvement_opportunities,
            average_processing_time_ms=avg_processing_time,
            total_processing_time_ms=total_processing_time,
            exact_match_rate=exact_match_rate,
            parser_success_rate=parser_success_rate,
            source_success_rate=source_success_rate,
            filters_applied=filters,
        )


# Global instance for dependency injection
dob_pipeline_service = DOBPipelineService()
