"""Testes da seleção do alvo energético com dados fictícios."""

import csv
import io
from copy import deepcopy

import pytest

from ai.src.preparar_alvo_energia import (
    CAMPOS_SAIDA,
    ORIGEM_CORRENTE,
    ORIGEM_PWM,
    selecionar_alvo,
)


@pytest.fixture
def linha():
    """Hora completa obtida de corrente medida e tensão assumida."""
    return {
        "no_id": "no1",
        "divisao": "teste",
        "hora_utc": "2026-11-02T00:00:00+00:00",
        "energia_mWh": "0",
        "energia_Wh": "0",
        "segundos_integrados": "3600",
        "segundos_excluidos": "0",
        "cobertura_proporcao": "1",
        "tensao_assumida_v": "3.3",
        "limite_intervalo_segundos": "30",
        "origem_energia": ORIGEM_CORRENTE,
    }


@pytest.fixture
def linha_pwm(linha):
    """Representa a estrutura do CSV produzido pelo estimador PWM."""
    estimada = deepcopy(linha)
    estimada.pop("tensao_assumida_v")
    estimada.update({
        "no_id": "no3",
        "potencia_referencia_mW": "17.9",
        "origem_energia": ORIGEM_PWM,
        "energia_mWh": "8.95",
        "energia_Wh": "0.00895",
    })
    return estimada


def test_aceita_zero_e_preserva_entrada(linha):
    dados = [linha]
    original = deepcopy(dados)

    resultado = selecionar_alvo(dados, "no1")
    aceite = resultado["aceites"][0]

    assert aceite["energia_Wh"] == 0
    assert aceite["tensao_assumida_v"] == 3.3
    assert aceite["potencia_referencia_mW"] is None
    assert aceite["origem_energia"] == ORIGEM_CORRENTE
    assert dados == original


def test_exclui_hora_parcial(linha):
    linha["segundos_integrados"] = "1800"
    linha["cobertura_proporcao"] = "0.5"

    resultado = selecionar_alvo([linha], "no1")

    assert resultado["aceites"] == []
    assert resultado["excluidas_parciais"] == 1


def test_exclui_ausencia_sem_converter_para_zero(linha):
    linha.update({
        "energia_mWh": "",
        "energia_Wh": "",
        "segundos_integrados": "0",
        "segundos_excluidos": "3600",
        "cobertura_proporcao": "0",
    })

    resultado = selecionar_alvo([linha], "no1")

    assert resultado["aceites"] == []
    assert resultado["excluidas_sem_cobertura"] == 1


def test_preserva_lacunas_e_ordena(linha):
    # Não cria a hora 01:00, que não foi fornecida.
    posterior = {**linha, "hora_utc": "2026-11-02T02:00:00+00:00"}

    resultado = selecionar_alvo([posterior, linha], "no1")

    assert [item["hora_utc"] for item in resultado["aceites"]] == [
        "2026-11-02T00:00:00+00:00",
        "2026-11-02T02:00:00+00:00",
    ]


def test_rejeita_duplicado(linha):
    with pytest.raises(ValueError, match="duplicado"):
        selecionar_alvo([linha, linha.copy()], "no1")


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("no_id", "no3"),
        ("hora_utc", "2026-11-02T00:30:00+00:00"),
        ("hora_utc", "2026-11-02T00:00:00"),
        ("energia_mWh", "-1"),
        ("energia_mWh", "nan"),
        ("energia_Wh", "1"),
        ("cobertura_proporcao", "0.5"),
        ("segundos_integrados", "3601"),
        ("segundos_excluidos", "1"),
        ("origem_energia", "estimativa_pwm"),
    ],
)
def test_rejeita_resumo_invalido(linha, campo, valor):
    """Mantém as verificações anteriores de consistência."""
    linha[campo] = valor

    with pytest.raises(ValueError):
        selecionar_alvo([linha], "no1")


def test_separa_divisoes(linha):
    outra = {**linha, "divisao": "outra"}

    resultado = selecionar_alvo([linha, outra], "no1")

    assert len(resultado["aceites"]) == 2


def test_rejeita_hipoteses_misturadas(linha):
    posterior = {
        **linha,
        "hora_utc": "2026-11-02T01:00:00+00:00",
        "tensao_assumida_v": "5",
    }

    with pytest.raises(ValueError, match="hipóteses diferentes"):
        selecionar_alvo([linha, posterior], "no1")


def test_rejeita_lista_vazia():
    with pytest.raises(ValueError, match="lista"):
        selecionar_alvo([], "no1")


def test_aceita_pwm_e_preserva_origem_e_entrada(linha_pwm):
    original = deepcopy(linha_pwm)

    resultado = selecionar_alvo([linha_pwm], "no3")
    aceite = resultado["aceites"][0]

    assert aceite["origem_energia"] == ORIGEM_PWM
    assert aceite["potencia_referencia_mW"] == 17.9
    assert aceite["tensao_assumida_v"] is None
    assert aceite["energia_mWh"] == pytest.approx(8.95)
    assert linha_pwm == original


def test_aceita_pwm_zero(linha_pwm):
    """Uma estimativa zero continua válida numa hora completa."""
    linha_pwm["energia_mWh"] = "0"
    linha_pwm["energia_Wh"] = "0"

    resultado = selecionar_alvo([linha_pwm], "no3")

    assert resultado["aceites"][0]["energia_Wh"] == 0


@pytest.mark.parametrize(
    "integrados,excluidos,cobertura,energia,motivo",
    [
        ("1800", "0", "0.5", "0", "excluidas_parciais"),
        ("0", "3600", "0", "", "excluidas_sem_cobertura"),
    ],
)
def test_exclui_pwm_incompleto(
    linha_pwm, integrados, excluidos, cobertura, energia, motivo
):
    linha_pwm.update({
        "segundos_integrados": integrados,
        "segundos_excluidos": excluidos,
        "cobertura_proporcao": cobertura,
        "energia_mWh": energia,
        "energia_Wh": energia,
    })

    resultado = selecionar_alvo([linha_pwm], "no3")

    assert resultado["aceites"] == []
    assert resultado[motivo] == 1


@pytest.mark.parametrize(
    "referencia",
    [None, "", "0", "-1", "nan", "inf", True],
)
def test_rejeita_referencia_pwm_invalida(linha_pwm, referencia):
    linha_pwm["potencia_referencia_mW"] = referencia

    with pytest.raises(ValueError, match="potencia_referencia_mW"):
        selecionar_alvo([linha_pwm], "no3")


def test_rejeita_referencia_pwm_em_falta(linha_pwm):
    del linha_pwm["potencia_referencia_mW"]

    with pytest.raises(ValueError, match="Falta o campo"):
        selecionar_alvo([linha_pwm], "no3")


def test_rejeita_tensao_em_falta(linha):
    del linha["tensao_assumida_v"]

    with pytest.raises(ValueError, match="Falta o campo"):
        selecionar_alvo([linha], "no1")


def test_rejeita_referencia_nao_aplicavel_na_corrente(linha):
    linha["potencia_referencia_mW"] = "17.9"

    with pytest.raises(ValueError, match="não aplicável"):
        selecionar_alvo([linha], "no1")


def test_rejeita_referencia_nao_aplicavel_no_pwm(linha_pwm):
    linha_pwm["tensao_assumida_v"] = "3.3"

    with pytest.raises(ValueError, match="não aplicável"):
        selecionar_alvo([linha_pwm], "no3")


def test_rejeita_origens_misturadas_na_mesma_divisao(linha, linha_pwm):
    # Mesmo nó e divisão, mas métodos diferentes em horas distintas.
    linha_pwm["no_id"] = "no1"
    linha_pwm["hora_utc"] = "2026-11-02T01:00:00+00:00"

    with pytest.raises(ValueError, match="hipóteses diferentes"):
        selecionar_alvo([linha, linha_pwm], "no1")


def test_rejeita_potencias_misturadas_na_mesma_divisao(linha_pwm):
    posterior = {
        **linha_pwm,
        "hora_utc": "2026-11-02T01:00:00+00:00",
        "potencia_referencia_mW": "20",
    }

    with pytest.raises(ValueError, match="hipóteses diferentes"):
        selecionar_alvo([linha_pwm, posterior], "no3")


def test_permite_referencias_diferentes_por_divisao(linha_pwm):
    outra = {
        **linha_pwm,
        "divisao": "outra",
        "potencia_referencia_mW": "20",
    }

    resultado = selecionar_alvo([linha_pwm, outra], "no3")

    assert len(resultado["aceites"]) == 2
    assert {
        item["potencia_referencia_mW"]
        for item in resultado["aceites"]
    } == {17.9, 20.0}


@pytest.mark.parametrize("origem", [ORIGEM_CORRENTE, ORIGEM_PWM])
def test_csv_preserva_referencia_e_campo_vazio(linha, linha_pwm, origem):
    """Verifica a representação CSV e a possibilidade de voltar a lê-la."""
    entrada = linha if origem == ORIGEM_CORRENTE else linha_pwm
    no_id = entrada["no_id"]
    aceites = selecionar_alvo([entrada], no_id)["aceites"]

    # Usa memória, sem criar nem modificar ficheiros reais.
    memoria = io.StringIO()
    escritor = csv.DictWriter(memoria, fieldnames=CAMPOS_SAIDA)
    escritor.writeheader()
    escritor.writerows(aceites)
    memoria.seek(0)

    relidas = list(csv.DictReader(memoria))
    campo_vazio = (
        "potencia_referencia_mW"
        if origem == ORIGEM_CORRENTE
        else "tensao_assumida_v"
    )

    assert relidas[0][campo_vazio] == ""
    assert relidas[0]["origem_energia"] == origem
    assert selecionar_alvo(relidas, no_id)["aceites"] == aceites