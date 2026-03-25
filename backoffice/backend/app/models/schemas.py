from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.models import (
    AlertType, ContractStatus, EmailPriority, TransactionType,
)


# --- Auth ---

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str

    class Config:
        from_attributes = True


# --- Client ---

class ClientCreate(BaseModel):
    name: str
    cnpj: str
    email: str | None = None
    phone: str | None = None


class ClientOut(BaseModel):
    id: int
    name: str
    cnpj: str
    email: str | None
    phone: str | None
    is_active: bool

    class Config:
        from_attributes = True


# --- Employee ---

class EmployeeCreate(BaseModel):
    client_id: int
    name: str
    cpf: str
    role_title: str | None = None
    department: str | None = None
    hire_date: date
    salary: Decimal
    carga_horaria_semanal: int = 44
    vale_transporte: bool = True
    vale_refeicao: Decimal = Decimal("0")
    plano_saude: bool = False


class EmployeeOut(BaseModel):
    id: int
    client_id: int
    name: str
    cpf: str
    role_title: str | None
    department: str | None
    hire_date: date
    salary: Decimal
    is_active: bool
    carga_horaria_semanal: int
    vale_transporte: bool
    vale_refeicao: Decimal
    plano_saude: bool

    class Config:
        from_attributes = True


# --- Payroll ---

class PayrollRecordOut(BaseModel):
    id: int
    employee_id: int
    reference_month: date
    gross_salary: Decimal
    inss_deduction: Decimal
    irrf_deduction: Decimal
    fgts_amount: Decimal
    net_salary: Decimal
    overtime_hours: Decimal
    overtime_amount: Decimal
    payment_date: date | None
    notes: str | None

    class Config:
        from_attributes = True


# --- Contract ---

class ContractCreate(BaseModel):
    client_id: int
    title: str
    description: str | None = None
    contract_number: str | None = None
    value: Decimal | None = None
    start_date: date
    end_date: date
    auto_renew: bool = False


class ContractOut(BaseModel):
    id: int
    client_id: int
    title: str
    description: str | None
    contract_number: str | None
    value: Decimal | None
    start_date: date
    end_date: date
    status: ContractStatus
    auto_renew: bool
    client_name: str | None = None

    class Config:
        from_attributes = True


# --- Email ---

class EmailRecordOut(BaseModel):
    id: int
    client_id: int | None
    sender: str
    subject: str
    body_preview: str | None
    received_at: datetime
    priority: EmailPriority
    category: str | None
    is_read: bool
    is_actionable: bool
    action_summary: str | None
    client_name: str | None = None

    class Config:
        from_attributes = True


# --- Transaction ---

class TransactionCreate(BaseModel):
    client_id: int | None = None
    type: TransactionType
    category: str
    description: str | None = None
    amount: Decimal
    transaction_date: date
    is_recurring: bool = False
    recurrence_months: int | None = None


class TransactionOut(BaseModel):
    id: int
    client_id: int | None
    type: TransactionType
    category: str
    description: str | None
    amount: Decimal
    transaction_date: date
    is_recurring: bool

    class Config:
        from_attributes = True


# --- Alert ---

class AlertOut(BaseModel):
    id: int
    type: AlertType
    title: str
    message: str
    severity: str
    is_read: bool
    reference_id: int | None
    reference_type: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Agent ---

class AgentRunOut(BaseModel):
    id: int
    agent_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    result_summary: str | None
    items_processed: int
    issues_found: int

    class Config:
        from_attributes = True


class AgentTriggerRequest(BaseModel):
    agent_name: str
    params: dict | None = None


# --- Dashboard ---

class DashboardSummary(BaseModel):
    total_clients: int
    active_contracts: int
    contracts_expiring_soon: int
    total_employees: int
    pending_alerts: int
    unread_emails: int
    monthly_revenue: Decimal
    monthly_expenses: Decimal
    cash_flow_balance: Decimal


class CashFlowProjection(BaseModel):
    month: str
    projected_revenue: Decimal
    projected_expenses: Decimal
    balance: Decimal


class PayrollAuditResult(BaseModel):
    employee_name: str
    employee_cpf: str
    issue_type: str
    description: str
    severity: str
    reference_month: str
