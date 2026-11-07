"""Business-rule errors. Routes turn them into HTTP responses; tools turn them into messages for the AI."""


class ServiceError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = 404
    code = "not_found"


class InvalidInputError(ServiceError):
    status_code = 422
    code = "invalid_input"


class SlotUnavailableError(ServiceError):
    status_code = 409
    code = "slot_unavailable"


class ConfirmationRequiredError(ServiceError):
    status_code = 400
    code = "confirmation_required"


class ForbiddenError(ServiceError):
    status_code = 403
    code = "forbidden"
