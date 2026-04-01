"""Utilitários de retry para requisições HTTP."""

import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import httpx

# Tenacity usa logging stdlib para before_sleep_log; criamos um logger compatível
_stdlib_logger = logging.getLogger(__name__)

# Retry padrão para requisições HTTP: 3 tentativas, backoff exponencial 1-10s
retry_http = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
    ),
    before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
    reraise=True,
)
