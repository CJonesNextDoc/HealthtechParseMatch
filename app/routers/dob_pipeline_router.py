"""
DOB Pipeline Router

API endpoints for managing the DOB training data pipeline.
"""

from datetime import date, datetime
from typing import List

from fastapi import APIRouter, HTTPException

from app.models.dob_pipeline import (
    DOBDataQueryParams,
    DOBPipelineRunResponse,
    DOBPipelineStats,
    DOBTrainingRecord,
)
from app.services.dob_pipeline_service import dob_pipeline_service


def parse_flexible_date(date_str: str) -> date:
    """
    Parse date string with flexible formats.

    Supports:
    - ISO format: YYYY-MM-DD
    - US format: MM-DD-YYYY
    - MM/DD/YYYY
    """
    date_str = date_str.strip()

    # Try ISO format first (YYYY-MM-DD)
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        pass

    # Try MM-DD-YYYY format
    try:
        return datetime.strptime(date_str, "%m-%d-%Y").date()
    except ValueError:
        pass

    # Try MM/DD/YYYY format
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        pass

    raise ValueError(f"Unable to parse date: {date_str}. Supported formats: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY")


router = APIRouter(prefix="/dob-pipeline", tags=["DOB Pipeline"])


@router.post("/run", response_model=DOBPipelineStats)
async def run_dob_pipeline(
    start_date: str,
    end_date: str,
    max_records: int = None,
    batch_size: int = 1000,
) -> DOBPipelineStats:
    """
    Execute the DOB training data pipeline.

    Fetches DOB data from external source for the specified date range,
    applies privacy transformations, and stores in local database.

    Args:
        start_date: Start date for data extraction (inclusive). Accepts formats: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY
        end_date: End date for data extraction (inclusive). Accepts formats: YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY
        max_records: Maximum records to process (optional, for testing)
        batch_size: Number of records to process in each batch

    Returns:
        Statistics about the pipeline run
    """
    try:
        # Parse dates with flexible format support
        parsed_start_date = parse_flexible_date(start_date)
        parsed_end_date = parse_flexible_date(end_date)

        params = DOBDataQueryParams(
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            max_records=max_records,
        )

        return await dob_pipeline_service.run_pipeline(params, batch_size)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ConnectionError, OSError) as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed (network issue): {str(e)}")
    except Exception as e:
        # Check if it's a network-related error
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ["connection", "network", "timeout", "resolve", "dns"]):
            raise HTTPException(status_code=503, detail=f"Network connectivity issue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")


@router.get("/history", response_model=List[DOBPipelineRunResponse])
async def get_pipeline_history(limit: int = 10) -> List[DOBPipelineRunResponse]:
    """
    Get recent pipeline run history.

    Args:
        limit: Maximum number of runs to return (default: 10)

    Returns:
        List of recent pipeline runs with their status and statistics
    """
    try:
        return await dob_pipeline_service.get_recent_runs(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve pipeline history: {str(e)}")


@router.get("/training-data", response_model=List[DOBTrainingRecord])
async def get_training_data_sample(limit: int = 100) -> List[DOBTrainingRecord]:
    """
    Get a sample of processed training data for inspection.

    Args:
        limit: Maximum number of records to return (default: 100)

    Returns:
        List of training data records (de-identified)
    """
    try:
        return await dob_pipeline_service.get_training_data_sample(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve training data: {str(e)}")


@router.get("/health")
async def pipeline_health_check() -> dict:
    """
    Perform comprehensive health check of the DOB pipeline.

    Returns:
        Health status of external database, local database, and overall pipeline
    """
    try:
        return await dob_pipeline_service.health_check()
    except Exception as e:
        return {"pipeline": "dob_training", "overall_status": "unhealthy", "error": str(e)}


@router.get("/stats")
async def get_pipeline_stats(
    start_date: date,
    end_date: date,
) -> DOBPipelineStats:
    """
    Get statistics about available DOB data without running the full pipeline.

    Useful for planning pipeline runs and understanding data availability.

    Args:
        start_date: Start date for statistics query
        end_date: End date for statistics query

    Returns:
        Statistics about DOB data in the specified date range
    """
    try:
        # This would require modifying the data fetcher to expose stats without full processing
        # For now, return a placeholder
        return DOBPipelineStats(
            total_records_processed=0,
            records_with_existing_dob=0,
            records_failed_conversion=0,
            spoken_attempts=0,
            dtmf_attempts=0,
            processing_duration_seconds=0.0,
            query_start_date=start_date,
            query_end_date=end_date,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline stats: {str(e)}")
