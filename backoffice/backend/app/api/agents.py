from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.redis import invalidate_cache
from app.agents.payroll_audit import run_payroll_audit
from app.agents.contract_tracker import run_contract_tracker
from app.agents.email_triage import run_email_triage
from app.agents.cashflow_projection import run_cashflow_projection
from app.agents.salary_alerts import run_salary_alerts
from app.models.models import AgentRun, User
from app.models.schemas import AgentRunOut, AgentTriggerRequest

router = APIRouter(prefix="/agents", tags=["agents"])

AGENT_REGISTRY = {
    "payroll_audit": {
        "name": "Auditoria de Folha (CLT)",
        "description": "Verifica conformidade da folha de pagamento com a legislação trabalhista brasileira",
        "runner": run_payroll_audit,
    },
    "contract_tracker": {
        "name": "Rastreamento de Contratos",
        "description": "Monitora vencimento de contratos e atualiza status automaticamente",
        "runner": run_contract_tracker,
    },
    "email_triage": {
        "name": "Triagem de E-mails",
        "description": "Classifica e-mails por cliente, prioridade e categoria",
        "runner": run_email_triage,
    },
    "cashflow_projection": {
        "name": "Projeção de Fluxo de Caixa",
        "description": "Projeta receitas e despesas futuras com base em dados históricos",
        "runner": run_cashflow_projection,
    },
    "salary_alerts": {
        "name": "Alertas de Pagamento",
        "description": "Monitora prazos de pagamento e suficiência de caixa para folha",
        "runner": run_salary_alerts,
    },
}


@router.get("/available")
def list_agents(_user: User = Depends(get_current_user)):
    return [
        {"key": key, "name": info["name"], "description": info["description"]}
        for key, info in AGENT_REGISTRY.items()
    ]


@router.post("/run")
def trigger_agent(
    request: AgentTriggerRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if request.agent_name not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agente '{request.agent_name}' não encontrado")

    agent_info = AGENT_REGISTRY[request.agent_name]
    runner = agent_info["runner"]

    params = request.params or {}
    if request.agent_name == "payroll_audit" and "reference_month" in params:
        params["reference_month"] = date.fromisoformat(params["reference_month"])

    if request.agent_name == "cashflow_projection" and "months_ahead" in params:
        result = runner(db, months_ahead=int(params["months_ahead"]))
    elif request.agent_name == "payroll_audit" and "reference_month" in params:
        result = runner(db, reference_month=params["reference_month"])
    else:
        result = runner(db)

    # Invalidate dashboard cache after agent run
    invalidate_cache("dashboard")

    return result


@router.get("/history", response_model=list[AgentRunOut])
def agent_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    runs = (
        db.query(AgentRun)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [AgentRunOut.model_validate(r) for r in runs]
