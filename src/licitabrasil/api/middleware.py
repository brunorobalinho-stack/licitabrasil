import logging
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("licitabrasil")
_TEMPLATES_DIR = str(Path(__file__).resolve().parent / "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code == 404 and not request.url.path.startswith("/static"):
                return self._error(request, 404, "Pagina nao encontrada")
            return response
        except Exception:
            log.exception("Erro interno em %s %s", request.method, request.url.path)
            return self._error(request, 500, "Erro interno do servidor")

    def _error(self, request: Request, status: int, message: str):
        if is_htmx(request):
            return HTMLResponse(
                f'<p class="text-center text-red-500 py-8">{message}</p>',
                status_code=status,
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"status": status, "message": message},
            status_code=status,
        )
