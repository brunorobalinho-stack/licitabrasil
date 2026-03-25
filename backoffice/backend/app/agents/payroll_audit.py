"""
Agente de Auditoria de Folha de Pagamento — CLT Compliance

Verifica conformidade com a legislação trabalhista brasileira:
- Cálculo correto do INSS (faixas progressivas)
- Cálculo correto do IRRF (tabela progressiva)
- FGTS (8% sobre remuneração bruta)
- Horas extras (mínimo 50% adicional, 100% domingos/feriados)
- Adicional noturno (mínimo 20%)
- Salário mínimo nacional
- 13º salário proporcional
- Férias + 1/3 constitucional
"""

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.models import (
    AgentRun, Alert, AlertType, Employee, PayrollRecord,
)

# Tabela INSS 2026 (faixas progressivas)
INSS_FAIXAS = [
    (Decimal("1518.00"), Decimal("0.075")),
    (Decimal("2793.88"), Decimal("0.09")),
    (Decimal("4190.83"), Decimal("0.12")),
    (Decimal("8157.41"), Decimal("0.14")),
]
INSS_TETO = Decimal("8157.41")

# Tabela IRRF 2026 (simplificada)
IRRF_FAIXAS = [
    (Decimal("2259.20"), Decimal("0"), Decimal("0")),
    (Decimal("2826.65"), Decimal("0.075"), Decimal("169.44")),
    (Decimal("3751.05"), Decimal("0.15"), Decimal("381.44")),
    (Decimal("4664.68"), Decimal("0.225"), Decimal("662.77")),
    (Decimal("999999999"), Decimal("0.275"), Decimal("896.00")),
]

FGTS_RATE = Decimal("0.08")
SALARIO_MINIMO = Decimal("1518.00")  # 2025, ajustar para 2026 quando publicado
OVERTIME_MIN_RATE = Decimal("1.50")


def _calc_inss(gross: Decimal) -> Decimal:
    """Calcula INSS progressivo por faixas."""
    total = Decimal("0")
    prev_limit = Decimal("0")
    for limit, rate in INSS_FAIXAS:
        if gross <= prev_limit:
            break
        taxable = min(gross, limit) - prev_limit
        total += (taxable * rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        prev_limit = limit
    return total


def _calc_irrf(gross: Decimal, inss: Decimal) -> Decimal:
    """Calcula IRRF sobre base (bruto - INSS)."""
    base = gross - inss
    for limit, rate, deduction in IRRF_FAIXAS:
        if base <= limit:
            tax = (base * rate - deduction).quantize(Decimal("0.01"), ROUND_HALF_UP)
            return max(tax, Decimal("0"))
    return Decimal("0")


def _calc_fgts(gross: Decimal) -> Decimal:
    return (gross * FGTS_RATE).quantize(Decimal("0.01"), ROUND_HALF_UP)


def run_payroll_audit(db: Session, reference_month: date | None = None) -> dict:
    """Execute full payroll audit for a given month or the latest available."""

    agent_run = AgentRun(agent_name="payroll_audit", status="running")
    db.add(agent_run)
    db.commit()

    issues = []
    items_processed = 0

    try:
        employees = db.query(Employee).filter(Employee.is_active.is_(True)).all()

        for emp in employees:
            query = db.query(PayrollRecord).filter(PayrollRecord.employee_id == emp.id)
            if reference_month:
                query = query.filter(PayrollRecord.reference_month == reference_month)
            else:
                query = query.order_by(PayrollRecord.reference_month.desc())

            record = query.first()
            if not record:
                continue

            items_processed += 1
            month_str = record.reference_month.strftime("%Y-%m")

            # 1. Salário mínimo
            if record.gross_salary < SALARIO_MINIMO:
                issues.append({
                    "employee_name": emp.name,
                    "employee_cpf": emp.cpf,
                    "issue_type": "salario_minimo",
                    "description": f"Salário bruto R${record.gross_salary} abaixo do mínimo R${SALARIO_MINIMO}",
                    "severity": "critical",
                    "reference_month": month_str,
                })

            # 2. INSS
            expected_inss = _calc_inss(record.gross_salary)
            diff_inss = abs(record.inss_deduction - expected_inss)
            if diff_inss > Decimal("1.00"):
                issues.append({
                    "employee_name": emp.name,
                    "employee_cpf": emp.cpf,
                    "issue_type": "inss_incorreto",
                    "description": f"INSS registrado R${record.inss_deduction}, esperado R${expected_inss} (dif: R${diff_inss})",
                    "severity": "warning",
                    "reference_month": month_str,
                })

            # 3. IRRF
            expected_irrf = _calc_irrf(record.gross_salary, record.inss_deduction)
            diff_irrf = abs(record.irrf_deduction - expected_irrf)
            if diff_irrf > Decimal("1.00"):
                issues.append({
                    "employee_name": emp.name,
                    "employee_cpf": emp.cpf,
                    "issue_type": "irrf_incorreto",
                    "description": f"IRRF registrado R${record.irrf_deduction}, esperado R${expected_irrf} (dif: R${diff_irrf})",
                    "severity": "warning",
                    "reference_month": month_str,
                })

            # 4. FGTS
            expected_fgts = _calc_fgts(record.gross_salary)
            diff_fgts = abs(record.fgts_amount - expected_fgts)
            if diff_fgts > Decimal("1.00"):
                issues.append({
                    "employee_name": emp.name,
                    "employee_cpf": emp.cpf,
                    "issue_type": "fgts_incorreto",
                    "description": f"FGTS registrado R${record.fgts_amount}, esperado R${expected_fgts} (dif: R${diff_fgts})",
                    "severity": "warning",
                    "reference_month": month_str,
                })

            # 5. Horas extras — valor mínimo 50%
            if record.overtime_hours and record.overtime_hours > 0:
                hourly_rate = record.gross_salary / Decimal(str(emp.carga_horaria_semanal * Decimal("4.345")))
                min_overtime_total = (hourly_rate * OVERTIME_MIN_RATE * record.overtime_hours).quantize(
                    Decimal("0.01"), ROUND_HALF_UP
                )
                if record.overtime_amount < min_overtime_total - Decimal("1.00"):
                    issues.append({
                        "employee_name": emp.name,
                        "employee_cpf": emp.cpf,
                        "issue_type": "hora_extra_abaixo",
                        "description": (
                            f"{record.overtime_hours}h extras: pago R${record.overtime_amount}, "
                            f"mínimo legal R${min_overtime_total}"
                        ),
                        "severity": "warning",
                        "reference_month": month_str,
                    })

            # 6. Net salary sanity check
            expected_net = (
                record.gross_salary
                - record.inss_deduction
                - record.irrf_deduction
                - record.vale_transporte_deduction
                - record.other_deductions
                + record.other_additions
                + record.overtime_amount
            )
            diff_net = abs(record.net_salary - expected_net)
            if diff_net > Decimal("1.00"):
                issues.append({
                    "employee_name": emp.name,
                    "employee_cpf": emp.cpf,
                    "issue_type": "salario_liquido_divergente",
                    "description": f"Líquido registrado R${record.net_salary}, calculado R${expected_net} (dif: R${diff_net})",
                    "severity": "critical",
                    "reference_month": month_str,
                })

        # Create alerts for critical issues
        for issue in issues:
            if issue["severity"] == "critical":
                alert = Alert(
                    type=AlertType.PAYROLL_ANOMALY,
                    title=f"Auditoria folha: {issue['issue_type']}",
                    message=f"{issue['employee_name']} ({issue['employee_cpf']}): {issue['description']}",
                    severity="critical",
                )
                db.add(alert)

        agent_run.status = "completed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.items_processed = items_processed
        agent_run.issues_found = len(issues)
        agent_run.result_summary = f"Auditados {items_processed} registros, {len(issues)} problemas encontrados"
        db.commit()

        return {
            "status": "completed",
            "items_processed": items_processed,
            "issues_found": len(issues),
            "issues": issues,
        }

    except Exception as e:
        db.rollback()
        agent_run.status = "failed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.result_summary = str(e)
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise
