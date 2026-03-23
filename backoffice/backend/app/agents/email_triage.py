"""
Agente de Triagem de E-mails por Cliente

Classifica e-mails recebidos:
- Associa ao cliente correto (por domínio de e-mail ou palavras-chave)
- Classifica prioridade (alta/média/baixa)
- Identifica se é acionável e sugere ação
- Categoriza por tema (financeiro, jurídico, operacional, etc.)
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.models import AgentRun, Client, EmailPriority, EmailRecord

# Keywords for priority classification
HIGH_PRIORITY_KEYWORDS = [
    "urgente", "urgent", "imediato", "prazo", "deadline", "multa",
    "notificação", "intimação", "judicial", "embargo", "rescisão",
    "inadimplência", "atraso pagamento", "vencido",
]

ACTIONABLE_KEYWORDS = [
    "favor enviar", "solicito", "por favor", "preciso de",
    "aprovação necessária", "pendente de", "aguardando resposta",
    "confirmar", "assinar", "providenciar",
]

CATEGORY_RULES = {
    "financeiro": ["pagamento", "fatura", "nota fiscal", "nf-e", "boleto", "cobrança", "recibo"],
    "juridico": ["contrato", "aditivo", "cláusula", "jurídico", "advogado", "parecer", "processo"],
    "rh": ["folha", "férias", "rescisão", "admissão", "demissão", "atestado", "benefício"],
    "operacional": ["entrega", "serviço", "cronograma", "relatório", "execução", "obra"],
    "licitacao": ["licitação", "edital", "pregão", "tomada de preço", "concorrência", "ata"],
}


def _classify_priority(subject: str, body: str) -> EmailPriority:
    text = (subject + " " + (body or "")).lower()
    for keyword in HIGH_PRIORITY_KEYWORDS:
        if keyword in text:
            return EmailPriority.ALTA
    return EmailPriority.MEDIA


def _classify_category(subject: str, body: str) -> str:
    text = (subject + " " + (body or "")).lower()
    scores = {}
    for category, keywords in CATEGORY_RULES.items():
        scores[category] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "geral"


def _is_actionable(subject: str, body: str) -> tuple[bool, str | None]:
    text = (subject + " " + (body or "")).lower()
    for keyword in ACTIONABLE_KEYWORDS:
        if keyword in text:
            # Generate brief action summary
            idx = text.index(keyword)
            snippet = text[max(0, idx - 20):idx + len(keyword) + 50].strip()
            return True, f"Ação identificada: '{snippet}...'"
    return False, None


def _match_client(sender_email: str, subject: str, db: Session) -> int | None:
    """Try to match email to a client by sender domain or name in subject."""
    domain = sender_email.split("@")[-1] if "@" in sender_email else ""

    clients = db.query(Client).filter(Client.is_active.is_(True)).all()
    for client in clients:
        # Match by email domain
        if client.email and domain and domain in client.email:
            return client.id
        # Match by client name in subject
        if client.name.lower() in subject.lower():
            return client.id
    return None


def run_email_triage(db: Session) -> dict:
    """Process unclassified emails and assign client, priority, category."""

    agent_run = AgentRun(agent_name="email_triage", status="running")
    db.add(agent_run)
    db.commit()

    items_processed = 0
    issues_found = 0

    try:
        # Get emails without category (unprocessed)
        emails = db.query(EmailRecord).filter(
            EmailRecord.category.is_(None)
        ).all()

        for email in emails:
            items_processed += 1

            # Classify
            email.priority = _classify_priority(email.subject, email.body_preview)
            email.category = _classify_category(email.subject, email.body_preview)
            actionable, action_summary = _is_actionable(email.subject, email.body_preview)
            email.is_actionable = actionable
            email.action_summary = action_summary

            # Match client
            if email.client_id is None:
                email.client_id = _match_client(email.sender, email.subject, db)

            if email.priority == EmailPriority.ALTA:
                issues_found += 1

        agent_run.status = "completed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.items_processed = items_processed
        agent_run.issues_found = issues_found
        agent_run.result_summary = (
            f"Triados {items_processed} e-mails, "
            f"{issues_found} alta prioridade"
        )
        db.commit()

        return {
            "status": "completed",
            "items_processed": items_processed,
            "high_priority": issues_found,
        }

    except Exception as e:
        agent_run.status = "failed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.result_summary = str(e)
        db.commit()
        raise
