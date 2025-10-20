"""
Tests for DOB Pipeline Service
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.dob_pipeline import DOBDataQueryParams, DOBPipelineStats
from app.services.dob_data_fetcher import DOBDataFetcher
from app.services.dob_pipeline_service import DOBPipelineService


class TestDOBDataFetcher:
    """Test cases for DOBDataFetcher service."""

    @pytest.fixture
    def fetcher(self):
        """Create a DOBDataFetcher instance."""
        return DOBDataFetcher()

    @pytest.fixture
    def sample_params(self):
        """Create sample query parameters."""
        return DOBDataQueryParams(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31), max_records=100)

    @patch("app.services.dob_data_fetcher.get_settings")
    @patch("app.services.dob_data_fetcher.create_async_engine")
    @patch("app.services.dob_data_fetcher.async_sessionmaker")
    async def test_connect_success(self, mock_sessionmaker, mock_engine, mock_get_settings, fetcher):
        """Test successful connection to external database."""
        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.caller_source_data = "postgresql://test:test@localhost/test"
        mock_get_settings.return_value = mock_settings

        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance

        # Mock session maker to return a context manager
        mock_session_instance = AsyncMock()
        mock_session_manager = AsyncMock()
        mock_session_manager.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_manager.__aexit__ = AsyncMock(return_value=None)
        mock_sessionmaker.return_value = MagicMock(return_value=mock_session_manager)

        # Mock successful connection test
        mock_session_instance.execute.return_value = MagicMock()

        # Test connection
        await fetcher.connect()

        assert fetcher._connected is True
        assert fetcher._engine == mock_engine_instance
        mock_engine.assert_called_once()
        mock_sessionmaker.assert_called_once()

    @patch("app.services.dob_data_fetcher.settings")
    async def test_connect_no_env_var(self, mock_settings, fetcher):
        """Test connection failure when CALLER_SOURCE_DATA is not set."""
        mock_settings.caller_source_data = None

        with pytest.raises(ValueError, match="CALLER_SOURCE_DATA environment variable must be set"):
            await fetcher.connect()

    def test_validate_date_range_valid(self, sample_params):
        """Test date range validation with valid dates."""
        # Should not raise any exception
        sample_params.validate_date_range()

    def test_validate_date_range_invalid(self):
        """Test date range validation with invalid dates."""
        params = DOBDataQueryParams(
            start_date=date(2024, 1, 31),
            end_date=date(2024, 1, 1),  # End before start
        )

        with pytest.raises(ValueError, match="start_date must be before or equal to end_date"):
            params.validate_date_range()


class TestDOBPipelineService:
    """Test cases for DOBPipelineService."""

    @pytest.fixture
    def pipeline_service(self):
        """Create a DOBPipelineService instance."""
        return DOBPipelineService()

    @pytest.fixture
    def sample_params(self):
        """Create sample query parameters."""
        return DOBDataQueryParams(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

    @patch("app.services.dob_pipeline_service.get_db_session")
    async def test_run_pipeline_success(self, mock_get_db_session, pipeline_service, sample_params):
        """Test successful pipeline execution."""
        # Setup mocks
        mock_db_session = MagicMock()
        # Make async methods actually async
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        mock_db_session.close = AsyncMock()
        mock_db_session.add = MagicMock()

        mock_get_db_session.return_value = mock_db_session

        # Mock the data fetcher instance on the pipeline service
        mock_fetcher = MagicMock()
        mock_fetcher.connect = AsyncMock()
        mock_fetcher.disconnect = AsyncMock()
        mock_fetcher.get_data_stats = AsyncMock(
            return_value=DOBPipelineStats(
                total_records_processed=50,
                records_with_existing_dob=30,
                records_failed_conversion=20,
                spoken_attempts=40,
                dtmf_attempts=10,
                query_start_date=sample_params.start_date,
                query_end_date=sample_params.end_date,
            )
        )
        mock_fetcher.fetch_dob_attempts = AsyncMock(return_value=[])
        pipeline_service.data_fetcher = mock_fetcher

        # Run pipeline
        result = await pipeline_service.run_pipeline(sample_params)

        # Verify results
        assert isinstance(result, DOBPipelineStats)
        assert result.total_records_processed == 0  # No data processed in this test
        assert result.query_start_date == sample_params.start_date
        assert result.query_end_date == sample_params.end_date

        # Verify calls
        mock_fetcher.connect.assert_called_once()
        mock_fetcher.disconnect.assert_called_once()
        mock_fetcher.get_data_stats.assert_called_once_with(sample_params)

    @patch("app.services.dob_pipeline_service.get_db_session")
    async def test_health_check_success(self, mock_get_db_session, pipeline_service):
        """Test successful health check."""
        # Setup mocks
        mock_db_session = AsyncMock()
        mock_get_db_session.return_value = mock_db_session

        with patch.object(
            pipeline_service.data_fetcher,
            "health_check",
            return_value={"status": "healthy", "database": "external_caller_data", "connected": True},
        ):
            result = await pipeline_service.health_check()

            assert result["pipeline"] == "dob_training"
            assert result["external_db"]["status"] == "healthy"
            assert result["local_db"]["status"] == "healthy"
            assert result["overall_status"] == "healthy"

    @patch("app.services.dob_pipeline_service.get_db_session")
    async def test_health_check_external_down(self, mock_get_db_session, pipeline_service):
        """Test health check when external database is down."""
        # Setup mocks
        mock_db_session = AsyncMock()
        mock_get_db_session.return_value = mock_db_session

        with patch.object(
            pipeline_service.data_fetcher,
            "health_check",
            return_value={"status": "unhealthy", "database": "external_caller_data", "connected": False},
        ):
            result = await pipeline_service.health_check()

            assert result["overall_status"] == "degraded"


class TestDOBParserValidation:
    """Test DOB parser validation functionality for Milestone 1.2."""

    @pytest.mark.asyncio
    async def test_validation_match_type_enum_values(self):
        """Test that ValidationMatchType enum has expected values."""
        from app.models.dob_pipeline import ValidationMatchType

        assert ValidationMatchType.EXACT_MATCH == "exact_match"
        assert ValidationMatchType.PARTIAL_MATCH == "partial_match"
        assert ValidationMatchType.NO_MATCH == "no_match"
        assert ValidationMatchType.PARSER_FAILURE == "parser_failure"
        assert ValidationMatchType.SOURCE_FAILURE == "source_failure"
        assert ValidationMatchType.IMPROVEMENT_OPPORTUNITY == "improvement_opportunity"

    def test_dob_validation_result_model_creation(self):
        """Test DOBValidationResult model creation and validation."""
        from datetime import date

        from app.models.dob_pipeline import DOBValidationResult, ValidationMatchType

        result = DOBValidationResult(
            record_hash="abc123",
            dob_input="january first nineteen eighty five",
            existing_dob=date(1985, 1, 1),
            parser_result=date(1985, 1, 1),
            match_type=ValidationMatchType.EXACT_MATCH,
            processing_time_ms=150.5,
            parser_confidence=0.95,
            input_type="spoken",
            classification="clean",
            attempt_number=1,
        )

        assert result.record_hash == "abc123"
        assert result.dob_input == "january first nineteen eighty five"
        assert result.existing_dob == date(1985, 1, 1)
        assert result.parser_result == date(1985, 1, 1)
        assert result.match_type == ValidationMatchType.EXACT_MATCH
        assert result.processing_time_ms == 150.5
        assert result.parser_confidence == 0.95
        assert result.input_type == "spoken"
        assert result.classification == "clean"
        assert result.attempt_number == 1
        assert result.error_message is None

    def test_dob_validation_result_with_error(self):
        """Test DOBValidationResult model with error message."""
        from datetime import date

        from app.models.dob_pipeline import DOBValidationResult, ValidationMatchType

        result = DOBValidationResult(
            record_hash="def456",
            dob_input="invalid input",
            existing_dob=date(1990, 5, 15),
            parser_result=None,
            match_type=ValidationMatchType.PARSER_FAILURE,
            processing_time_ms=50.0,
            parser_confidence=None,
            error_message="Failed to parse date",
            input_type="spoken",
            classification="failure",
            attempt_number=2,
        )

        assert result.record_hash == "def456"
        assert result.parser_result is None
        assert result.match_type == ValidationMatchType.PARSER_FAILURE
        assert result.parser_confidence is None
        assert result.error_message == "Failed to parse date"

    def test_dob_validation_summary_model_creation(self):
        """Test DOBValidationSummary model creation and validation."""
        from datetime import datetime

        from app.models.dob_pipeline import DOBValidationSummary

        summary = DOBValidationSummary(
            total_records=1000,
            processed=100,
            exact_matches=80,
            partial_matches=5,
            no_matches=10,
            parser_failures=3,
            source_failures=2,
            improvement_opportunities=0,
            average_processing_time_ms=120.5,
            total_processing_time_ms=12050.0,
            exact_match_rate=0.8,
            parser_success_rate=0.97,
            source_success_rate=0.98,
            filters_applied={"input_type": "spoken"},
        )

        assert summary.total_records == 1000
        assert summary.processed == 100
        assert summary.exact_matches == 80
        assert summary.no_matches == 10
        assert summary.parser_failures == 3
        assert summary.source_failures == 2
        assert summary.improvement_opportunities == 0
        assert summary.average_processing_time_ms == 120.5
        assert summary.total_processing_time_ms == 12050.0
        assert summary.exact_match_rate == 0.8
        assert summary.parser_success_rate == 0.97
        assert summary.source_success_rate == 0.98
        assert summary.filters_applied == {"input_type": "spoken"}
        assert isinstance(summary.request_timestamp, datetime)

    def test_dob_validation_detailed_response_model(self):
        """Test DOBValidationDetailedResponse model creation."""
        from datetime import date

        from app.models.dob_pipeline import (
            DOBValidationDetailedResponse,
            DOBValidationResult,
            DOBValidationSummary,
            ValidationMatchType,
        )

        summary = DOBValidationSummary(
            total_records=50,
            processed=10,
            exact_matches=7,
            partial_matches=1,
            no_matches=1,
            parser_failures=1,
            source_failures=0,
            improvement_opportunities=0,
            average_processing_time_ms=100.0,
            total_processing_time_ms=1000.0,
            exact_match_rate=0.7,
            parser_success_rate=0.9,
            source_success_rate=1.0,
        )

        results = [
            DOBValidationResult(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                parser_result=date(2000, 1, 1),
                match_type=ValidationMatchType.EXACT_MATCH,
                processing_time_ms=95.0,
                parser_confidence=0.95,
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            )
        ]

        response = DOBValidationDetailedResponse(
            summary=summary,
            results=results,
            mismatches_only=False,
        )

        assert response.summary == summary
        assert response.results == results
        assert response.mismatches_only is False

    def test_determine_match_type_exact_match(self):
        """Test _determine_match_type returns EXACT_MATCH when both dates match."""
        from datetime import date

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()
        existing_dob = date(1985, 1, 1)
        parser_result = date(1985, 1, 1)

        result = service._determine_match_type(existing_dob, parser_result)
        assert result == ValidationMatchType.EXACT_MATCH

    def test_determine_match_type_no_match(self):
        """Test _determine_match_type returns NO_MATCH when dates differ."""
        from datetime import date

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()
        existing_dob = date(1985, 1, 1)
        parser_result = date(1990, 5, 15)

        result = service._determine_match_type(existing_dob, parser_result)
        assert result == ValidationMatchType.NO_MATCH

    def test_determine_match_type_parser_failure(self):
        """Test _determine_match_type returns PARSER_FAILURE when parser fails but source succeeds."""
        from datetime import date

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()
        existing_dob = date(1985, 1, 1)
        parser_result = None

        result = service._determine_match_type(existing_dob, parser_result)
        assert result == ValidationMatchType.PARSER_FAILURE

    def test_determine_match_type_source_failure(self):
        """Test _determine_match_type returns SOURCE_FAILURE when source fails and parser fails."""
        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()
        existing_dob = None
        parser_result = None

        result = service._determine_match_type(existing_dob, parser_result)
        assert result == ValidationMatchType.SOURCE_FAILURE

    def test_determine_match_type_improvement_opportunity(self):
        """Test _determine_match_type returns IMPROVEMENT_OPPORTUNITY when source fails but parser succeeds."""
        from datetime import date

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()
        existing_dob = None
        parser_result = date(1985, 1, 1)

        result = service._determine_match_type(existing_dob, parser_result)
        assert result == ValidationMatchType.IMPROVEMENT_OPPORTUNITY

    def test_generate_validation_summary_basic(self):
        """Test _generate_validation_summary with basic result set."""
        from datetime import date

        from app.models.dob_pipeline import (
            DOBValidationResult,
            ValidationMatchType,
        )
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        results = [
            DOBValidationResult(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                parser_result=date(2000, 1, 1),
                match_type=ValidationMatchType.EXACT_MATCH,
                processing_time_ms=100.0,
                parser_confidence=0.95,
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            ),
            DOBValidationResult(
                record_hash="hash2",
                dob_input="february second two thousand one",
                existing_dob=date(2001, 2, 2),
                parser_result=date(2001, 2, 3),  # Different day
                match_type=ValidationMatchType.NO_MATCH,
                processing_time_ms=120.0,
                parser_confidence=0.90,
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            ),
        ]

        summary = service._generate_validation_summary(
            results=results,
            total_records=100,
            total_processing_time=220.0,
            limit=10,
            offset=0,
            input_type="spoken",
            classification=None,
        )

        assert summary.total_records == 100
        assert summary.processed == 2
        assert summary.exact_matches == 1
        assert summary.no_matches == 1
        assert summary.partial_matches == 0
        assert summary.parser_failures == 0
        assert summary.source_failures == 0
        assert summary.improvement_opportunities == 0
        assert summary.average_processing_time_ms == 110.0  # 220.0 / 2
        assert summary.total_processing_time_ms == 220.0
        assert summary.exact_match_rate == 0.5  # 1 / 2
        assert summary.parser_success_rate == 1.0  # 2 / 2
        assert summary.source_success_rate == 1.0  # 2 / 2
        assert summary.filters_applied == {"input_type": "spoken"}

    def test_generate_validation_summary_with_failures(self):
        """Test _generate_validation_summary with parser and source failures."""
        from datetime import date

        from app.models.dob_pipeline import (
            DOBValidationResult,
            ValidationMatchType,
        )
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        results = [
            DOBValidationResult(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                parser_result=None,
                match_type=ValidationMatchType.PARSER_FAILURE,
                processing_time_ms=50.0,
                parser_confidence=None,
                input_type="spoken",
                classification="failure",
                attempt_number=1,
            ),
            DOBValidationResult(
                record_hash="hash2",
                dob_input="invalid input",
                existing_dob=None,
                parser_result=None,
                match_type=ValidationMatchType.SOURCE_FAILURE,
                processing_time_ms=30.0,
                parser_confidence=None,
                input_type="spoken",
                classification="failure",
                attempt_number=1,
            ),
            DOBValidationResult(
                record_hash="hash3",
                dob_input="march third two thousand two",
                existing_dob=None,
                parser_result=date(2002, 3, 3),
                match_type=ValidationMatchType.IMPROVEMENT_OPPORTUNITY,
                processing_time_ms=80.0,
                parser_confidence=0.85,
                input_type="spoken",
                classification="failure",
                attempt_number=1,
            ),
        ]

        summary = service._generate_validation_summary(
            results=results,
            total_records=50,
            total_processing_time=160.0,
            limit=20,
            offset=5,
            input_type=None,
            classification="failure",
        )

        assert summary.total_records == 50
        assert summary.processed == 3
        assert summary.exact_matches == 0
        assert summary.no_matches == 0
        assert summary.partial_matches == 0
        assert summary.parser_failures == 1
        assert summary.source_failures == 1
        assert summary.improvement_opportunities == 1
        assert summary.average_processing_time_ms == 160.0 / 3  # ~53.33
        assert summary.total_processing_time_ms == 160.0
        assert summary.exact_match_rate == 0.0
        assert summary.parser_success_rate == 2.0 / 3  # ~0.667
        assert summary.source_success_rate == 2.0 / 3  # Records 1 and 3 have source results
        assert summary.filters_applied == {"classification": "failure"}

    @pytest.mark.asyncio
    async def test_validate_parser_batch_success(self):
        """Test validate_parser_batch with successful validation."""
        from datetime import date
        from unittest.mock import AsyncMock, MagicMock

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        # Mock database records
        mock_records = [
            MagicMock(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            ),
            MagicMock(
                record_hash="hash2",
                dob_input="february second two thousand one",
                existing_dob=date(2001, 2, 2),
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            ),
        ]

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_records
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value.total = 100
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.close = AsyncMock()

        # Mock get_db_session
        with patch("app.services.dob_pipeline_service.get_db_session", return_value=mock_session):
            # Mock parse_spoken_date
            with patch("app.services.dob_parser.parse_spoken_date") as mock_parse:
                mock_parse.side_effect = [
                    {"year": 2000, "month": 1, "day": 1},  # Exact match
                    {"year": 2001, "month": 2, "day": 3},  # No match (different day)
                ]

                results, summary = await service.validate_parser_batch(limit=10, offset=0)

                assert len(results) == 2
                assert results[0].match_type == ValidationMatchType.EXACT_MATCH
                assert results[1].match_type == ValidationMatchType.NO_MATCH
                assert summary.total_records == 100
                assert summary.processed == 2
                assert summary.exact_matches == 1
                assert summary.no_matches == 1

    @pytest.mark.asyncio
    async def test_validate_parser_batch_with_parser_failure(self):
        """Test validate_parser_batch when parser fails."""
        from datetime import date
        from unittest.mock import AsyncMock, MagicMock

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        # Mock database record
        mock_records = [
            MagicMock(
                record_hash="hash1",
                dob_input="invalid input",
                existing_dob=date(2000, 1, 1),
                input_type="spoken",
                classification="failure",
                attempt_number=1,
            ),
        ]

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_records
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value.total = 50
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.close = AsyncMock()

        # Mock get_db_session
        with patch("app.services.dob_pipeline_service.get_db_session", return_value=mock_session):
            # Mock parse_spoken_date to raise exception
            with patch("app.services.dob_parser.parse_spoken_date") as mock_parse:
                mock_parse.side_effect = ValueError("Invalid date format")

                results, summary = await service.validate_parser_batch(limit=5, offset=0)

                assert len(results) == 1
                assert results[0].match_type == ValidationMatchType.PARSER_FAILURE
                assert results[0].error_message == "Invalid date format"
                assert summary.parser_failures == 1

    @pytest.mark.asyncio
    async def test_validate_parser_batch_with_filters(self):
        """Test validate_parser_batch with input type and classification filters."""
        from datetime import date
        from unittest.mock import AsyncMock, MagicMock

        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        # Mock database record
        mock_records = [
            MagicMock(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                input_type="dtmf",
                classification="clean",
                attempt_number=1,
            ),
        ]

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_records
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value.total = 25
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_count_result])
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.close = AsyncMock()

        # Mock get_db_session
        with patch("app.services.dob_pipeline_service.get_db_session", return_value=mock_session):
            # Mock parse_spoken_date
            with patch("app.services.dob_parser.parse_spoken_date") as mock_parse:
                mock_parse.return_value = {"year": 2000, "month": 1, "day": 1}

                results, summary = await service.validate_parser_batch(
                    limit=10, offset=0, input_type="dtmf", classification="clean"
                )

                assert len(results) == 1
                assert summary.filters_applied == {"input_type": "dtmf", "classification": "clean"}

    @pytest.mark.asyncio
    async def test_validate_single_record_success(self):
        """Test validate_single_record with successful validation."""
        from datetime import date
        from unittest.mock import AsyncMock, MagicMock

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        # Mock database record
        mock_record = MagicMock(
            record_hash="test_hash",
            dob_input="january first two thousand",
            existing_dob=date(2000, 1, 1),
            input_type="spoken",
            classification="clean",
            attempt_number=1,
        )

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_record
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        # Mock get_db_session
        with patch("app.services.dob_pipeline_service.get_db_session", return_value=mock_session):
            # Mock parse_spoken_date
            with patch("app.services.dob_parser.parse_spoken_date") as mock_parse:
                mock_parse.return_value = {"year": 2000, "month": 1, "day": 1}

                result = await service.validate_single_record("test_hash")

                assert result.record_hash == "test_hash"
                assert result.match_type == ValidationMatchType.EXACT_MATCH
                assert result.parser_result == date(2000, 1, 1)
                assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_validate_single_record_parser_failure(self):
        """Test validate_single_record when parser fails."""
        from datetime import date
        from unittest.mock import AsyncMock, MagicMock

        from app.models.dob_pipeline import ValidationMatchType
        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        # Mock database record
        mock_record = MagicMock(
            record_hash="test_hash",
            dob_input="invalid input",
            existing_dob=date(2000, 1, 1),
            input_type="spoken",
            classification="failure",
            attempt_number=1,
        )

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_record
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        # Mock get_db_session
        with patch("app.services.dob_pipeline_service.get_db_session", return_value=mock_session):
            # Mock parse_spoken_date to raise exception
            with patch("app.services.dob_parser.parse_spoken_date") as mock_parse:
                mock_parse.side_effect = ValueError("Invalid date")

                result = await service.validate_single_record("test_hash")

                assert result.match_type == ValidationMatchType.PARSER_FAILURE
                assert result.error_message == "Invalid date"
                assert result.parser_result is None

    @pytest.mark.asyncio
    async def test_validate_single_record_not_found(self):
        """Test validate_single_record when record is not found."""
        from unittest.mock import AsyncMock, MagicMock

        from fastapi import HTTPException

        from app.services.dob_pipeline_service import DOBPipelineService

        service = DOBPipelineService()

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # No record found
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        # Mock get_db_session
        with patch("app.services.dob_pipeline_service.get_db_session", return_value=mock_session):
            with pytest.raises(HTTPException) as exc_info:
                await service.validate_single_record("nonexistent_hash")

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_validate_parser_batch_endpoint_summary_only(self):
        """Test validate_parser_batch endpoint returning summary only."""
        from unittest.mock import AsyncMock

        from app.models.dob_pipeline import DOBValidationSummary
        from app.routers.dob_pipeline_router import validate_parser_batch

        # Mock service response
        mock_results = []
        mock_summary = DOBValidationSummary(
            total_records=100,
            processed=10,
            exact_matches=8,
            partial_matches=0,
            no_matches=1,
            parser_failures=1,
            source_failures=0,
            improvement_opportunities=0,
            average_processing_time_ms=100.0,
            total_processing_time_ms=1000.0,
            exact_match_rate=0.8,
            parser_success_rate=0.9,
            source_success_rate=1.0,
        )

        with patch("app.routers.dob_pipeline_router.dob_pipeline_service") as mock_service:
            mock_service.validate_parser_batch = AsyncMock(return_value=(mock_results, mock_summary))

            response = await validate_parser_batch(
                limit=10, offset=0, input_type=None, classification=None, include_details=False, mismatches_only=False
            )

            assert isinstance(response, DOBValidationSummary)
            assert response.total_records == 100
            assert response.processed == 10

    @pytest.mark.asyncio
    async def test_validate_parser_batch_endpoint_with_details(self):
        """Test validate_parser_batch endpoint returning detailed response."""
        from datetime import date
        from unittest.mock import AsyncMock

        from app.models.dob_pipeline import (
            DOBValidationDetailedResponse,
            DOBValidationResult,
            DOBValidationSummary,
            ValidationMatchType,
        )
        from app.routers.dob_pipeline_router import validate_parser_batch

        # Mock service response
        mock_results = [
            DOBValidationResult(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                parser_result=date(2000, 1, 1),
                match_type=ValidationMatchType.EXACT_MATCH,
                processing_time_ms=95.0,
                parser_confidence=0.95,
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            )
        ]
        mock_summary = DOBValidationSummary(
            total_records=50,
            processed=1,
            exact_matches=1,
            partial_matches=0,
            no_matches=0,
            parser_failures=0,
            source_failures=0,
            improvement_opportunities=0,
            average_processing_time_ms=95.0,
            total_processing_time_ms=95.0,
            exact_match_rate=1.0,
            parser_success_rate=1.0,
            source_success_rate=1.0,
        )

        with patch("app.routers.dob_pipeline_router.dob_pipeline_service") as mock_service:
            mock_service.validate_parser_batch = AsyncMock(return_value=(mock_results, mock_summary))

            response = await validate_parser_batch(
                limit=10, offset=0, input_type=None, classification=None, include_details=True, mismatches_only=False
            )

            assert isinstance(response, DOBValidationDetailedResponse)
            assert len(response.results) == 1
            assert response.mismatches_only is False

    @pytest.mark.asyncio
    async def test_validate_parser_batch_endpoint_mismatches_only(self):
        """Test validate_parser_batch endpoint with mismatches_only filter."""
        from datetime import date
        from unittest.mock import AsyncMock

        from app.models.dob_pipeline import (
            DOBValidationDetailedResponse,
            DOBValidationResult,
            DOBValidationSummary,
            ValidationMatchType,
        )
        from app.routers.dob_pipeline_router import validate_parser_batch

        # Mock service response with mixed results
        mock_results = [
            DOBValidationResult(
                record_hash="hash1",
                dob_input="january first two thousand",
                existing_dob=date(2000, 1, 1),
                parser_result=date(2000, 1, 1),
                match_type=ValidationMatchType.EXACT_MATCH,
                processing_time_ms=95.0,
                parser_confidence=0.95,
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            ),
            DOBValidationResult(
                record_hash="hash2",
                dob_input="february second two thousand one",
                existing_dob=date(2001, 2, 2),
                parser_result=date(2001, 2, 3),
                match_type=ValidationMatchType.NO_MATCH,
                processing_time_ms=100.0,
                parser_confidence=0.90,
                input_type="spoken",
                classification="clean",
                attempt_number=1,
            ),
        ]
        mock_summary = DOBValidationSummary(
            total_records=50,
            processed=2,
            exact_matches=1,
            partial_matches=0,
            no_matches=1,
            parser_failures=0,
            source_failures=0,
            improvement_opportunities=0,
            average_processing_time_ms=97.5,
            total_processing_time_ms=195.0,
            exact_match_rate=0.5,
            parser_success_rate=1.0,
            source_success_rate=1.0,
        )

        with patch("app.routers.dob_pipeline_router.dob_pipeline_service") as mock_service:
            mock_service.validate_parser_batch = AsyncMock(return_value=(mock_results, mock_summary))

            response = await validate_parser_batch(
                limit=10, offset=0, input_type=None, classification=None, include_details=True, mismatches_only=True
            )

            assert isinstance(response, DOBValidationDetailedResponse)
            # Should only include the NO_MATCH result
            assert len(response.results) == 1
            assert response.results[0].match_type == ValidationMatchType.NO_MATCH
            assert response.mismatches_only is True

    @pytest.mark.asyncio
    async def test_validate_single_record_endpoint_success(self):
        """Test validate_single_record endpoint success."""
        from datetime import date
        from unittest.mock import AsyncMock

        from app.models.dob_pipeline import DOBValidationResult, ValidationMatchType
        from app.routers.dob_pipeline_router import validate_single_record

        mock_result = DOBValidationResult(
            record_hash="test_hash",
            dob_input="january first two thousand",
            existing_dob=date(2000, 1, 1),
            parser_result=date(2000, 1, 1),
            match_type=ValidationMatchType.EXACT_MATCH,
            processing_time_ms=95.0,
            parser_confidence=0.95,
            input_type="spoken",
            classification="clean",
            attempt_number=1,
        )

        with patch("app.routers.dob_pipeline_router.dob_pipeline_service") as mock_service:
            mock_service.validate_single_record = AsyncMock(return_value=mock_result)

            response = await validate_single_record("test_hash")

            assert isinstance(response, DOBValidationResult)
            assert response.record_hash == "test_hash"
            assert response.match_type == ValidationMatchType.EXACT_MATCH
