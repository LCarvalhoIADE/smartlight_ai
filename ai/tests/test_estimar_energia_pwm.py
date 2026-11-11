"""Testa a estimativa PWM com leituras fictícias."""

from copy import deepcopy

import pytest

from ai.src.estimar_energia_pwm import estimar


@pytest.fixture
def resposta():
    """Cria duas leituras separadas por 30 segundos."""
    inicio = 1793577600  # 02/11/2026 às 00:00 UTC.

    leitura = {
        "divisao": "teste",
        "luz_raw": 1,
        "luz_pct": None,
        "presenca": 1,
        "led_pct": 100,
        "corrente_ma": None,
        "modo": "auto",
    }

    return {
        "no": {"no_id": "no3"},
        "de": inicio,
        "ate": inicio + 86399,
        "mais": False,
        "leituras": [
            {**leitura, "ts": inicio},
            {**leitura, "ts": inicio + 30},
        ],
    }


def executar(resposta, **opcoes):
    """Usa uma referência fictícia de 36 mW para facilitar as contas."""
    return estimar(
        resposta,
        no_esperado="no3",
        divisao="teste",
        potencia_referencia_mw=36,
        **opcoes,
    )


def test_pwm_constante_unidades_e_preservacao(resposta):
    original = deepcopy(resposta)
    linha = executar(resposta)[0]

    # 36 mW durante 30 segundos = 0,3 mWh.
    assert linha["energia_mWh"] == pytest.approx(0.3)
    assert linha["energia_Wh"] == pytest.approx(0.0003)
    assert linha["segundos_integrados"] == 30
    assert linha["origem_energia"] == "estimativa_pwm_potencia_assumida"
    assert linha["potencia_referencia_mW"] == 36
    assert resposta == original

    # Não foram inventadas medições de corrente.
    assert all(linha["corrente_ma"] is None for linha in resposta["leituras"])


def test_pwm_zero_e_valido(resposta):
    for leitura in resposta["leituras"]:
        leitura["led_pct"] = 0

    linha = executar(resposta)[0]

    assert linha["energia_mWh"] == 0
    assert linha["segundos_integrados"] == 30


def test_pwm_variavel_utiliza_trapezio(resposta):
    resposta["leituras"][0]["led_pct"] = 0

    # Potência média de 18 mW durante 30 segundos.
    assert executar(resposta)[0]["energia_mWh"] == pytest.approx(0.15)


def test_divide_na_fronteira_horaria(resposta):
    inicio = resposta["de"]
    resposta["leituras"][0].update(ts=inicio + 3590, led_pct=0)
    resposta["leituras"][1].update(ts=inicio + 3610, led_pct=100)

    linhas = executar(resposta)

    # Primeira metade: potência de 0 a 18 mW.
    # Segunda metade: potência de 18 a 36 mW.
    assert len(linhas) == 2
    assert linhas[0]["energia_mWh"] == pytest.approx(0.025)
    assert linhas[1]["energia_mWh"] == pytest.approx(0.075)
    assert sum(linha["energia_mWh"] for linha in linhas) == pytest.approx(0.1)


def test_exclui_intervalo_longo(resposta):
    resposta["leituras"][1]["ts"] += 1

    linha = executar(resposta)[0]

    assert linha["energia_mWh"] is None
    assert linha["segundos_integrados"] == 0
    assert linha["segundos_excluidos"] == 31


def test_limite_configuravel(resposta):
    resposta["leituras"][1]["ts"] += 1

    linha = executar(resposta, limite_intervalo=31)[0]

    assert linha["segundos_integrados"] == 31
    assert linha["segundos_excluidos"] == 0


def test_leitura_isolada_nao_inventa_energia(resposta):
    resposta["leituras"] = resposta["leituras"][:1]

    linha = executar(resposta)[0]

    assert linha["energia_mWh"] is None
    assert linha["segundos_integrados"] == 0


def test_seleciona_apenas_a_divisao_pedida(resposta):
    resposta["leituras"].extend([
        {**leitura, "divisao": "outra", "led_pct": 0}
        for leitura in list(resposta["leituras"])
    ])

    linhas = executar(resposta)

    assert len(linhas) == 1
    assert linhas[0]["divisao"] == "teste"
    assert linhas[0]["energia_mWh"] == pytest.approx(0.3)


@pytest.mark.parametrize("pwm", [None, True, -1, 101, "erro", float("nan")])
def test_rejeita_pwm_invalido(resposta, pwm):
    resposta["leituras"][0]["led_pct"] = pwm

    with pytest.raises(ValueError, match="led_pct"):
        executar(resposta)


@pytest.mark.parametrize("referencia", [0, -1, True, float("inf")])
def test_rejeita_referencia_invalida(resposta, referencia):
    with pytest.raises(ValueError, match="Potência"):
        estimar(resposta, "no3", "teste", referencia)


def test_rejeita_divisao_sem_leituras(resposta):
    with pytest.raises(ValueError, match="Não existem leituras"):
        estimar(resposta, "no3", "inexistente", 36)