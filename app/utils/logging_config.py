import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request_id if available
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        # Add any extra fields from the record
        if hasattr(record, "extras"):
            log_obj.update(record.extras)

        # Add error information if present
        if record.exc_info:
            log_obj["error"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_obj)


def setup_logging(
    log_level: str = "INFO", log_file: Optional[Path] = None, max_size_mb: int = 10, backup_count: int = 5
) -> None:
    """Configure application-wide logging with JSON formatting"""
    log_dir = Path(__file__).parent.parent.parent / "logs"
    if log_file is None:
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "app.log"

    # Configure root logger
    root_logger = logging.getLogger()

    # Clear any existing handlers
    root_logger.handlers.clear()

    root_logger.setLevel(getattr(logging, log_level.upper()))

    # JSON formatter for structured logging
    json_formatter = JsonFormatter()

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)

    # File handler with JSON formatting
    file_handler = RotatingFileHandler(
        filename=log_file, maxBytes=max_size_mb * 1024 * 1024, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info("Logging configured", extra={"log_file": str(log_file)})
    logger.info(f"log_dir: {log_dir}")


def check_logging_handlers():
    """Diagnostic function to check logger configuration"""
    loggers = [
        ("root", logging.getLogger()),
        ("app", logging.getLogger("app")),
        ("app.utils", logging.getLogger("app.utils")),
        ("app.main", logging.getLogger("app.main")),
    ]

    for name, logger in loggers:
        print(f"\nLogger: {name}")
        print(f"Handlers: {len(logger.handlers)}")
        for h in logger.handlers:
            print(f"  - {type(h).__name__}")
