# app/utils/logger.py
import logging
from typing import Any, Mapping, MutableMapping, Optional, Tuple

from app.core.context import request_id_ctx_var


def _check_logger_handlers(name: str) -> None:
    """Debug helper to inspect and flush handlers (safe no-op if none)."""
    logger = logging.getLogger(name)
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:
            pass


class RequestIdAdapter(logging.LoggerAdapter):
    """Injects request_id from context var into log `extra`."""

    def __init__(self, logger: logging.Logger, extra: Optional[Mapping[str, Any]] = None) -> None:
        super().__init__(logger, dict(extra or {}))

    # Match the base class signature exactly for mypy
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> Tuple[Any, MutableMapping[str, Any]]:
        rid = request_id_ctx_var.get(None)
        extra: dict[str, Any] = dict(kwargs.get("extra", {}))  # make a copy we can mutate
        if rid is not None:
            extra["request_id"] = rid
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> RequestIdAdapter:
    """
    Return a logger adapter that carries request_id from context.
    Usage:
        logger = get_logger(__name__)
        logger.info("hello")
    """
    base = logging.getLogger(name)
    return RequestIdAdapter(base)
