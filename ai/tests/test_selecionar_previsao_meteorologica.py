"""Testes com aquisições fictícias, sem rede e sem dados reais."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from ai.src.adquirir_previsao_meteorologica import adquirir
from ai.src.preparar_meteorologia import UNIDADES
from ai.src.selecionar_previsao_meteorologica import selecionar


@pytest.fixture
def historico():
    """Metadados fictícios para uma instalação de teste."""
    return {
        "no": {
            "no_id": "no_teste",
            "latitude": 40.0,
            "longitude": -8.0,
            "fuso": "Europe/Lisbon",
        }
    }


@pytest.fixture
def emissao():
    """Emissão de teste às 20h UTC, também 20h locais nesta data."""
    return datetime(2026, 11, 16, 20, tzinfo=timezone.utc)


def resposta_ficticia(parametros):
    """Simula as variáveis horárias devolvidas pela Open-Meteo."""
    inicio = datetime.fromisoformat(parametros["start_hour"])
    fim = datetime.fromisoformat(parametros["end_hour"])
    quantidade = int((fim - inicio).total_seconds() / 3600) + 1

    horas = {
        "time": [
            (inicio + timedelta(hours=i)).isoformat(timespec="minutes")
            for i in range(quantidade)
        ]
    }

    for campo in UNIDADES:
        horas[campo] = [0] * quantidade

    return {
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly_units": {"time": "iso8601", **UNIDADES},
        "hourly": horas,
    }


def criar_aquisicao(historico, disponivel):
    """
    Reutiliza o produtor de envelopes para verificar compatibilidade.

    O transporte e o relógio são fictícios: não há pedidos à Internet.
    """
    momentos = iter([
        disponivel - timedelta(seconds=1),
        disponivel,
    ])

    return adquirir(
        historico,
        "no_teste",
        consultar=resposta_ficticia,
        relogio=lambda: next(momentos),
    )


def executar_selecao(documentos, historico, emissao, **opcoes):
    """Encurta as chamadas sem alterar o comportamento do seletor."""
    return selecionar(
        documentos,
        historico,
        "no_teste",
        emissao,
        **opcoes,
    )


@pytest.mark.parametrize(
    "hora,minuto,segundo,aceite",
    [
        (8, 0, 0, True),
        (7, 59, 59, False),
        (19, 55, 0, True),
        (19, 55, 1, False),
        (20, 0, 0, False),
        (20, 58, 0, False),
    ],
)
def test_fronteiras_temporais(
    historico,
    emissao,
    hora,
    minuto,
    segundo,
    aceite,
):
    """Confirma os limites inclusivos e a rejeição de chegadas tardias."""
    disponivel = emissao.replace(
        hour=hora,
        minute=minuto,
        second=segundo,
    )
    documento = criar_aquisicao(historico, disponivel)

    resultado = executar_selecao([documento], historico, emissao)

    assert (resultado["selecionada"] is not None) is aceite
    assert resultado["elegiveis"] == int(aceite)


def test_escolhe_mais_recente_sem_alterar_entrada(historico, emissao):
    antiga = criar_aquisicao(historico, emissao.replace(hour=10))
    recente = criar_aquisicao(
        historico,
        emissao.replace(hour=19, minute=50),
    )
    tardia = criar_aquisicao(
        historico,
        emissao.replace(hour=20, minute=58),
    )

    documentos = [recente, tardia, antiga]
    original = deepcopy(documentos)
    original_historico = deepcopy(historico)

    resultado = executar_selecao(documentos, historico, emissao)

    assert resultado["indice_selecionado"] == 0
    assert resultado["elegiveis"] == 2
    assert len(resultado["rejeitadas"]) == 1
    assert documentos == original
    assert historico == original_historico

    # A seleção é uma cópia independente da entrada.
    resultado["selecionada"]["no"]["latitude"] = 0
    assert documentos == original


def test_empate_mantem_primeiro(historico, emissao):
    documento = criar_aquisicao(historico, emissao.replace(hour=19))

    resultado = executar_selecao(
        [documento, deepcopy(documento)],
        historico,
        emissao,
    )

    assert resultado["elegiveis"] == 2
    assert resultado["indice_selecionado"] == 0


def test_lista_vazia_devolve_indisponivel(historico, emissao):
    resultado = executar_selecao([], historico, emissao)

    assert resultado["estado"] == "indisponivel"
    assert resultado["selecionada"] is None
    assert resultado["indice_selecionado"] is None
    assert resultado["elegiveis"] == 0


@pytest.mark.parametrize(
    "problema",
    [
        "no",
        "localizacao",
        "fuso",
        "dia",
        "historica",
        "endpoint",
        "fronteira",
        "parametros",
        "variaveis",
        "unidade",
        "nulo",
        "hora_em_falta",
        "contagem",
        "sem_fuso",
        "disponibilidade_inconsistente",
        "relogio",
    ],
)
def test_rejeita_candidato_incompativel(historico, emissao, problema):
    documento = criar_aquisicao(historico, emissao.replace(hour=19))
    aquisicao = documento["aquisicao"]

    if problema == "no":
        documento["no"]["no_id"] = "outro_no"
    elif problema == "localizacao":
        documento["no"]["longitude"] = -7.0
    elif problema == "fuso":
        documento["no"]["fuso"] = "Europe/Zurich"
    elif problema == "dia":
        aquisicao["data_alvo_local"] = "2026-11-18"
    elif problema == "historica":
        aquisicao["tipo"] = "meteorologia_historica"
    elif problema == "endpoint":
        aquisicao["endpoint"] = "https://archive-api.open-meteo.com/v1/archive"
    elif problema == "fronteira":
        aquisicao["inicio_alvo_utc"] = "2026-11-17T01:00:00+00:00"
    elif problema == "parametros":
        aquisicao["parametros"]["latitude"] = 41.0
    elif problema == "variaveis":
        aquisicao["parametros"]["hourly"] = "temperature_2m"
    elif problema == "unidade":
        documento["meteorologia"]["hourly_units"]["temperature_2m"] = "°F"
    elif problema == "nulo":
        documento["meteorologia"]["hourly"]["precipitation"][-1] = None
    elif problema == "hora_em_falta":
        for valores in documento["meteorologia"]["hourly"].values():
            valores.pop()
    elif problema == "contagem":
        aquisicao["instantes_recebidos"] = 24
    elif problema == "sem_fuso":
        aquisicao["disponivel_desde_utc"] = "2026-11-16T19:00:00"
    elif problema == "disponibilidade_inconsistente":
        aquisicao["disponivel_desde_utc"] = "2026-11-16T18:00:00+00:00"
    elif problema == "relogio":
        aquisicao["inicio_consulta_utc"] = "2026-11-16T19:01:00+00:00"

    resultado = executar_selecao([documento], historico, emissao)

    assert resultado["estado"] == "indisponivel"
    assert resultado["selecionada"] is None
    assert len(resultado["rejeitadas"]) == 1
    assert resultado["rejeitadas"][0]["motivo"]


def test_rejeitada_nao_impede_outra_valida(historico, emissao):
    valida = criar_aquisicao(historico, emissao.replace(hour=19))
    historica = deepcopy(valida)
    historica["aquisicao"]["tipo"] = "meteorologia_historica"

    resultado = executar_selecao(
        [historica, valida],
        historico,
        emissao,
    )

    assert resultado["indice_selecionado"] == 1
    assert resultado["elegiveis"] == 1
    assert len(resultado["rejeitadas"]) == 1


def test_parametros_configuraveis(historico, emissao):
    antiga = criar_aquisicao(historico, emissao.replace(hour=9))
    recente = criar_aquisicao(
        historico,
        emissao.replace(hour=19, minute=40),
    )

    # Com idade máxima de 10h, a aquisição das 09h é rejeitada.
    # Com margem de 30min, a aquisição das 19h40 também é rejeitada.
    resultado = executar_selecao(
        [antiga, recente],
        historico,
        emissao,
        margem_minutos=30,
        idade_maxima_horas=10,
    )

    assert resultado["selecionada"] is None
    assert len(resultado["rejeitadas"]) == 2


@pytest.mark.parametrize(
    "opcoes",
    [
        {"margem_minutos": -1},
        {"margem_minutos": True},
        {"margem_minutos": float("nan")},
        {"idade_maxima_horas": 0},
        {"idade_maxima_horas": float("inf")},
        {"idade_maxima_horas": "12"},
        {"margem_minutos": 61, "idade_maxima_horas": 1},
    ],
)
def test_rejeita_limites_invalidos(historico, emissao, opcoes):
    with pytest.raises(ValueError):
        executar_selecao([], historico, emissao, **opcoes)


def test_rejeita_emissao_sem_fuso(historico):
    with pytest.raises(ValueError, match="fuso"):
        executar_selecao(
            [],
            historico,
            datetime(2026, 11, 16, 20),
        )


@pytest.mark.parametrize("fuso", ["Europe/Lisbon", "Europe/Zurich"])
@pytest.mark.parametrize(
    "mes,dia,horas",
    [(3, 28, 23), (10, 24, 25)],
)
def test_dia_alvo_com_mudanca_de_hora(historico, fuso, mes, dia, horas):
    """A seleção preserva as 23 ou 25 horas do dia civil seguinte."""
    historico["no"]["fuso"] = fuso

    emissao_local = datetime(
        2026,
        mes,
        dia,
        20,
        tzinfo=ZoneInfo(fuso),
    )
    emissao_utc = emissao_local.astimezone(timezone.utc)

    documento = criar_aquisicao(
        historico,
        emissao_utc - timedelta(minutes=10),
    )

    resultado = executar_selecao(
        [documento],
        historico,
        emissao_local,
    )

    assert resultado["estado"] == "disponivel"
    assert (
        resultado["selecionada"]["aquisicao"]["intervalos_horarios"]
        == horas
    )

    inicio = datetime.fromisoformat(resultado["inicio_alvo_utc"])
    fim = datetime.fromisoformat(resultado["fim_alvo_exclusivo_utc"])

    assert (fim - inicio).total_seconds() == horas * 3600
    assert resultado["emissao_utc"] == emissao_utc.isoformat()


def test_idade_contada_ate_emissao(historico, emissao):
    """Uma aquisição com 12h05 não passa por estar a 12h do corte."""
    documento = criar_aquisicao(
        historico,
        emissao - timedelta(hours=12, minutes=5),
    )

    resultado = executar_selecao([documento], historico, emissao)

    assert resultado["selecionada"] is None
    assert "antiga" in resultado["rejeitadas"][0]["motivo"]