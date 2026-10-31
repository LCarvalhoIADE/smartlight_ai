"""Testes da agregação horária com dados fictícios."""

from copy import deepcopy
from datetime import datetime

import pytest

from ai.src.agregar_por_hora import agregar


@pytest.fixture
def criar_leitura():
    """Cria leituras com data explícita em UTC para facilitar os testes."""

    def criar(
        instante="2026-10-26T10:00:00+00:00",
        divisao="sala",
        presenca=1,
        led_pct=100,
        luz_pct=None,
    ):
        data = datetime.fromisoformat(instante)

        return {
            "no_id": "no3",
            "divisao": divisao,
            "ts": int(data.timestamp()),
            "luz_raw": 1,
            "luz_pct": luz_pct,
            "presenca": presenca,
            "led_pct": led_pct,
            "modo": "auto",
            "hora": data.strftime("%Y-%m-%d %H:%M:%S"),
        }

    return criar


def test_calcula_medias_e_preserva_entrada(criar_leitura):
    """Verifica médias, contagens, ordenação e preservação dos dados."""
    dados = [
        criar_leitura(
            "2026-10-26T10:00:30+00:00",
            presenca=0,
            led_pct=20,
            luz_pct=60,
        ),
        criar_leitura(
            "2026-10-26T10:00:00+00:00",
            presenca=1,
            led_pct=100,
            luz_pct=20,
        ),
    ]
    original = deepcopy(dados)

    resultado = agregar(dados)

    assert len(resultado) == 1
    resumo = resultado[0]

    assert resumo["no_id"] == "no3"
    assert resumo["divisao"] == "sala"
    assert resumo["hora_utc"] == "2026-10-26T10:00:00+00:00"
    assert resumo["numero_leituras"] == 2
    assert resumo["primeira_leitura_utc"] == dados[1]["hora"].replace(
        " ", "T"
    ) + "+00:00"
    assert resumo["ultima_leitura_utc"] == "2026-10-26T10:00:30+00:00"
    assert resumo["intervalo_observado_segundos"] == 30
    assert resumo["presenca_proporcao"] == pytest.approx(0.5)
    assert resumo["led_pct_medio"] == pytest.approx(60)
    assert resumo["luz_pct_media"] == pytest.approx(40)
    assert resumo["numero_leituras_luz_pct"] == 2
    assert dados == original


def test_separa_horas_na_fronteira(criar_leitura):
    """Leituras antes e depois da hora certa pertencem a grupos distintos."""
    dados = [
        criar_leitura("2026-10-26T11:00:00+00:00"),
        criar_leitura("2026-10-26T10:59:59+00:00"),
    ]

    resultado = agregar(dados)

    assert [r["hora_utc"] for r in resultado] == [
        "2026-10-26T10:00:00+00:00",
        "2026-10-26T11:00:00+00:00",
    ]
    assert [r["numero_leituras"] for r in resultado] == [1, 1]


def test_separa_dias(criar_leitura):
    """A mesma hora em dias diferentes não pode ser agrupada."""
    dados = [
        criar_leitura("2026-10-27T10:15:00+00:00"),
        criar_leitura("2026-10-26T10:15:00+00:00"),
    ]

    resultado = agregar(dados)

    assert [r["hora_utc"] for r in resultado] == [
        "2026-10-26T10:00:00+00:00",
        "2026-10-27T10:00:00+00:00",
    ]


def test_separa_divisoes(criar_leitura):
    """Cada divisão mantém as suas próprias contagens e médias."""
    dados = [
        criar_leitura(divisao="sala", led_pct=100),
        criar_leitura(divisao="quarto", led_pct=0),
    ]

    resultado = agregar(dados)
    grupos = {r["divisao"]: r for r in resultado}

    assert len(grupos) == 2
    assert grupos["sala"]["led_pct_medio"] == 100
    assert grupos["quarto"]["led_pct_medio"] == 0
    assert grupos["sala"]["numero_leituras"] == 1
    assert grupos["quarto"]["numero_leituras"] == 1


def test_luminosidade_totalmente_nula(criar_leitura):
    """Sem medições válidas, a luminosidade média permanece nula."""
    dados = [
        criar_leitura(),
        criar_leitura("2026-10-26T10:00:15+00:00"),
    ]

    resumo = agregar(dados)[0]

    assert resumo["luz_pct_media"] is None
    assert resumo["numero_leituras_luz_pct"] == 0


def test_luminosidade_ignora_nulos_mas_inclui_zero(criar_leitura):
    """Zero é uma medição válida; apenas None fica fora da média."""
    dados = [
        criar_leitura(luz_pct=None),
        criar_leitura(
            "2026-10-26T10:00:15+00:00",
            luz_pct=0,
        ),
        criar_leitura(
            "2026-10-26T10:00:30+00:00",
            luz_pct=60,
        ),
    ]

    resumo = agregar(dados)[0]

    # A média correta é (0 + 60) / 2 = 30.
    assert resumo["luz_pct_media"] == pytest.approx(30)
    assert resumo["numero_leituras_luz_pct"] == 2
    assert resumo["numero_leituras"] == 3


def test_uma_leitura(criar_leitura):
    """Uma leitura produz um resumo, com intervalo observado igual a zero."""
    resumo = agregar([criar_leitura()])[0]

    assert resumo["numero_leituras"] == 1
    assert resumo["intervalo_observado_segundos"] == 0
    assert resumo["primeira_leitura_utc"] == resumo["ultima_leitura_utc"]
    assert resumo["presenca_proporcao"] == 1


def test_nao_preenche_horas_sem_dados(criar_leitura):
    """A ausência de leituras às 11h não deve gerar uma linha artificial."""
    dados = [
        criar_leitura("2026-10-26T10:00:00+00:00"),
        criar_leitura("2026-10-26T12:00:00+00:00"),
    ]

    resultado = agregar(dados)

    assert [r["hora_utc"] for r in resultado] == [
        "2026-10-26T10:00:00+00:00",
        "2026-10-26T12:00:00+00:00",
    ]


def test_rejeita_duplicados(criar_leitura):
    """Confirma que a agregação reutiliza a validação de duplicados."""
    leitura = criar_leitura()

    with pytest.raises(ValueError, match="duplicado"):
        agregar([leitura, leitura.copy()])


def test_rejeita_lista_vazia():
    """Uma entrada vazia deve ser rejeitada, sem inventar resultados."""
    with pytest.raises(ValueError, match="lista"):
        agregar([])