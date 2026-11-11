"""Testes da seleção do alvo energético com dados fictícios."""

from copy import deepcopy

import pytest

from ai.src.preparar_alvo_energia import selecionar_alvo


@pytest.fixture
def linha():
    """Representa uma hora completa com consumo medido igual a zero."""
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
        "origem_energia": "corrente_medida_tensao_assumida",
    }


def test_aceita_zero_e_preserva_entrada(linha):
    dados = [linha]
    original = deepcopy(dados)

    resultado = selecionar_alvo(dados, "no1")

    assert len(resultado["aceites"]) == 1
    assert resultado["aceites"][0]["energia_Wh"] == 0
    assert dados == original


def test_exclui_hora_parcial(linha):
    # Energia calculada numa hora parcial não é um alvo horário completo.
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
    # Não deve criar uma linha para a hora 01:00, que não foi fornecida.
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
    """Cada combinação verifica uma inconsistência do resumo."""
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