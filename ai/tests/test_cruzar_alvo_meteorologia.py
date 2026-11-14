"""Testa o cruzamento usando exclusivamente dados fictícios."""

import csv
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from ai.src import cruzar_alvo_meteorologia as modulo
from ai.src.preparar_meteorologia import UNIDADES


@pytest.fixture
def historico():
    """Localização fictícia, sem dados reais dos colegas."""

    return {
        "no": {
            "no_id": "no_teste",
            "latitude": 40.0,
            "longitude": -8.0,
            "fuso": "Europe/Lisbon",
        }
    }


@pytest.fixture
def alvos():
    """Uma hora com energia válida e cobertura completa."""

    return [{
        "no_id": "no_teste",
        "divisao": "sala",
        "hora_utc": "2026-10-01T00:00:00+00:00",
        "energia_mWh": 2.0,
        "energia_Wh": 0.002,
        "segundos_integrados": 3600,
        "segundos_excluidos": 0,
        "cobertura_proporcao": 1.0,
        "tensao_assumida_v": 3.3,
        "potencia_referencia_mW": None,
        "limite_intervalo_segundos": 30,
        "origem_energia": "corrente_medida_tensao_assumida",
    }]


@pytest.fixture
def documento(historico):
    """Resposta meteorológica fictícia com o formato da aquisição."""

    inicio = datetime(2026, 10, 1, tzinfo=timezone.utc)
    horas = {
        "time": [
            (inicio + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
            for i in range(48)
        ]
    }

    for campo in UNIDADES:
        horas[campo] = [0] * 48

    # Valores diferentes permitem verificar o alinhamento:
    # temperatura em T, precipitação e radiação em T+1.
    horas["temperature_2m"][0] = 12
    horas["temperature_2m"][1] = 15
    horas["precipitation"][0] = 9
    horas["precipitation"][1] = 2
    horas["shortwave_radiation"][0] = 40
    horas["shortwave_radiation"][1] = 80

    return {
        "no": deepcopy(historico["no"]),
        "aquisicao": {
            "tipo": "meteorologia_historica",
            "inicio_alvo_utc": "2026-10-01T00:00:00+00:00",
            "fim_alvo_exclusivo_utc": "2026-10-02T00:00:00+00:00",
            "parametros": {
                "latitude": 40.0,
                "longitude": -8.0,
                "timezone": "GMT",
                "start_date": "2026-10-01",
                "end_date": "2026-10-02",
            },
        },
        "meteorologia": {
            # A célula da grelha pode diferir do ponto pedido.
            "latitude": 40.01,
            "longitude": -8.01,
            "timezone": "GMT",
            "utc_offset_seconds": 0,
            "hourly_units": {"time": "iso8601", **UNIDADES},
            "hourly": horas,
        },
    }


def executar(alvos, documento, historico):
    """Facilita a chamada repetida ao cruzamento."""

    return modulo.cruzar_alvo(
        alvos, documento, historico, "no_teste"
    )


def test_alinha_instantes_e_preserva_entradas(alvos, documento, historico):
    """Verifica T/T+1 e garante que as fontes não são modificadas."""

    originais = deepcopy((alvos, documento, historico))
    linhas = executar(alvos, documento, historico)
    linha = linhas[0]

    assert len(linhas) == 1
    assert linha["energia_mWh"] == 2
    assert linha["meteo_temperature_2m"] == 12
    assert linha["meteo_precipitation"] == 2
    assert linha["meteo_shortwave_radiation"] == 80
    assert linha["meteo_instante_utc"] == "2026-10-01T00:00:00+00:00"
    assert linha["meteo_fim_intervalo_utc"] == "2026-10-01T01:00:00+00:00"
    assert (alvos, documento, historico) == originais


def test_preserva_zero_e_origem_pwm(alvos, documento, historico):
    """Energia zero válida e potência assumida mantêm o seu significado."""

    alvos[0].update({
        "energia_mWh": 0,
        "energia_Wh": 0,
        "origem_energia": "estimativa_pwm_potencia_assumida",
        "tensao_assumida_v": None,
        "potencia_referencia_mW": 17.9,
    })

    linha = executar(alvos, documento, historico)[0]

    assert linha["energia_mWh"] == 0
    assert linha["tensao_assumida_v"] is None
    assert linha["potencia_referencia_mW"] == 17.9
    assert linha["origem_energia"] == "estimativa_pwm_potencia_assumida"


def test_preserva_lacunas_e_separa_divisoes(alvos, documento, historico):
    """Não cria horas intermédias e mantém divisões distintas."""

    alvos.extend([
        {**alvos[0], "hora_utc": "2026-10-01T03:00:00+00:00"},
        {**alvos[0], "divisao": "quarto"},
    ])

    linhas = executar(alvos, documento, historico)

    assert len(linhas) == 3
    assert {linha["divisao"] for linha in linhas} == {"sala", "quarto"}
    assert {linha["hora_utc"] for linha in linhas} == {
        "2026-10-01T00:00:00+00:00",
        "2026-10-01T03:00:00+00:00",
    }


def test_fecha_ultima_hora_do_dia(alvos, documento, historico):
    """A hora 23–00 utiliza meteorologia da meia-noite seguinte."""

    alvos[0]["hora_utc"] = "2026-10-01T23:00:00+00:00"
    documento["meteorologia"]["hourly"]["precipitation"][24] = 7

    linha = executar(alvos, documento, historico)[0]

    assert linha["meteo_precipitation"] == 7
    assert linha["meteo_fim_intervalo_utc"] == "2026-10-02T00:00:00+00:00"


@pytest.mark.parametrize("origem", ["alvo", "documento", "historico"])
def test_rejeita_no_diferente(alvos, documento, historico, origem):
    """Não permite misturar instalações."""

    if origem == "alvo":
        alvos[0]["no_id"] = "outro_no"
    elif origem == "documento":
        documento["no"]["no_id"] = "outro_no"
    else:
        historico["no"]["no_id"] = "outro_no"

    with pytest.raises(ValueError):
        executar(alvos, documento, historico)


@pytest.mark.parametrize("origem", ["no", "pedido"])
def test_rejeita_localizacao_diferente(alvos, documento, historico, origem):
    """Confirma tanto o metadado do nó como a coordenada pedida."""

    if origem == "no":
        documento["no"]["longitude"] = -7
    else:
        documento["aquisicao"]["parametros"]["longitude"] = -7

    with pytest.raises(ValueError, match="coordenadas"):
        executar(alvos, documento, historico)


def test_rejeita_fuso_diferente(alvos, documento, historico):
    """Uma divergência nos metadados deve ser investigada."""

    documento["no"]["fuso"] = "Europe/Zurich"

    with pytest.raises(ValueError, match="fuso"):
        executar(alvos, documento, historico)


def test_rejeita_previsao_como_historico(alvos, documento, historico):
    """Impede confundir previsões com dados históricos."""

    documento["aquisicao"]["tipo"] = "previsao_meteorologica"

    with pytest.raises(ValueError, match="histórica"):
        executar(alvos, documento, historico)


def test_rejeita_datas_do_pedido_incoerentes(alvos, documento, historico):
    """A margem declarada deve corresponder às datas pedidas."""

    documento["aquisicao"]["parametros"]["end_date"] = "2026-10-01"

    with pytest.raises(ValueError, match="Datas"):
        executar(alvos, documento, historico)


def test_rejeita_alvo_fora_do_periodo(alvos, documento, historico):
    """Não usa as horas da margem como se pertencessem ao período alvo."""

    alvos[0]["hora_utc"] = "2026-10-02T00:00:00+00:00"

    with pytest.raises(ValueError, match="fora do período"):
        executar(alvos, documento, historico)


def test_rejeita_alvo_parcial(alvos, documento, historico):
    """Não descarta silenciosamente uma hora incompleta."""

    alvos[0]["segundos_integrados"] = 1800
    alvos[0]["cobertura_proporcao"] = 0.5

    with pytest.raises(ValueError, match="cobertura completa"):
        executar(alvos, documento, historico)


def test_rejeita_duplicados(alvos, documento, historico):
    """Reutiliza a verificação de duplicados do seletor energético."""

    alvos.append(deepcopy(alvos[0]))

    with pytest.raises(ValueError, match="duplicado"):
        executar(alvos, documento, historico)


def test_rejeita_fronteira_meteorologica_ausente(alvos, documento, historico):
    """Uma série contínua mas demasiado curta não chega ao cruzamento."""

    alvos[0]["hora_utc"] = "2026-10-01T23:00:00+00:00"

    for campo, valores in documento["meteorologia"]["hourly"].items():
        documento["meteorologia"]["hourly"][campo] = valores[:24]

    with pytest.raises(ValueError, match="Falta meteorologia"):
        executar(alvos, documento, historico)


@pytest.mark.parametrize(
    "campo,indice",
    [("temperature_2m", 0), ("precipitation", 1)],
)
def test_rejeita_nulo_necessario(alvos, documento, historico, campo, indice):
    """Não transforma uma ausência meteorológica em zero."""

    documento["meteorologia"]["hourly"][campo][indice] = None

    with pytest.raises(ValueError, match="Meteorologia ausente"):
        executar(alvos, documento, historico)


def test_nao_exige_nulos_fora_do_cruzamento(alvos, documento, historico):
    """Um valor fora das horas utilizadas não altera o resultado."""

    documento["meteorologia"]["hourly"]["temperature_2m"][47] = None

    assert len(executar(alvos, documento, historico)) == 1


def test_csv_e_recusa_substituicao(
    alvos, documento, historico, tmp_path, monkeypatch
):
    """Exporta em pasta temporária e preserva o primeiro ficheiro."""

    monkeypatch.setattr(modulo, "AI_DIR", tmp_path / "ai")
    destino = tmp_path / "ai/data/processed/cruzado.csv"
    linhas = executar(alvos, documento, historico)

    modulo.guardar(linhas, destino)
    original = destino.read_bytes()

    with destino.open(encoding="utf-8", newline="") as ficheiro:
        guardadas = list(csv.DictReader(ficheiro))

    assert len(guardadas) == 1
    assert guardadas[0]["potencia_referencia_mW"] == ""
    assert guardadas[0]["meteo_tipo"] == "meteorologia_historica"

    with pytest.raises(ValueError, match="já existe"):
        modulo.guardar(linhas, destino)

    assert destino.read_bytes() == original


def test_rejeita_destino_fora_de_processed(
    alvos, documento, historico, tmp_path, monkeypatch
):
    """Não guarda resultados noutras pastas."""

    monkeypatch.setattr(modulo, "AI_DIR", tmp_path / "ai")
    linhas = executar(alvos, documento, historico)

    with pytest.raises(ValueError, match="ai/data/processed"):
        modulo.guardar(linhas, tmp_path / "fora.csv")


@pytest.mark.parametrize(
    "texto",
    [
        "no_id,no_id\nno_teste,no_teste\n",
        "no_id,divisao\nno_teste\n",
        "no_id,divisao\nno_teste,sala,extra\n",
    ],
)
def test_rejeita_csv_malformado(tmp_path, texto):
    """Rejeita colunas repetidas ou quantidades incorretas de campos."""

    caminho = tmp_path / "alvo.csv"
    caminho.write_text(texto, encoding="utf-8")

    with pytest.raises(ValueError):
        modulo.ler_alvo(caminho)