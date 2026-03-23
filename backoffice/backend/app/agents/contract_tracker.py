"""
Agente de Rastreamento de Vencimento de Contratos

Monitora contratos e:
- Identifica contratos próximos do vencimento
- Atualiza status automaticamente (ativo → próximo_vencimento → vencido)
- Gera alertas para renovação
- Calcula métricas de portfólio de contratos
"""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import (
    AgentRun, Alert, AlertType, Contract, ContractStatus,
)

settings = get_settings()


def run_contract_tracker(db: Session) -> dict:
    """Scan all contracts and update status / generate alerts."""

    agent_run = AgentRun(agent_name="contract_tracker", status="running")
    db.add(agent_run)
    db.commit()

    today = date.today()
    alert_threshold = settings.CONTRACT_ALERT_DAYS_BEFORE
    items_processed = 0
    issues_found = 0
    status_changes = []

    try:
        contracts = db.query(Contract).filter(
            Contract.status.in_([ContractStatus.ATIVO, ContractStatus.PROXIMO_VENCIMENTO])
        ).all()

        for contract in contracts:
            items_processed += 1
            days_until_expiry = (contract.end_date - today).days

            # Already expired
            if days_until_expiry < 0:
                if contract.status != ContractStatus.VENCIDO:
                    old_status = contract.status
                    contract.status = ContractStatus.VENCIDO
                    status_changes.append({
                        "contract_id": contract.id,
                        "title": contract.title,
                        "old_status": old_status,
                        "new_status": ContractStatus.VENCIDO,
                        "days": days_until_expiry,
                    })
                    issues_found += 1

                    alert = Alert(
                        type=AlertType.CONTRACT_EXPIRY,
                        title=f"Contrato vencido: {contract.title}",
                        message=(
                            f"O contrato '{contract.title}' (nº {contract.contract_number}) "
                            f"venceu em {contract.end_date.strftime('%d/%m/%Y')}. "
                            f"{'Renovação automática configurada.' if contract.auto_renew else 'Ação necessária.'}"
                        ),
                        severity="critical",
                        reference_id=contract.id,
                        reference_type="contract",
                    )
                    db.add(alert)

            # Approaching expiry
            elif days_until_expiry <= alert_threshold:
                if contract.status != ContractStatus.PROXIMO_VENCIMENTO:
                    old_status = contract.status
                    contract.status = ContractStatus.PROXIMO_VENCIMENTO
                    status_changes.append({
                        "contract_id": contract.id,
                        "title": contract.title,
                        "old_status": old_status,
                        "new_status": ContractStatus.PROXIMO_VENCIMENTO,
                        "days": days_until_expiry,
                    })
                    issues_found += 1

                    alert = Alert(
                        type=AlertType.CONTRACT_EXPIRY,
                        title=f"Contrato expira em {days_until_expiry} dias",
                        message=(
                            f"O contrato '{contract.title}' (nº {contract.contract_number}) "
                            f"vence em {contract.end_date.strftime('%d/%m/%Y')} "
                            f"({days_until_expiry} dias restantes). "
                            f"Valor: R${contract.value or 'N/A'}."
                        ),
                        severity="warning",
                        reference_id=contract.id,
                        reference_type="contract",
                    )
                    db.add(alert)

        agent_run.status = "completed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.items_processed = items_processed
        agent_run.issues_found = issues_found
        agent_run.result_summary = (
            f"Verificados {items_processed} contratos, "
            f"{issues_found} alterações de status"
        )
        db.commit()

        return {
            "status": "completed",
            "items_processed": items_processed,
            "issues_found": issues_found,
            "status_changes": status_changes,
        }

    except Exception as e:
        agent_run.status = "failed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.result_summary = str(e)
        db.commit()
        raise
