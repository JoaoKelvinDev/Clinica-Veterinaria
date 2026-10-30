class DomainError(Exception):
    code = "business_rule"


class AuthenticationRequired(DomainError):
    code = "unauthenticated"


class AccessDenied(DomainError):
    code = "forbidden"


class ResourceNotFound(DomainError):
    code = "not_found"


class BusinessConflict(DomainError):
    code = "conflict"


class InvalidData(DomainError):
    code = "invalid_data"


class ServiceUnavailable(DomainError):
    code = "unavailable"
