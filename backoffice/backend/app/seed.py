"""Seed script to populate the database with sample data for development."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from app.core.auth import hash_password
from app.core.database import SessionLocal, Base, engine
from app.models.models import (
    Client, Contract, ContractStatus,
    EmailRecord, Employee, PayrollRecord,
    Transaction, TransactionType, User,
)


logger = logging.getLogger(__name__)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).first():
            logger.info("Database already seeded, skipping.")
            return

        # --- Users ---
        admin = User(
            email="admin@licitabrasil.com",
            name="Admin Backoffice",
            hashed_password=hash_password("admin123"),
            role="admin",
        )
        analyst = User(
            email="analista@licitabrasil.com",
            name="Ana Silva",
            hashed_password=hash_password("analista123"),
            role="analyst",
        )
        db.add_all([admin, analyst])
        db.flush()

        # --- Clients ---
        clients = [
            Client(name="Construtora Horizonte LTDA", cnpj="12.345.678/0001-90",
                   email="contato@horizonte.com.br", phone="(11) 3456-7890"),
            Client(name="Tech Solutions SA", cnpj="23.456.789/0001-01",
                   email="admin@techsolutions.com.br", phone="(21) 2345-6789"),
            Client(name="Serviços Gerais Brasil ME", cnpj="34.567.890/0001-12",
                   email="sgbrasil@email.com", phone="(31) 4567-8901"),
            Client(name="Prefeitura de Exemplo", cnpj="45.678.901/0001-23",
                   email="licitacao@exemplo.gov.br", phone="(41) 5678-9012"),
        ]
        db.add_all(clients)
        db.flush()

        # --- Employees ---
        employees_data = [
            (clients[0].id, "Carlos Mendes", "111.222.333-44", "Engenheiro Civil", "Obras",
             date(2022, 3, 15), Decimal("8500.00")),
            (clients[0].id, "Maria Oliveira", "222.333.444-55", "Técnica de Segurança", "SST",
             date(2023, 7, 1), Decimal("4200.00")),
            (clients[1].id, "João Santos", "333.444.555-66", "Desenvolvedor Senior", "TI",
             date(2021, 1, 10), Decimal("12000.00")),
            (clients[1].id, "Fernanda Lima", "444.555.666-77", "Analista Financeiro", "Financeiro",
             date(2023, 11, 1), Decimal("5800.00")),
            (clients[2].id, "Roberto Alves", "555.666.777-88", "Auxiliar de Serviços", "Operações",
             date(2024, 2, 1), Decimal("1518.00")),
            (clients[2].id, "Ana Paula Costa", "666.777.888-99", "Supervisora", "Operações",
             date(2022, 6, 1), Decimal("3800.00")),
        ]
        employees = []
        for cid, name, cpf, role, dept, hire, salary in employees_data:
            emp = Employee(
                client_id=cid, name=name, cpf=cpf, role_title=role,
                department=dept, hire_date=hire, salary=salary,
                vale_refeicao=Decimal("600.00"), plano_saude=salary > 3000,
            )
            employees.append(emp)
        db.add_all(employees)
        db.flush()

        # --- Payroll Records (last 3 months) ---
        for emp in employees:
            for month_offset in range(3):
                month = date(2026, 3 - month_offset, 1)
                gross = emp.salary
                inss = min(gross * Decimal("0.11"), Decimal("900.00"))  # slightly off for audit testing
                irrf = max((gross - inss) * Decimal("0.15") - Decimal("381.44"), Decimal("0"))
                fgts = gross * Decimal("0.08")
                net = gross - inss - irrf
                record = PayrollRecord(
                    employee_id=emp.id, reference_month=month,
                    gross_salary=gross, inss_deduction=inss,
                    irrf_deduction=irrf, fgts_amount=fgts,
                    net_salary=net, overtime_hours=Decimal("0"),
                    overtime_amount=Decimal("0"),
                    payment_date=date(2026, 3 - month_offset, 5) if month_offset > 0 else None,
                )
                db.add(record)

        # --- Contracts ---
        contracts = [
            Contract(
                client_id=clients[0].id, title="Obra de Reforma - Escola Municipal",
                contract_number="CT-2025-001", value=Decimal("450000.00"),
                start_date=date(2025, 6, 1), end_date=date(2026, 4, 15),
                status=ContractStatus.PROXIMO_VENCIMENTO,
            ),
            Contract(
                client_id=clients[1].id, title="Manutenção de Sistemas - Portal Gov",
                contract_number="CT-2025-002", value=Decimal("180000.00"),
                start_date=date(2025, 1, 1), end_date=date(2026, 12, 31),
                status=ContractStatus.ATIVO,
            ),
            Contract(
                client_id=clients[2].id, title="Limpeza e Conservação Predial",
                contract_number="CT-2024-015", value=Decimal("96000.00"),
                start_date=date(2024, 7, 1), end_date=date(2026, 3, 20),
                status=ContractStatus.VENCIDO,
            ),
            Contract(
                client_id=clients[3].id, title="Consultoria em Licitações",
                contract_number="CT-2026-001", value=Decimal("72000.00"),
                start_date=date(2026, 1, 1), end_date=date(2026, 6, 30),
                status=ContractStatus.ATIVO,
            ),
        ]
        db.add_all(contracts)

        # --- Email Records ---
        email_records = [
            EmailRecord(
                sender="financeiro@horizonte.com.br",
                subject="URGENTE: Nota fiscal pendente - Medição 3",
                body_preview="Prezados, solicito envio urgente da NF referente à 3ª medição da obra...",
                received_at=datetime(2026, 3, 22, 14, 30, tzinfo=timezone.utc),
                client_id=clients[0].id,
            ),
            EmailRecord(
                sender="juridico@techsolutions.com.br",
                subject="Aditivo contratual - Portal Gov",
                body_preview="Conforme reunião, segue minuta do aditivo para aprovação...",
                received_at=datetime(2026, 3, 22, 10, 15, tzinfo=timezone.utc),
                client_id=clients[1].id,
            ),
            EmailRecord(
                sender="compras@exemplo.gov.br",
                subject="Pregão Eletrônico 045/2026 - Resultado",
                body_preview="Informamos o resultado do pregão eletrônico para aquisição de materiais...",
                received_at=datetime(2026, 3, 21, 16, 0, tzinfo=timezone.utc),
                client_id=clients[3].id,
            ),
            EmailRecord(
                sender="rh@sgbrasil.com",
                subject="Atestados médicos - Março 2026",
                body_preview="Seguem os atestados médicos dos funcionários para o mês de março...",
                received_at=datetime(2026, 3, 20, 9, 0, tzinfo=timezone.utc),
                client_id=clients[2].id,
            ),
            EmailRecord(
                sender="desconhecido@email.com",
                subject="Proposta comercial - Serviços de TI",
                body_preview="Gostaríamos de apresentar nossa proposta para serviços de infraestrutura...",
                received_at=datetime(2026, 3, 19, 11, 0, tzinfo=timezone.utc),
            ),
        ]
        db.add_all(email_records)

        # --- Transactions (6 months of data) ---
        for month_offset in range(6):
            m = date(2026, 3 - month_offset if 3 - month_offset > 0 else 12 + (3 - month_offset),
                     15 if month_offset % 2 == 0 else 20)
            year = 2026 if 3 - month_offset > 0 else 2025
            m = m.replace(year=year)

            db.add_all([
                Transaction(client_id=clients[0].id, type=TransactionType.RECEITA,
                           category="Medição de obra", amount=Decimal("75000.00"), transaction_date=m),
                Transaction(client_id=clients[1].id, type=TransactionType.RECEITA,
                           category="Mensalidade SaaS", amount=Decimal("15000.00"), transaction_date=m,
                           is_recurring=True, recurrence_months=1),
                Transaction(client_id=clients[3].id, type=TransactionType.RECEITA,
                           category="Consultoria", amount=Decimal("12000.00"), transaction_date=m,
                           is_recurring=True, recurrence_months=1),
                Transaction(type=TransactionType.DESPESA, category="Folha de pagamento",
                           amount=Decimal("35816.00"), transaction_date=m.replace(day=5),
                           is_recurring=True, recurrence_months=1),
                Transaction(type=TransactionType.DESPESA, category="Aluguel escritório",
                           amount=Decimal("8500.00"), transaction_date=m.replace(day=1),
                           is_recurring=True, recurrence_months=1),
                Transaction(type=TransactionType.DESPESA, category="Fornecedores",
                           amount=Decimal("22000.00") + Decimal(str(month_offset * 1500)), transaction_date=m),
            ])

        db.commit()
        logger.info("Database seeded successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
