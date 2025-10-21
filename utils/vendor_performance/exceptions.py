"""
Custom Exceptions for Vendor Performance Module

Provides clear, specific exception types for better error handling.
"""

class VendorPerformanceError(Exception):
    """Base exception for vendor performance module"""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class DataAccessError(VendorPerformanceError):
    """Raised when database query or data loading fails"""
    pass


class CalculationError(VendorPerformanceError):
    """Raised when calculation logic fails"""
    pass


class ValidationError(VendorPerformanceError):
    """Raised when data validation fails"""
    pass


class ExportError(VendorPerformanceError):
    """Raised when data export fails"""
    pass


class ConfigurationError(VendorPerformanceError):
    """Raised when configuration is invalid"""
    pass


# Helper function for error logging
def log_and_raise(logger, exception_class, message: str, details: dict = None, exc_info=None):
    """
    Log error and raise exception
    
    Args:
        logger: Logger instance
        exception_class: Exception class to raise
        message: Error message
        details: Additional error details
        exc_info: Exception info for traceback
    """
    full_message = message
    if details:
        full_message = f"{message} | Details: {details}"
    
    logger.error(full_message, exc_info=exc_info)
    raise exception_class(message, details)