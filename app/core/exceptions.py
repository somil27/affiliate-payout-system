"""Domain-specific exception hierarchy.

Using dedicated exceptions keeps HTTP concerns out of the service layer;
the API middleware maps them to appropriate HTTP responses.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base for all business/domain errors."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class ValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class RateLimitedError(DomainError):
    status_code = 429
    code = "rate_limited"


class InsufficientFundsError(DomainError):
    status_code = 409
    code = "insufficient_funds"


class InvalidStateError(DomainError):
    status_code = 409
    code = "invalid_state"
