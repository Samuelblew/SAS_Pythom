class AppError(Exception):
    def __init__(self, status: int, title: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, detail: str):
        super().__init__(404, "Não encontrado", detail)


class ConflictError(AppError):
    def __init__(self, detail: str):
        super().__init__(409, "Conflito", detail)


class ValidationAppError(AppError):
    def __init__(self, detail: str):
        super().__init__(400, "Erro de validação", detail)
