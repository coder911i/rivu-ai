"""Custom exception types and HTTP error helpers."""

from fastapi import HTTPException, status


class RivuError(Exception):
    """Base exception for Rivu application errors."""
    def __init__(self, message: str, code: str = "rivu_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(RivuError):
    def __init__(self, resource: str, id: str = ""):
        super().__init__(f"{resource} not found: {id}", "not_found")


class AuthorizationError(RivuError):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, "unauthorized")


class ValidationError(RivuError):
    def __init__(self, message: str):
        super().__init__(message, "validation_error")


class ProcessingError(RivuError):
    def __init__(self, message: str):
        super().__init__(message, "processing_error")


class StorageError(RivuError):
    def __init__(self, message: str):
        super().__init__(message, "storage_error")


class AIError(RivuError):
    def __init__(self, message: str):
        super().__init__(message, "ai_error")


# ── HTTP helpers ──────────────────────────────

def http_not_found(resource: str, id: str = "") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"{resource} not found", "id": id, "type": "not_found"},
    )


def http_forbidden(message: str = "Access denied") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"message": message, "type": "forbidden"},
    )


def http_bad_request(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": message, "type": "bad_request"},
    )


def http_conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": message, "type": "conflict"},
    )
