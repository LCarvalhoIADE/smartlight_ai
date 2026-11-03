"""Testa o cruzamento temporal com dados fictícios.

Não utiliza ficheiros reais nem faz pedidos à Internet.
"""

from copy import deepcopy

import pytest

from ai.src.cruzar_meteorologia import cruzar


@pytest.fixture
def resumos():
    """Cria um resumo fictício para o intervalo das 23:00 às 00:00."""
    return [{
        "no_id": "no3",
        "divisao": "teste",
        "hora_utc": "2026-01-01T23:00:00+00:00",
        "numero_leituras": 2,
        "primeira_leitura_utc": "2026-01-01T23:10:00+00:00",
        "ultima_leitura_utc": "2026-01-01T23:20:00+00:00",
        "intervalo_observado_segundos": 600,
        "presenca_proporcao": 0.5,
        "led_pct_medio": 50.0,
        "luz_pct_media": None,
        "numero_leituras_luz_pct": 0,
        "numero_leituras_luz_raw": 1,
    }]


@pytest.fixture
def meteorologia():
    """Cria duas horas com valores diferentes para detetar desalinhamentos."""
    return [
        {
            "instante_meteo_utc": "2026-01-01T23:00:00+00:00",
            "cloud_cover": 10,
            "temperature_2m": 12,
            "relative_humidity_2m": 60,
            "cloud_cover_low": 1,
            "cloud_cover_mid": 2,
            "cloud_cover_high": 3,
            "is_day": 0,
            "precipitation": 0.2,
            "diffuse_radiation": 0,
            "shortwave_radiation": 0,
        },
        {
            "instante_meteo_utc": "2026-01-02T00:00:00+00:00",
            "cloud_cover": 80,
            "temperature_2m": 9,
            "relative_humidity_2m": 90,
            "cloud_cover_low": 40,
            "cloud_cover_mid": 50,
            "cloud_cover_high": 60,
            "is_day": 0,
            "precipitation": 1.5,
            # Valores artificiais distintos para verificar a origem
            # de cada campo; não representam meteorologia real.
            "diffuse_radiation": 20,
            "shortwave_radiation": 50,
        },
    ]


def test_alinha_variaveis_na_passagem_do_dia(resumos, meteorologia):
    """Usa 23:00 para valores instantâneos e 00:00 para a hora anterior."""
    resultado = cruzar(resumos, meteorologia)

    assert len(resultado) == 1
    linha = resultado[0]

    # A hora do resumo do ESP32 não deve mudar.
    assert linha["hora_utc"] == "2026-01-01T23:00:00+00:00"

    # Os dois timestamps usados ficam registados na saída.
    assert linha["meteo_instante_utc"] == "2026-01-01T23:00:00+00:00"
    assert linha["meteo_fim_intervalo_utc"] == "2026-01-02T00:00:00+00:00"

    # Estes valores devem vir das 23:00.
    esperados_instantaneos = {
        "cloud_cover": 10,
        "temperature_2m": 12,
        "relative_humidity_2m": 60,
        "cloud_cover_low": 1,
        "cloud_cover_mid": 2,
        "cloud_cover_high": 3,
        "is_day": 0,
    }
    for campo, valor in esperados_instantaneos.items():
        assert linha[f"meteo_{campo}"] == valor

    # Estes valores devem vir das 00:00 do dia seguinte.
    assert linha["meteo_precipitation"] == 1.5
    assert linha["meteo_diffuse_radiation"] == 20
    assert linha["meteo_shortwave_radiation"] == 50


def test_preserva_entradas_e_hora_parcial(resumos, meteorologia):
    """O cruzamento não altera as fontes nem completa a hora do ESP32."""
    original_resumos = deepcopy(resumos)
    original_meteo = deepcopy(meteorologia)

    resultado = cruzar(resumos, meteorologia)

    # Todos os campos originais do resumo devem ser preservados.
    for campo, valor in original_resumos[0].items():
        assert resultado[0][campo] == valor

    assert resumos == original_resumos
    assert meteorologia == original_meteo


def test_preserva_nulos_meteorologicos(resumos, meteorologia):
    """Uma medição ausente não deve tornar-se zero."""
    meteorologia[0]["temperature_2m"] = None
    meteorologia[1]["precipitation"] = None

    resultado = cruzar(resumos, meteorologia)

    assert resultado[0]["meteo_temperature_2m"] is None
    assert resultado[0]["meteo_precipitation"] is None

    # Zero continua a ser um valor válido.
    assert resultado[0]["meteo_is_day"] == 0


@pytest.mark.parametrize("indice_removido", [0, 1])
def test_rejeita_hora_meteorologica_em_falta(
    resumos, meteorologia, indice_removido
):
    """Exige tanto a hora inicial como a hora final do intervalo."""
    del meteorologia[indice_removido]

    with pytest.raises(ValueError, match="Falta meteorologia"):
        cruzar(resumos, meteorologia)


def test_rejeita_timestamp_meteorologico_duplicado(resumos, meteorologia):
    """Não permite escolher silenciosamente entre duas horas iguais."""
    meteorologia.append(deepcopy(meteorologia[0]))

    with pytest.raises(ValueError, match="meteorológico duplicado"):
        cruzar(resumos, meteorologia)


def test_rejeita_resumo_duplicado(resumos, meteorologia):
    """Não permite repetir a mesma combinação de nó, divisão e hora."""
    resumos.append(deepcopy(resumos[0]))

    with pytest.raises(ValueError, match="Resumo horário duplicado"):
        cruzar(resumos, meteorologia)


def test_rejeita_outro_no(resumos, meteorologia):
    """Evita aplicar a meteorologia do no3 a outra instalação."""
    resumos[0]["no_id"] = "no2"

    with pytest.raises(ValueError, match="configurado para no3"):
        cruzar(resumos, meteorologia)


def test_mantem_divisoes_distintas(resumos, meteorologia):
    """Duas divisões do mesmo nó podem partilhar a meteorologia exterior."""
    segunda = deepcopy(resumos[0])
    segunda["divisao"] = "outra_divisao"
    resumos.append(segunda)

    resultado = cruzar(resumos, meteorologia)

    assert len(resultado) == 2
    assert {linha["divisao"] for linha in resultado} == {
        "teste", "outra_divisao"
    }
    assert all(linha["meteo_precipitation"] == 1.5 for linha in resultado)


@pytest.mark.parametrize(
    "hora",
    [
        "2026-01-01T23:00:00",        # Falta o fuso.
        "2026-01-01T23:00:00+01:00",  # Fuso diferente de UTC.
        "2026-01-01T23:30:00+00:00",  # Não é o início da hora.
        "data-invalida",              # Texto sem uma data válida.
    ],
)
def test_rejeita_hora_invalida_no_resumo(resumos, meteorologia, hora):
    """Impede associações com timestamps inválidos ou ambíguos."""
    resumos[0]["hora_utc"] = hora

    with pytest.raises(ValueError):
        cruzar(resumos, meteorologia)


@pytest.mark.parametrize("entrada", ["resumos", "meteorologia"])
def test_rejeita_lista_vazia(resumos, meteorologia, entrada):
    """São necessárias as duas fontes para efetuar o cruzamento."""
    if entrada == "resumos":
        resumos = []
    else:
        meteorologia = []

    with pytest.raises(ValueError, match="lista não vazia"):
        cruzar(resumos, meteorologia)