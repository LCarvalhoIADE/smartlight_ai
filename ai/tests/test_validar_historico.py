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


# Testes adicionais para o instante de chegada ao servidor.
# Os imports locais tornam este bloco independente dos nomes
# utilizados pelos testes anteriores.


def criar_historico_rececao():
    """Cria duas leituras fictícias com chegadas conhecidas."""
    return {
        "no": {"no_id": "no_teste"},
        "de": 1700000000,
        "ate": 1700000059,
        "mais": False,
        "leituras": [
            {
                "divisao": "sala",
                "ts": 1700000000,
                "recebido_ts": 1700000000,
                "luz_raw": 1,
                "luz_pct": None,
                "presenca": 1,
                "led_pct": 100,
                "corrente_ma": None,
                "modo": "auto",
            },
            {
                "divisao": "sala",
                "ts": 1700000015,
                "recebido_ts": 1700000016,
                "luz_raw": 0,
                "luz_pct": None,
                "presenca": 0,
                "led_pct": 0,
                "corrente_ma": None,
                "modo": "auto",
            },
        ],
    }


def resumir_historico_rececao(dados):
    """Executa a função pública, sem alterar os dados."""
    from ai.src.validar_historico import validar_historico

    return validar_historico(dados, no_esperado="no_teste")


def test_rececao_preserva_entrada_e_intervalos():
    from copy import deepcopy

    dados = criar_historico_rececao()
    original = deepcopy(dados)

    grupo = resumir_historico_rececao(dados)["grupos"][0]
    rececao = grupo["disponibilidade"]

    assert rececao["com_timestamp"] == 2
    assert rececao["desconhecida"] == 0
    assert rececao["anteriores_a_medicao"] == 0
    assert rececao["diferenca_minima_segundos"] == 0
    assert rececao["diferenca_maxima_segundos"] == 1

    # O intervalo continua a ser calculado entre medições.
    assert grupo["intervalo_minimo"] == 15
    assert grupo["segundos_intervalos_aceites"] == 15
    assert dados == original


def test_rececao_historico_antigo_sem_campo():
    dados = criar_historico_rececao()

    for leitura in dados["leituras"]:
        del leitura["recebido_ts"]

    rececao = resumir_historico_rececao(dados)["grupos"][0][
        "disponibilidade"
    ]

    assert rececao["sem_campo"] == 2
    assert rececao["nulos"] == 0
    assert rececao["desconhecida"] == 2
    assert rececao["com_timestamp"] == 0
    assert rececao["diferenca_minima_segundos"] is None
    assert rececao["diferenca_maxima_segundos"] is None

    # Não acrescenta timestamps inventados.
    assert all(
        "recebido_ts" not in leitura
        for leitura in dados["leituras"]
    )


def test_rececao_distingue_ausente_e_nulo():
    dados = criar_historico_rececao()
    del dados["leituras"][0]["recebido_ts"]
    dados["leituras"][1]["recebido_ts"] = None

    rececao = resumir_historico_rececao(dados)["grupos"][0][
        "disponibilidade"
    ]

    assert rececao["sem_campo"] == 1
    assert rececao["nulos"] == 1
    assert rececao["desconhecida"] == 2
    assert dados["leituras"][1]["recebido_ts"] is None


def test_rececao_permite_chegada_depois_do_periodo():
    dados = criar_historico_rececao()

    # Simula uma leitura guardada na fila e recebida um dia depois.
    leitura = dados["leituras"][1]
    leitura["recebido_ts"] = leitura["ts"] + 86400

    grupo = resumir_historico_rececao(dados)["grupos"][0]

    assert (
        grupo["disponibilidade"]["diferenca_maxima_segundos"]
        == 86400
    )
    assert grupo["segundos_intervalos_aceites"] == 15


def test_rececao_sinaliza_chegada_anterior_sem_corrigir():
    from copy import deepcopy

    dados = criar_historico_rececao()
    dados["leituras"][0]["recebido_ts"] -= 2
    original = deepcopy(dados)

    rececao = resumir_historico_rececao(dados)["grupos"][0][
        "disponibilidade"
    ]

    assert rececao["anteriores_a_medicao"] == 1
    assert rececao["diferenca_minima_segundos"] == -2
    assert dados == original


def test_rececao_separa_divisoes():
    dados = criar_historico_rececao()
    dados["leituras"][1]["divisao"] = "quarto"
    dados["leituras"][1]["recebido_ts"] = None

    grupos = {
        grupo["divisao"]: grupo["disponibilidade"]
        for grupo in resumir_historico_rececao(dados)["grupos"]
    }

    assert grupos["sala"]["com_timestamp"] == 1
    assert grupos["sala"]["desconhecida"] == 0
    assert grupos["quarto"]["com_timestamp"] == 0
    assert grupos["quarto"]["desconhecida"] == 1


# Cada valor inválido é verificado como um caso independente.
import pytest


@pytest.mark.parametrize(
    "valor",
    [
        True,
        False,
        0,
        -1,
        1700000000.0,
        "1700000000",
        float("nan"),
        float("inf"),
        10**30,
    ],
)
def test_rececao_rejeita_timestamp_invalido(valor):
    dados = criar_historico_rececao()
    dados["leituras"][0]["recebido_ts"] = valor

    with pytest.raises(ValueError, match="recebido_ts"):
        resumir_historico_rececao(dados)
