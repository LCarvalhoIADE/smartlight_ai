"""Testes de cobertura energética com dados fictícios."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from ai.src.analisar_cobertura_energia import analisar_cobertura


@pytest.fixture
def resposta():
    """Cria um dia UTC completo com leituras nos primeiros 30 segundos."""
    inicio = int(
        datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp()
    )

    # Leitura fictícia: corrente zero é uma medição válida.
    leitura = {
        "divisao": "teste",
        "luz_raw": 0,
        "luz_pct": None,
        "presenca": 0,
        "led_pct": 0,
        "corrente_ma": 0,
        "modo": "auto",
    }

    return {
        "no": {"no_id": "no1"},
        "de": inicio,
        "ate": inicio + 86400 - 1,
        "mais": False,
        "leituras": [
            {**leitura, "ts": inicio + deslocamento}
            for deslocamento in (0, 15, 30)
        ],
    }


def test_cobertura_parcial_e_preservacao(resposta):
    """Conta todas as horas pedidas sem inventar energia nas restantes."""
    # Guarda uma cópia para confirmar que a entrada não é alterada.
    original = deepcopy(resposta)

    resultado = analisar_cobertura(resposta, "no1")
    dia = resultado["diarios"][0]

    # Só existem intervalos válidos nos primeiros 30 segundos.
    assert dia["horas_completas"] == 0
    assert dia["horas_parciais"] == 1
    assert dia["horas_sem_cobertura"] == 23
    assert dia["segundos_integrados"] == 30
    assert dia["segundos_excluidos"] == 0
    assert dia["segundos_sem_intervalo"] == 86370

    # Corrente medida igual a zero produz energia integrada igual a zero.
    assert dia["energia_integrada_mWh"] == 0
    assert resposta == original


def test_corrente_ausente_nao_equivale_a_zero(resposta):
    """Mantém a energia ausente quando nenhum intervalo é integrável."""
    # Simula leituras sem medição de corrente.
    for leitura in resposta["leituras"]:
        leitura["corrente_ma"] = None

    resultado = analisar_cobertura(resposta, "no1")
    dia = resultado["diarios"][0]

    assert dia["correntes_ausentes"] == 3
    assert dia["energia_integrada_mWh"] is None
    assert dia["horas_sem_cobertura"] == 24

    # Os intervalos existem, mas não permitem calcular energia.
    assert dia["segundos_excluidos"] == 30
    assert resultado["horas_incompletas"][0]["correntes_ausentes"] == 3


def test_identifica_uma_hora_completa(resposta):
    """Uma sequência válida de uma hora produz 3 600 segundos integrados."""
    modelo = resposta["leituras"][0]
    inicio = resposta["de"]

    # Inclui a leitura da fronteira seguinte para integrar a hora inteira.
    resposta["leituras"] = [
        {**modelo, "ts": inicio + deslocamento}
        for deslocamento in range(0, 3601, 15)
    ]

    dia = analisar_cobertura(resposta, "no1")["diarios"][0]

    assert dia["horas_completas"] == 1
    assert dia["horas_parciais"] == 0
    assert dia["horas_sem_cobertura"] == 23
    assert dia["segundos_integrados"] == 3600


def test_separa_divisoes(resposta):
    """Não soma tempos de duas divisões como se fossem uma só."""
    # Cria leituras nos mesmos instantes, mas noutra divisão.
    adicionais = [
        {**leitura, "divisao": "outra"}
        for leitura in resposta["leituras"]
    ]
    resposta["leituras"].extend(adicionais)

    resultado = analisar_cobertura(resposta, "no1")

    assert len(resultado["diarios"]) == 2
    assert all(
        dia["segundos_integrados"] == 30
        for dia in resultado["diarios"]
    )


def test_separa_dias_e_contabiliza_intervalos_longos(resposta):
    """Um intervalo longo não é convertido em energia estimada."""
    inicio = resposta["de"]

    # Alarga o período pedido para dois dias completos.
    resposta["ate"] += 86400

    # Acrescenta uma leitura no início do segundo dia.
    resposta["leituras"].append({
        **resposta["leituras"][0],
        "ts": inicio + 86400,
    })

    diarios = analisar_cobertura(resposta, "no1")["diarios"]

    assert len(diarios) == 2
    assert diarios[0]["segundos_integrados"] == 30
    assert diarios[0]["segundos_excluidos"] == 86370
    assert diarios[1]["energia_integrada_mWh"] is None

    # Cada dia deve contabilizar exatamente 86 400 segundos.
    for dia in diarios:
        assert (
            dia["segundos_integrados"]
            + dia["segundos_excluidos"]
            + dia["segundos_sem_intervalo"]
        ) == 86400


def test_rejeita_periodo_que_nao_seja_dia_completo(resposta):
    """Evita apresentar uma percentagem diária com limites ambíguos."""
    # Retira um segundo ao período originalmente completo.
    resposta["ate"] -= 1

    with pytest.raises(ValueError, match="dias completos"):
        analisar_cobertura(resposta, "no1")