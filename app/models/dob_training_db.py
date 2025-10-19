"""
DOB Pipeline Database Models

SQLAlchemy models for local storage of DOB training data with hash-based
de-identification to ensure privacy compliance.
"""

import hashlib
from datetime import date
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .modelbase import Base


class DOBTrainingData(Base):
    """
    Local storage model for DOB training data.

    Stores processed DOB attempts with hash-based de-identification for privacy.
    No direct linkage to external patient data is maintained.
    """

    __tablename__ = "dob_training_data"

    # Primary key - hash-based for de-identification
    record_hash: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="SHA-256 hash of external voice.id for de-identification"
    )

    # DOB processing data
    dob_input: Mapped[str] = mapped_column(Text, nullable=False, comment="Normalized spoken word input text from caller")
    existing_dob: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="Existing system DOB conversion result (NULL if failed)"
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Attempt sequence number for this DOB extraction"
    )

    # Classification data
    input_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="Input type: 'spoken' or 'dtmf'")
    classification: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Processing classification: 'multiple_attempts', 'spoken_candidate', 'failure', 'clean'",
    )

    # Metadata
    processed_at: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(), comment="Date when this record was processed and stored"
    )
    source_table: Mapped[str] = mapped_column(
        String(50), nullable=False, default="voice", comment="Source table name for audit trail"
    )
    extraction_query_version: Mapped[str] = mapped_column(
        String(10), nullable=False, default="1.0", comment="Version of extraction query/logic used"
    )

    # Audit timestamps
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Record creation timestamp"
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )

    @classmethod
    def generate_record_hash(cls, external_id: int, attempt_num: int) -> str:
        """
        Generate a SHA-256 hash for de-identification.

        Combines external ID and attempt number to create unique but
        non-reversible identifiers.

        Args:
            external_id: External voice table primary key
            attempt_num: Attempt number for this DOB extraction

        Returns:
            SHA-256 hash string for use as primary key
        """
        hash_input = f"{external_id}:{attempt_num}:dob_training"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            f"<DOBTrainingData("
            f"record_hash={self.record_hash[:8]}..., "
            f"input_type={self.input_type}, "
            f"classification={self.classification}, "
            f"processed_at={self.processed_at}"
            f")>"
        )


class DOBPipelineRun(Base):
    """
    Audit log for DOB pipeline processing runs.

    Tracks when and how data was processed for monitoring and debugging.
    """

    __tablename__ = "dob_pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Query parameters used
    query_start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Start date of the data extraction query")
    query_end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="End date of the data extraction query")

    # Processing statistics
    total_records_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Total records retrieved from external source"
    )
    records_with_existing_dob: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Records with successful existing system conversion"
    )
    records_failed_conversion: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Records where existing system failed to convert"
    )
    spoken_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Records with spoken word input (alphabetic characters)"
    )
    dtmf_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Records with DTMF input (numeric only)"
    )

    # Performance metrics
    processing_duration_seconds: Mapped[float] = mapped_column(
        Integer, nullable=False, default=0, comment="Total time taken to process this batch"
    )

    # Metadata
    extraction_query_version: Mapped[str] = mapped_column(
        String(10), nullable=False, default="1.0", comment="Version of extraction query used"
    )
    success: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=True, comment="Whether the pipeline run completed successfully"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Error message if pipeline run failed")

    # Audit timestamps
    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), comment="When the pipeline run started"
    )
    completed_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the pipeline run completed"
    )

    def mark_completed(self, success: bool = True, error_message: Optional[str] = None) -> None:
        """Mark the pipeline run as completed."""
        from datetime import datetime

        self.completed_at = datetime.now()
        self.success = success
        if error_message:
            self.error_message = error_message

    def __repr__(self) -> str:
        return (
            f"<DOBPipelineRun("
            f"id={self.id}, "
            f"start_date={self.query_start_date}, "
            f"end_date={self.query_end_date}, "
            f"records={self.total_records_processed}, "
            f"success={self.success}"
            f")>"
        )
