"""Testes para o PropostaGenerator."""

import json
import pytest
from decimal import Decimal

from licitabrasil.generators.proposta import (
    DadosEmpresa,
    DadosLicitacao,
    ItemProposta,
    Modulo1Remuneracao,
    Modulo2Encargos,
    Modulo5Insumos,
    Modulo6CustosIndiretos,
    PlanilhaCustos,
    PropostaGenerator,
)


@pytest.fixture
def generator():
    return PropostaGenerator()


@pytest.fixture
def empresa():
    return DadosEmpresa(
        razao_social="Empresa Teste LTDA",
        cnpj="12.345.678/0001-90",
        endereco="Rua Teste, 123 - Recife/PE",
        telefone="(81) 3333-4444",
        email="contato@teste.com.br",
        representante_legal="Jose da Silva",
        cargo_representante="Socio Administrador",
    )


@pytest.fixture
def licitacao():
    return DadosLicitacao(
        numero="PE-001/2025",
        orgao="Prefeitura do Recife",
        modalidade="PREGAO_ELETRONICO",
        objeto="Contratacao de servicos de limpeza e conservacao",
        data_abertura="15/03/2025",
    )


@pytest.fixture
def itens():
    return [
        ItemProposta(numero=1, descricao="Limpeza predial", unidade="M2", quantidade=Decimal("1000"), valor_unitario=Decimal("5.50")),
        ItemProposta(numero=2, descricao="Conservacao de jardim", unidade="M2", quantidade=Decimal("500"), valor_unitario=Decimal("3.00")),
    ]


class TestItemProposta:
    def test_valor_total(self):
        item = ItemProposta(numero=1, descricao="Teste", quantidade=Decimal("10"), valor_unitario=Decimal("100"))
        assert item.valor_total == Decimal("1000")

    def test_valor_total_padrao(self):
        item = ItemProposta(numero=1, descricao="Teste")
        assert item.valor_total == Decimal("0")


class TestPropostaGeracaoSemTemplate:
    """Testa geração programática (sem template .docx)."""

    def test_gerar_proposta(self, generator, empresa, licitacao, itens, tmp_path):
        output = tmp_path / "proposta.docx"
        result = generator.gerar_proposta_preco(empresa, licitacao, itens, output)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_gerar_proposta_sem_itens(self, generator, empresa, licitacao, tmp_path):
        output = tmp_path / "proposta_vazia.docx"
        result = generator.gerar_proposta_preco(empresa, licitacao, [], output)
        assert result.exists()

    def test_gerar_proposta_item_unico(self, generator, empresa, licitacao, tmp_path):
        output = tmp_path / "proposta_single.docx"
        item = ItemProposta(numero=1, descricao="Servico X", valor_unitario=Decimal("1000"))
        result = generator.gerar_proposta_preco(empresa, licitacao, [item], output)
        assert result.exists()


class TestDeclaracaoGeracaoSemTemplate:
    """Testa geração de declarações (sem template .docx)."""

    def test_declaracao_me_epp(self, generator, empresa, tmp_path):
        output = tmp_path / "decl_me_epp.docx"
        result = generator.gerar_declaracao("me-epp", empresa, output)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_declaracao_fato_impeditivo(self, generator, empresa, tmp_path):
        output = tmp_path / "decl_fato.docx"
        result = generator.gerar_declaracao("fato-impeditivo", empresa, output)
        assert result.exists()

    def test_declaracao_menor(self, generator, empresa, tmp_path):
        output = tmp_path / "decl_menor.docx"
        result = generator.gerar_declaracao("menor", empresa, output)
        assert result.exists()

    def test_declaracao_tipo_invalido(self, generator, empresa, tmp_path):
        with pytest.raises(ValueError, match="invalido"):
            generator.gerar_declaracao("inexistente", empresa, tmp_path / "x.docx")


class TestDadosEmpresa:
    def test_from_json_file(self, tmp_path):
        data = {
            "razao_social": "Teste LTDA",
            "cnpj": "12345678000190",
            "email": "teste@teste.com",
        }
        path = tmp_path / "empresa.json"
        path.write_text(json.dumps(data))
        empresa = DadosEmpresa(**json.loads(path.read_text()))
        assert empresa.razao_social == "Teste LTDA"
        assert empresa.cnpj == "12345678000190"

    def test_campos_opcionais(self):
        empresa = DadosEmpresa(razao_social="X", cnpj="000")
        assert empresa.endereco == ""
        assert empresa.representante_legal == ""
        assert empresa.dados_bancarios == {}


class TestDeclaracaoIndependente:
    """Testa declaração de elaboração independente."""

    def test_declaracao_independente(self, generator, empresa, tmp_path):
        output = tmp_path / "decl_indep.docx"
        result = generator.gerar_declaracao("independente", empresa, output)
        assert result.exists()
        assert result.stat().st_size > 0


class TestPlanilhaCustos:
    """Testes para PlanilhaCustos IN 65/2021."""

    def test_modulo1_total(self):
        m1 = Modulo1Remuneracao(
            salario_base=Decimal("2000"),
            adicional_periculosidade=Decimal("600"),
        )
        assert m1.total == Decimal("2600")

    def test_modulo6_bdi(self):
        m6 = Modulo6CustosIndiretos(
            custos_indiretos_pct=Decimal("3"),
            lucro_pct=Decimal("6.79"),
            pis=Decimal("0.65"),
            cofins=Decimal("3.0"),
            iss=Decimal("5.0"),
        )
        assert m6.bdi_total_pct == Decimal("18.44")

    def test_modulo6_calculo(self):
        m6 = Modulo6CustosIndiretos(
            custos_indiretos_pct=Decimal("10"),
            lucro_pct=Decimal("0"),
            pis=Decimal("0"),
            cofins=Decimal("0"),
            iss=Decimal("0"),
        )
        assert m6.calcular_valor(Decimal("1000")) == Decimal("100")

    def test_planilha_valor_mensal(self):
        p = PlanilhaCustos(
            cargo="Auxiliar de Limpeza",
            quantidade_postos=3,
            modulo1=Modulo1Remuneracao(salario_base=Decimal("1500")),
            modulo6=Modulo6CustosIndiretos(
                custos_indiretos_pct=Decimal("10"),
                lucro_pct=Decimal("0"),
                pis=Decimal("0"), cofins=Decimal("0"), iss=Decimal("0"),
            ),
        )
        # subtotal_1_5 = 1500 (mod1) + 0+0+0+0 = 1500
        assert p.subtotal_modulos_1_5 == Decimal("1500")
        # mod6 = 1500 * 10% = 150
        assert p.valor_modulo_6 == Decimal("150")
        # mensal unitario = 1500 + 150 = 1650
        assert p.valor_mensal_unitario == Decimal("1650")
        # mensal total = 1650 * 3 postos = 4950
        assert p.valor_mensal_total == Decimal("4950")


class TestGeracaoPlanilhaCustos:
    """Testa geração de planilha de custos sem template."""

    def test_gerar_planilha(self, generator, empresa, licitacao, tmp_path):
        planilha = PlanilhaCustos(
            cargo="Servente",
            quantidade_postos=2,
            modulo1=Modulo1Remuneracao(salario_base=Decimal("1600")),
            modulo2=Modulo2Encargos(
                gps=Decimal("320"), fgts=Decimal("128"),
                vale_transporte=Decimal("200"),
            ),
            modulo5=Modulo5Insumos(uniformes=Decimal("50")),
            modulo6=Modulo6CustosIndiretos(
                custos_indiretos_pct=Decimal("3"),
                lucro_pct=Decimal("6.79"),
            ),
        )
        output = tmp_path / "planilha.docx"
        result = generator.gerar_planilha_custos(empresa, licitacao, [planilha], output)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_gerar_planilha_multiplos_cargos(self, generator, empresa, licitacao, tmp_path):
        planilhas = [
            PlanilhaCustos(cargo="Servente", quantidade_postos=5,
                           modulo1=Modulo1Remuneracao(salario_base=Decimal("1500"))),
            PlanilhaCustos(cargo="Encarregado", quantidade_postos=1,
                           modulo1=Modulo1Remuneracao(salario_base=Decimal("2500"))),
        ]
        output = tmp_path / "planilha_multi.docx"
        result = generator.gerar_planilha_custos(empresa, licitacao, planilhas, output, vigencia_meses=24)
        assert result.exists()


class TestChecklist:
    """Testes para geração de checklist."""

    def test_checklist_basico(self, generator, licitacao):
        checklist = generator.gerar_checklist(licitacao)
        docs = [c["documento"] for c in checklist]
        assert "Proposta de precos" in docs
        assert "Certidao conjunta de debitos federais (RFB/PGFN)" in docs
        assert "Atestado de capacidade tecnica" in docs

    def test_checklist_com_edital(self, generator, licitacao):
        class FakeEdital:
            exclusiva_me_epp = True
            cota_reservada = False
            visita_tecnica = "obrigatoria"
            exige_amostra = True
            garantia = type("G", (), {"exige": True, "percentual": 5})()
            habilitacao_detalhada = type("H", (), {"economico_financeira": ["Balanco"]})()

        checklist = generator.gerar_checklist(licitacao, edital=FakeEdital())
        docs = [c["documento"] for c in checklist]
        assert "Declaracao de ME/EPP (LC 123/2006)" in docs
        assert "Atestado de visita tecnica" in docs
        assert "Amostra do produto/material" in docs
        assert any("Garantia" in d for d in docs)
        assert "Balanco patrimonial do ultimo exercicio" in docs

    def test_checklist_sem_edital_sem_extras(self, generator, licitacao):
        checklist = generator.gerar_checklist(licitacao)
        docs = [c["documento"] for c in checklist]
        # Não deve ter documentos condicionais
        assert "Declaracao de ME/EPP (LC 123/2006)" not in docs
        assert "Amostra do produto/material" not in docs


class TestDadosLicitacao:
    def test_campos_opcionais(self):
        lic = DadosLicitacao()
        assert lic.numero == ""
        assert lic.orgao == ""
