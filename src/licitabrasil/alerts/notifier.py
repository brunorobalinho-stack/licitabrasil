"""Notificador — envia alertas por email, webhook, etc.

TODO: Implementar
- Email via SMTP ou SendGrid
- Webhook genérico
- Slack/Telegram (opcional)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Notifier:
    """Envia notificações de alertas."""

    async def enviar(self, canal: str, destinatario: str, mensagem: str) -> bool:
        """Envia notificação. Retorna True se enviado com sucesso."""
        raise NotImplementedError("Notifier ainda não implementado")
