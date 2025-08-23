import logging
from app.core.context import request_id_ctx_var

def get_logger(name: str) -> logging.Logger:
    """Get a logger that automatically includes request_id in extra"""
    logger = logging.getLogger(name)
    
    # Wrap the logger's methods to automatically include request_id
    def wrap_log(func):
        def wrapped(msg: str, *args, **kwargs):
            extras = kwargs.get('extra', {})
            request_id = request_id_ctx_var.get(None)
            if request_id:
                extras['request_id'] = request_id
            kwargs['extra'] = extras
            return func(msg, *args, **kwargs)
        return wrapped
    
    logger.info = wrap_log(logger.info)
    logger.error = wrap_log(logger.error)
    logger.warning = wrap_log(logger.warning)
    logger.debug = wrap_log(logger.debug)
    
    return logger