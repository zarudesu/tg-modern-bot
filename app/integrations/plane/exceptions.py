"""
Plane API Exceptions
"""


class PlaneAPIError(Exception):
    """Base exception for Plane API errors"""
    pass


class PlaneAuthError(PlaneAPIError):
    """Authentication error"""
    pass


class PlaneNotFoundError(PlaneAPIError):
    """Resource not found"""
    pass


class PlaneRateLimitError(PlaneAPIError):
    """Rate limit exceeded"""
    pass


class PlaneValidationError(PlaneAPIError):
    """Validation error"""
    pass
