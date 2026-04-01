"""
Custom Exceptions
"""
from fastapi import HTTPException, status


class PaperClawException(Exception):
    """Base exception for PaperClaw"""
    pass


class ResourceNotFoundError(PaperClawException):
    """Resource not found"""
    pass


class UnauthorizedError(PaperClawException):
    """User not authorized"""
    pass


class InvalidInputError(PaperClawException):
    """Invalid input provided"""
    pass


class DuplicateResourceError(PaperClawException):
    """Resource already exists"""
    pass


# HTTP Exception wrappers
def raise_not_found(detail: str = "Resource not found"):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def raise_bad_request(detail: str = "Bad request"):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def raise_unauthorized(detail: str = "Unauthorized"):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


def raise_forbidden(detail: str = "Forbidden"):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def raise_conflict(detail: str = "Conflict"):
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )
