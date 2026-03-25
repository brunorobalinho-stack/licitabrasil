from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# --- Enums ---

class ContractStatus(str, PyEnum):
    ATIVO = "ativo"
    VENCIDO = "vencido"
    PROXIMO_VENCIMENTO = "proximo_vencimento"
    CANCELADO = "cancelado"


class EmailPriority(str, PyEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class AlertType(str, PyEnum):
    SALARY_PAYOUT = "salary_payout"
    CONTRACT_EXPIRY = "contract_expiry"
    PAYROLL_ANOMALY = "payroll_anomaly"
    CASH_FLOW_WARNING = "cash_flow_warning"


class TransactionType(str, PyEnum):
    RECEITA = "receita"
    DESPESA = "despesa"


# --- Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="analyst")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    cnpj = Column(String(18), unique=True, index=True)
    email = Column(String(255))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    contracts = relationship("Contract", back_populates="client")
    employees = relationship("Employee", back_populates="client")
    emails = relationship("EmailRecord", back_populates="client")
    transactions = relationship("Transaction", back_populates="client")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    cpf = Column(String(14), unique=True, index=True)
    role_title = Column(String(255))
    department = Column(String(100))
    hire_date = Column(Date, nullable=False)
    salary = Column(Numeric(12, 2), nullable=False)
    is_active = Column(Boolean, default=True)

    # CLT fields
    carga_horaria_semanal = Column(Integer, default=44)
    vale_transporte = Column(Boolean, default=True)
    vale_refeicao = Column(Numeric(10, 2), default=0)
    plano_saude = Column(Boolean, default=False)
    fgts_deposited = Column(Boolean, default=True)

    client = relationship("Client", back_populates="employees")
    payroll_records = relationship("PayrollRecord", back_populates="employee")


class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    reference_month = Column(Date, nullable=False)  # first day of month
    gross_salary = Column(Numeric(12, 2), nullable=False)
    inss_deduction = Column(Numeric(10, 2), nullable=False)
    irrf_deduction = Column(Numeric(10, 2), nullable=False)
    fgts_amount = Column(Numeric(10, 2), nullable=False)
    vale_transporte_deduction = Column(Numeric(10, 2), default=0)
    other_deductions = Column(Numeric(10, 2), default=0)
    other_additions = Column(Numeric(10, 2), default=0)
    net_salary = Column(Numeric(12, 2), nullable=False)
    overtime_hours = Column(Numeric(6, 2), default=0)
    overtime_amount = Column(Numeric(10, 2), default=0)
    payment_date = Column(Date)
    notes = Column(Text)

    employee = relationship("Employee", back_populates="payroll_records")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    contract_number = Column(String(100), unique=True)
    value = Column(Numeric(14, 2))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(Enum(ContractStatus), default=ContractStatus.ATIVO)
    auto_renew = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    client = relationship("Client", back_populates="contracts")


class EmailRecord(Base):
    __tablename__ = "email_records"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    sender = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body_preview = Column(Text)
    received_at = Column(DateTime, nullable=False)
    priority = Column(Enum(EmailPriority), default=EmailPriority.MEDIA)
    category = Column(String(100))  # auto-classified
    is_read = Column(Boolean, default=False)
    is_actionable = Column(Boolean, default=False)
    action_summary = Column(Text)

    client = relationship("Client", back_populates="emails")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    type = Column(Enum(TransactionType), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(String(500))
    amount = Column(Numeric(14, 2), nullable=False)
    transaction_date = Column("date", Date, nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_months = Column(Integer)

    client = relationship("Client", back_populates="transactions")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(AlertType), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="info")  # info, warning, critical
    is_read = Column(Boolean, default=False)
    reference_id = Column(Integer)  # generic FK to related record
    reference_type = Column(String(50))  # "employee", "contract", etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(20), default="running")  # running, completed, failed
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime)
    result_summary = Column(Text)
    items_processed = Column(Integer, default=0)
    issues_found = Column(Integer, default=0)
