"""Testes da preparação meteorológica com dados fictícios.

Não fazem pedidos à Internet nem utilizam os ficheiros reais.
"""

from copy import deepcopy

import pytest

from ai.src.preparar_meteorologia import preparar_meteorologia


@pytest.fixture
def meteo():
    """Cria duas horas fictícias com as dez variáveis esperadas."""

    # As unidades são escritas explicitamente para que o teste
    # possa detetar alterações inesperadas nas unidades do módulo.
    return {
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly_units": {
            "time": "iso8601",
            "cloud_cover": "%",
            "temperature_2m": "°C",
            "precipitation": "mm",
            "relative_humidity_2m": "%",
            "cloud_cover_low": "%",
            "cloud_cover_mid": "%",
            "cloud_cover_high": "%",
            "is_day": "",
            "diffuse_radiation": "W/m²",
            "shortwave_radiation": "W/m²",
        },
        "hourly": {
            "time": ["2026-01-01T10:00", "2026-01-01T11:00"],
            "cloud_cover": [0, 100],
            "temperature_2m": [-2.5, 5.0],
            "precipitation": [0, 1.2],
            "relative_humidity_2m": [60, 80],
            "cloud_cover_low": [0, 30],
            "cloud_cover_mid": [0, 40],
            "cloud_cover_high": [0, 50],
            "is_day": [1, 1],
            "diffuse_radiation": [20, 30],
            "shortwave_radiation": [100, 120],
        },
    }


def test_prepara_e_preserva_entrada(meteo):
    """Confirma UTC explícito, valores preservados e entrada intacta."""
    original = deepcopy(meteo)

    resultado = preparar_meteorologia(meteo)

    assert len(resultado) == 2

    # Os timestamps da fonte mantêm a mesma hora.
    # Apenas acrescentamos a identificação explícita de UTC.
    assert [linha["instante_meteo_utc"] for linha in resultado] == [
        "2026-01-01T10:00:00+00:00",
        "2026-01-01T11:00:00+00:00",
    ]

    # Verifica todas as variáveis, sem depender da ordem no JSON.
    for indice, linha in enumerate(resultado):
        for campo, valores in meteo["hourly"].items():
            if campo != "time":
                assert linha[campo] == valores[indice]

    assert meteo == original


def test_preserva_nulo_zero_e_temperatura_negativa(meteo):
    """Distingue ausência, zero válido e temperatura negativa."""
    meteo["hourly"]["diffuse_radiation"][0] = None

    resultado = preparar_meteorologia(meteo)

    assert resultado[0]["diffuse_radiation"] is None
    assert resultado[0]["precipitation"] == 0
    assert resultado[0]["temperature_2m"] == -2.5


def test_aceita_datas_com_utc_explicito(meteo):
    """Aceita os sufixos Z e +00:00 como representações de UTC."""
    meteo["hourly"]["time"] = [
        "2026-01-01T10:00Z",
        "2026-01-01T11:00:00+00:00",
    ]

    resultado = preparar_meteorologia(meteo)

    assert resultado[0]["instante_meteo_utc"].endswith("+00:00")
    assert resultado[1]["instante_meteo_utc"].endswith("+00:00")


def test_rejeita_resposta_de_erro(meteo):
    """Uma resposta de erro não pode ser tratada como meteorologia."""
    meteo["error"] = True
    meteo["reason"] = "Pedido inválido"

    with pytest.raises(ValueError, match="Erro devolvido pela API"):
        preparar_meteorologia(meteo)


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("utc_offset_seconds", 3600),
        ("utc_offset_seconds", True),
        ("timezone", "Europe/Lisbon"),
    ],
)
def test_rejeita_metadados_fora_do_contrato_utc(meteo, campo, valor):
    """Exige o contrato GMT/UTC usado nesta etapa do projeto."""
    meteo[campo] = valor

    with pytest.raises(ValueError, match="UTC"):
        preparar_meteorologia(meteo)


@pytest.mark.parametrize("bloco", ["hourly", "hourly_units"])
def test_rejeita_bloco_em_falta(meteo, bloco):
    """Exige os dados horários e a identificação das unidades."""
    del meteo[bloco]

    with pytest.raises(ValueError, match="hourly"):
        preparar_meteorologia(meteo)


def test_rejeita_variavel_em_falta(meteo):
    """Não aceita uma resposta sem uma das variáveis selecionadas."""
    del meteo["hourly"]["cloud_cover"]

    with pytest.raises(ValueError, match="cloud_cover"):
        preparar_meteorologia(meteo)


def test_rejeita_comprimentos_diferentes(meteo):
    """Cada variável deve ter exatamente um valor por timestamp."""
    meteo["hourly"]["precipitation"] = [0]

    with pytest.raises(ValueError, match="quantidade diferente"):
        preparar_meteorologia(meteo)


def test_rejeita_unidade_inesperada(meteo):
    """Impede interpretar Fahrenheit como se fossem graus Celsius."""
    meteo["hourly_units"]["temperature_2m"] = "°F"

    with pytest.raises(ValueError, match="unidade"):
        preparar_meteorologia(meteo)


@pytest.mark.parametrize(
    "tempos",
    [
        # Timestamp repetido.
        ["2026-01-01T10:00", "2026-01-01T10:00"],

        # Ordem cronológica invertida.
        ["2026-01-01T11:00", "2026-01-01T10:00"],

        # Falta a hora das 11:00.
        ["2026-01-01T10:00", "2026-01-01T12:00"],

        # Instante desalinhado do início da hora.
        ["2026-01-01T10:30", "2026-01-01T11:00"],

        # Data sem componente horária.
        ["2026-01-01", "2026-01-01T11:00"],

        # Data impossível.
        ["2026-02-30T10:00", "2026-02-30T11:00"],

        # Fuso que contradiz os metadados GMT.
        ["2026-01-01T10:00+01:00", "2026-01-01T11:00+01:00"],
    ],
)
def test_rejeita_sequencia_temporal_invalida(meteo, tempos):
    """Deteta erros temporais sem ordenar ou preencher silenciosamente."""
    meteo["hourly"]["time"] = tempos

    with pytest.raises(ValueError, match="Instante"):
        preparar_meteorologia(meteo)


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("cloud_cover", -1),
        ("relative_humidity_2m", 101),
        ("precipitation", -0.1),
        ("diffuse_radiation", -1),
        ("shortwave_radiation", -1),
        ("is_day", 2),
        ("temperature_2m", "frio"),
        ("temperature_2m", True),
        ("temperature_2m", float("nan")),
        ("temperature_2m", float("inf")),
    ],
)
def test_rejeita_valor_meteorologico_invalido(meteo, campo, valor):
    """Verifica limites, tipos e rejeição de números não finitos."""
    meteo["hourly"][campo][0] = valor

    with pytest.raises(ValueError, match=campo):
        preparar_meteorologia(meteo)


def test_rejeita_lista_de_datas_vazia(meteo):
    """Uma resposta sem horas não permite preparar dados."""
    meteo["hourly"]["time"] = []

    with pytest.raises(ValueError, match="lista não vazia"):
        preparar_meteorologia(meteo)


def test_rejeita_entrada_que_nao_e_objeto():
    """A raiz do JSON deve ser um objeto, não uma lista."""
    with pytest.raises(ValueError, match="objeto JSON"):
        preparar_meteorologia([])