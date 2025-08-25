import logging
from app.core.context import request_id_ctx_var

def _check_logger_handlers(name: str) -> None:
    """Debug function to check logger configuration"""
    logger = logging.getLogger(name)
    root = logging.getLogger()
    
    print("\n=== Logger Configuration ===")
    print(f"Logger '{name}' handlers: {len(logger.handlers)}")
    for h in logger.handlers:
        print(f"  - {type(h).__name__}")
    
    print(f"Root logger handlers: {len(root.handlers)}")
    for h in root.handlers:
        print(f"  - {type(h).__name__}")
    print("=========================\n")

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
    
    # Only add handlers if none exist
    if not logger.handlers and not logging.getLogger().handlers:
        # ... existing handler setup code ...
        pass
        
    _check_logger_handlers(name)  # Add this line temporarily
    return logger