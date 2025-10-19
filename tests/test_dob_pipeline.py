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
