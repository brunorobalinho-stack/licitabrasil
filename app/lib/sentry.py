import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration


def init_sentry():
    """Inicializa o Sentry para monitoramento de erros. Requer SENTRY_DSN."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.2 if os.getenv("ENVIRONMENT") == "production" else 1.0,
        integrations=[FastApiIntegration()],
    )
