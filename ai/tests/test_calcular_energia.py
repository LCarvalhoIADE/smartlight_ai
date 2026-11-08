"""Testes do cálculo energético com leituras fictícias."""

from copy import deepcopy

import pytest

from ai.src.calcular_energia import calcular


# Timestamp correspondente a 2026-11-02 00:00:00 UTC.
INICIO = 1793577600


def criar_resposta(pontos, divisao="teste"):
    """Cria uma resposta da API a partir de pares (segundos, corrente)."""
    return {
        "no": {"no_id": "no1"},
        "mais": False,
        "leituras": [
            {
                "divisao": divisao,
                "ts": INICIO + segundos,
                "corrente_ma": corrente,
            }
            for segundos, corrente in pontos
        ],
    }


def test_corrente_constante_e_preservacao():
    """Verifica unidades, duração real e preservação da entrada."""
    resposta = criar_resposta([(0, 10), (15, 10), (31, 10)])
    original = deepcopy(resposta)

    resultado = calcular(resposta)
    hora = resultado[0]

    # 3,3 V × 10 mA = 33 mW, durante 31 segundos.
    esperado = 33 * 31 / 3600
    assert hora["energia_mWh"] == pytest.approx(esperado)
    assert hora["energia_Wh"] == pytest.approx(esperado / 1000)
    assert hora["segundos_integrados"] == 31
    assert hora["segundos_excluidos"] == 0
    assert hora["cobertura_proporcao"] == pytest.approx(31 / 3600)
    assert resposta == original


def test_trapezio_com_corrente_variavel():
    """Verifica a média das potências nas extremidades do intervalo."""
    resposta = criar_resposta([(0, 0), (20, 10)])

    resultado = calcular(resposta)

    # Potência média de (0 + 33) / 2 = 16,5 mW, durante 20 segundos.
    assert resultado[0]["energia_mWh"] == pytest.approx(
        16.5 * 20 / 3600
    )


def test_divide_energia_na_fronteira_horaria():
    """Verifica a interpolação ao atravessar a mudança de hora."""
    resposta = criar_resposta([(3590, 0), (3610, 10)])

    resultado = calcular(resposta)

    assert len(resultado) == 2
    assert resultado[0]["hora_utc"] == "2026-11-02T00:00:00+00:00"
    assert resultado[1]["hora_utc"] == "2026-11-02T01:00:00+00:00"

    # Na fronteira, a potência interpolada é 16,5 mW.
    # Primeiro segmento: média de 0 e 16,5 mW, durante 10 segundos.
    assert resultado[0]["energia_mWh"] == pytest.approx(
        8.25 * 10 / 3600
    )

    # Segundo segmento: média de 16,5 e 33 mW, durante 10 segundos.
    assert resultado[1]["energia_mWh"] == pytest.approx(
        24.75 * 10 / 3600
    )
    assert [hora["segundos_integrados"] for hora in resultado] == [10, 10]

    # A divisão pelas horas deve conservar a energia do intervalo inteiro.
    assert sum(hora["energia_mWh"] for hora in resultado) == pytest.approx(
        16.5 * 20 / 3600
    )


@pytest.mark.parametrize(
    "duracao,integrados,excluidos",
    [(30, 30, 0), (31, 0, 31)],
)
def test_fronteira_do_limite(duracao, integrados, excluidos):
    """Aceita exatamente 30 segundos e exclui intervalos superiores."""
    resposta = criar_resposta([(0, 10), (duracao, 10)])

    hora = calcular(resposta)[0]

    assert hora["segundos_integrados"] == integrados
    assert hora["segundos_excluidos"] == excluidos

    if integrados:
        assert hora["energia_mWh"] == pytest.approx(33 * duracao / 3600)
    else:
        assert hora["energia_mWh"] is None


def test_limite_configuravel():
    """Permite aceitar um intervalo maior através do parâmetro explícito."""
    resposta = criar_resposta([(0, 10), (40, 10)])

    hora = calcular(resposta, limite_intervalo=40)[0]

    assert hora["segundos_integrados"] == 40
    assert hora["energia_mWh"] == pytest.approx(33 * 40 / 3600)


@pytest.mark.parametrize("corrente", [None, -1, float("nan"), float("inf")])
def test_corrente_invalida_exclui_intervalos_adjacentes(corrente):
    """Mantém a interrupção provocada por uma medição inválida."""
    resposta = criar_resposta([(0, 10), (15, corrente), (30, 10)])

    hora = calcular(resposta)[0]

    # Os dois intervalos utilizam a medição inválida.
    assert hora["segundos_integrados"] == 0
    assert hora["segundos_excluidos"] == 30
    assert hora["energia_mWh"] is None


def test_corrente_zero_tem_energia_zero():
    """Distingue uma medição válida de zero da ausência de medição."""
    resposta = criar_resposta([(0, 0), (15, 0)])

    hora = calcular(resposta)[0]

    assert hora["energia_mWh"] == 0
    assert hora["segundos_integrados"] == 15


def test_leitura_isolada():
    """Uma única leitura permite identificar a hora, com cobertura zero."""
    resposta = criar_resposta([(14, 5)])

    hora = calcular(resposta)[0]

    assert hora["energia_mWh"] is None
    assert hora["segundos_integrados"] == 0
    assert hora["cobertura_proporcao"] == 0


def test_separa_divisoes():
    """Calcula cada divisão com os seus próprios intervalos."""
    resposta = criar_resposta([(0, 10), (15, 10)], divisao="sala")
    quarto = criar_resposta([(0, 20), (15, 20)], divisao="quarto")
    resposta["leituras"].extend(quarto["leituras"])

    resultado = {
        hora["divisao"]: hora
        for hora in calcular(resposta)
    }

    assert resultado["sala"]["energia_mWh"] == pytest.approx(33 * 15 / 3600)
    assert resultado["quarto"]["energia_mWh"] == pytest.approx(66 * 15 / 3600)


def test_rejeita_duplicados():
    """Rejeita dois registos da mesma divisão no mesmo instante."""
    resposta = criar_resposta([(0, 10), (0, 10)])

    with pytest.raises(ValueError, match="duplicado"):
        calcular(resposta)


def test_rejeita_resposta_com_mais_paginas():
    """Impede calcular sobre uma resposta que ainda indica continuação."""
    resposta = criar_resposta([(0, 10), (15, 10)])
    resposta["mais"] = True

    with pytest.raises(ValueError, match="mais=false"):
        calcular(resposta)