"""
DOB Pipeline Models

Pydantic models for DOB training data pipeline, ensuring complete data isolation
between DOB, ZIP, and phone data silos for privacy compliance.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DOBAttemptData(BaseModel):
    """
    External source data model for individual DOB attempts from voice table.

    This represents a single row from the parameterized query extracting DOB
    attempts from the voice.caller_responses JSONB field.
    """

    model_config = ConfigDict(from_attributes=True)

    # External source fields (read-only access)
    id: int = Field(..., description="Voice table primary key")
    dob_value: Optional[date] = Field(None, description="Existing system DOB conversion (NULL if failed)")
    patient_id: Optional[str] = Field(None, description="Patient identifier (filtered to NULL for privacy)")
    dob_input: str = Field(..., description="Spoken word input text from caller")
    attempt_num: int = Field(..., description="Attempt number for this DOB extraction")
    input_type: str = Field(..., description="Type of input: 'spoken' or 'dtmf'")
    classification: str = Field(
        ..., description="Classification: 'multiple_attempts', 'spoken_candidate', 'failure', 'clean'"
    )


class DOBTrainingRecord(BaseModel):
    """
    Processed DOB training record for local pipeline storage.

    This model represents the final processed form of DOB data that gets stored
    locally for training and analysis, with hash-based de-identification.
    """

    model_config = ConfigDict(from_attributes=True)

    # De-identified fields for local storage
    record_hash: str = Field(..., description="SHA-256 hash of external ID for de-identification")
    dob_input: str = Field(..., description="Normalized spoken word input text")
    existing_dob: Optional[date] = Field(None, description="Existing system conversion result")
    attempt_number: int = Field(..., description="Attempt sequence number")
    input_type: str = Field(..., description="Input classification: spoken/dtmf")
    classification: str = Field(..., description="Processing classification")
    processed_at: date = Field(default_factory=date.today, description="When this record was processed")

    # Metadata for pipeline tracking
    source_table: str = Field(default="voice", description="Source table name")
    extraction_query_version: str = Field(default="1.0", description="Version of extraction logic")


class DOBDataQueryParams(BaseModel):
    """
    Parameters for DOB data extraction queries.

    Allows flexible date range queries while maintaining data isolation.
    """

    start_date: date = Field(..., description="Start date for call filtering (inclusive)")
    end_date: date = Field(..., description="End date for call filtering (inclusive)")
    max_records: Optional[int] = Field(None, description="Maximum records to retrieve (for testing)")

    def validate_date_range(self) -> None:
        """Validate that start_date is before or equal to end_date."""
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")


class DOBPipelineRunResponse(BaseModel):
    """
    Response model for DOB pipeline run information.

    Used for API responses to avoid exposing internal SQLAlchemy models.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Pipeline run ID")
    run_start_time: datetime = Field(..., description="When the pipeline run started")
    run_end_time: Optional[datetime] = Field(None, description="When the pipeline run ended")
    query_start_date: date = Field(..., description="Start date of data query")
    query_end_date: date = Field(..., description="End date of data query")
    records_processed: Optional[int] = Field(None, description="Number of records processed")
    status: str = Field(..., description="Pipeline run status")
    processing_duration_seconds: Optional[float] = Field(None, description="Processing duration in seconds")
    error_message: Optional[str] = Field(None, description="Error message if run failed")


class DOBPipelineStats(BaseModel):
    """
    Statistics for DOB pipeline processing runs.

    Tracks processing metrics for monitoring and optimization.
    """

    total_records_processed: int = Field(default=0, description="Total records retrieved")
    records_with_existing_dob: int = Field(default=0, description="Records with successful existing conversion")
    records_failed_conversion: int = Field(default=0, description="Records where existing system failed")
    spoken_attempts: int = Field(default=0, description="Records with spoken word input")
    dtmf_attempts: int = Field(default=0, description="Records with DTMF input")
    processing_duration_seconds: float = Field(default=0.0, description="Time taken to process batch")
    query_start_date: Optional[date] = Field(None, description="Start date of query range")
    query_end_date: Optional[date] = Field(None, description="End date of query range")
