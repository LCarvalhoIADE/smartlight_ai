"""Testes do validador com dados fictícios, sem acesso à API."""

from copy import deepcopy

import pytest

from ai.src.validar_historico import validar_historico


@pytest.fixture
def resposta():
    """Cria um período de 60 segundos com três leituras fictícias."""
    inicio = 1700000000

    leitura = {
        "divisao": "teste",
        "luz_raw": 0,
        "luz_pct": None,
        "presenca": 0,
        "led_pct": 0,
        "corrente_ma": None,
        "modo": "auto",
    }

    return {
        "no": {"no_id": "no1"},
        "de": inicio,
        "ate": inicio + 59,
        "mais": False,
        "leituras": [
            {**leitura, "ts": inicio + deslocamento}
            for deslocamento in (0, 15, 45)
        ],
    }


def test_resumo_cobertura_e_preservacao(resposta):
    """Verifica contagens, ausências, cobertura e preservação da entrada."""
    original = deepcopy(resposta)
    resumo = validar_historico(resposta, "no1")
    grupo = resumo["grupos"][0]

    assert resumo["total"] == 3
    assert grupo["segundos_intervalos_aceites"] == 45
    assert grupo["segundos_intervalos_longos"] == 0
    assert grupo["segundos_exteriores"] == 15
    assert grupo["cobertura_temporal_proporcao"] == pytest.approx(0.75)
    assert grupo["nulos"]["corrente_ma"] == 3
    assert grupo["nulos"]["luz_raw"] == 0
    assert resposta == original


@pytest.mark.parametrize("intervalo,alertas", [(30, 0), (31, 1)])
def test_fronteira_do_limite(resposta, intervalo, alertas):
    """Exatamente 30 segundos é aceite; 31 gera um alerta."""
    resposta["leituras"] = resposta["leituras"][:2]
    resposta["leituras"][1]["ts"] = resposta["de"] + intervalo

    grupo = validar_historico(resposta, "no1")["grupos"][0]

    assert grupo["alertas"] == alertas


def test_limite_configuravel(resposta):
    """Com limite de 20 segundos, o intervalo de 30 fica separado."""
    grupo = validar_historico(
        resposta, "no1", limite_intervalo=20
    )["grupos"][0]

    assert grupo["segundos_intervalos_aceites"] == 15
    assert grupo["segundos_intervalos_longos"] == 30

    # Todos os segundos do período pedido ficam contabilizados.
    assert (
        grupo["segundos_intervalos_aceites"]
        + grupo["segundos_intervalos_longos"]
        + grupo["segundos_exteriores"]
    ) == 60


def test_separa_divisoes(resposta):
    """O mesmo timestamp é permitido em divisões diferentes."""
    outra = {**resposta["leituras"][0], "divisao": "outra"}
    resposta["leituras"].append(outra)

    resumo = validar_historico(resposta, "no1")
    grupos = {grupo["divisao"]: grupo for grupo in resumo["grupos"]}

    assert len(grupos) == 2
    assert grupos["outra"]["intervalo_minimo"] is None
    assert grupos["outra"]["cobertura_temporal_proporcao"] == 0


def test_rejeita_duplicados(resposta):
    """Um registo repetido não deve aumentar artificialmente a contagem."""
    resposta["leituras"].append(resposta["leituras"][0].copy())

    with pytest.raises(ValueError, match="duplicado"):
        validar_historico(resposta, "no1")


@pytest.mark.parametrize("valor", [True, None, 0, "1700000000"])
def test_rejeita_timestamp_invalido(resposta, valor):
    """Não converte silenciosamente tipos ou timestamps inválidos."""
    resposta["leituras"][0]["ts"] = valor

    with pytest.raises(ValueError, match="timestamp"):
        validar_historico(resposta, "no1")


def test_rejeita_leitura_fora_do_periodo(resposta):
    resposta["leituras"][0]["ts"] = resposta["de"] - 1

    with pytest.raises(ValueError, match="fora do período"):
        validar_historico(resposta, "no1")


def test_rejeita_no_diferente(resposta):
    with pytest.raises(ValueError, match="nó"):
        validar_historico(resposta, "no3")


def test_rejeita_paginas_pendentes(resposta):
    resposta["mais"] = True

    with pytest.raises(ValueError, match="páginas"):
        validar_historico(resposta, "no1")


def test_rejeita_periodo_invertido(resposta):
    resposta["de"] = resposta["ate"] + 1

    with pytest.raises(ValueError, match="posterior"):
        validar_historico(resposta, "no1")


def test_rejeita_lista_vazia(resposta):
    resposta["leituras"] = []

    with pytest.raises(ValueError, match="lista"):
        validar_historico(resposta, "no1")


def test_rejeita_campo_em_falta(resposta):
    del resposta["leituras"][0]["corrente_ma"]

    with pytest.raises(ValueError, match="faltam campos"):
        validar_historico(resposta, "no1")


@pytest.mark.parametrize("limite", [0, -1, True, float("inf"), float("nan")])
def test_rejeita_limite_invalido(resposta, limite):
    with pytest.raises(ValueError, match="limite"):
        validar_historico(resposta, "no1", limite_intervalo=limite)