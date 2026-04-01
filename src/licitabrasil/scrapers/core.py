"""Exceptions base para todos os scrapers LicitaBrasil.

Hierarquia:
    LicitaBrasilError
    ├── PortalIndisponivelError  — Portal retornou 5xx ou timeout
    ├── RateLimitError           — 429 ou limite atingido
    ├── ParseError               — Mudou layout/API do portal
    └── DadosInvalidosError      — Dados não passaram Pydantic
"""


class LicitaBrasilError(Exception):
    """Exceção base do projeto."""


class PortalIndisponivelError(LicitaBrasilError):
    """Portal retornou erro (5xx) ou está fora do ar (timeout)."""

    def __init__(self, portal: str, status_code: int | None = None, message: str = ""):
        """Inicializa exceção de portal indisponível.

        Args:
            portal: Identificador do portal.
            status_code: Código HTTP retornado, se aplicável.
            message: Mensagem adicional de detalhe.
        """
        self.portal = portal
        self.status_code = status_code
        detail = f"Portal {portal} indisponível"
        if status_code:
            detail += f" (HTTP {status_code})"
        if message:
            detail += f": {message}"
        super().__init__(detail)


class RateLimitError(LicitaBrasilError):
    """Limite de requisições atingido (HTTP 429 ou similar)."""

    def __init__(self, portal: str, retry_after: int | None = None):
        """Inicializa exceção de rate limit.

        Args:
            portal: Identificador do portal.
            retry_after: Segundos para aguardar antes de tentar novamente.
        """
        self.portal = portal
        self.retry_after = retry_after
        detail = f"Rate limit atingido para {portal}"
        if retry_after:
            detail += f" — retry após {retry_after}s"
        super().__init__(detail)


class ParseError(LicitaBrasilError):
    """Erro ao parsear resposta do portal (layout mudou?)."""

    def __init__(self, portal: str, message: str = ""):
        """Inicializa exceção de erro de parse.

        Args:
            portal: Identificador do portal.
            message: Descrição do erro encontrado.
        """
        self.portal = portal
        detail = f"Erro de parse em {portal}"
        if message:
            detail += f": {message}"
        super().__init__(detail)


class DadosInvalidosError(LicitaBrasilError):
    """Dados não passaram na validação Pydantic."""

    def __init__(self, portal: str, errors: list[dict] | None = None):
        """Inicializa exceção de dados inválidos.

        Args:
            portal: Identificador do portal.
            errors: Lista de erros de validação Pydantic.
        """
        self.portal = portal
        self.errors = errors or []
        detail = f"Dados inválidos de {portal}"
        if errors:
            detail += f" ({len(errors)} erro(s) de validação)"
        super().__init__(detail)
