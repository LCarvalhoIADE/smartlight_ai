"""Testes da associação por emissão, com fontes inteiramente fictícias."""

import json
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from ai.src import preparar_contexto_emissao as modulo
from ai.src.adquirir_previsao_meteorologica import adquirir
from ai.src.preparar_meteorologia import UNIDADES


def criar_caso(dia="2026-11-17", fuso="Europe/Lisbon"):
    """Cria uma hora histórica completa, anterior às 20h locais."""
    emissao = datetime.combine(
        date.fromisoformat(dia), time(20), tzinfo=ZoneInfo(fuso)
    ).astimezone(timezone.utc)

    base = int((emissao - timedelta(hours=3)).timestamp())

    historico = {
        "no": {
            "no_id": "no_teste",
            "latitude": 40.0,
            "longitude": -8.0,
            "fuso": fuso,
        },
        "de": base,
        "ate": base + 3600,
        "mais": False,
        "leituras": [
            {
                "divisao": "sala",
                "ts": base + segundo,
                "recebido_ts": base + segundo,
                "luz_raw": 1,
                "luz_pct": None,
                "presenca": 1,
                "led_pct": 100,
                "corrente_ma": 5.0,
                "modo": "auto",
            }
            for segundo in range(0, 3601, 15)
        ],
    }
    return historico, emissao


def resposta_ficticia(parametros):
    """Varia os valores por instante para detetar desalinhamentos T/T+1."""
    inicio = datetime.fromisoformat(parametros["start_hour"])
    fim = datetime.fromisoformat(parametros["end_hour"])
    quantidade = int((fim - inicio).total_seconds() / 3600) + 1

    hourly = {
        "time": [
            (inicio + timedelta(hours=i)).isoformat(timespec="minutes")
            for i in range(quantidade)
        ],
    }

    for campo in UNIDADES:
        hourly[campo] = [
            1 if campo == "is_day" else i
            for i in range(quantidade)
        ]

    return {
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly_units": {"time": "iso8601", **UNIDADES},
        "hourly": hourly,
    }


def previsao(historico, disponivel):
    """Usa o adquiridor existente com transporte e relógio fictícios."""
    momentos = iter([disponivel - timedelta(seconds=1), disponivel])
    return adquirir(
        historico,
        "no_teste",
        consultar=resposta_ficticia,
        relogio=lambda: next(momentos),
    )


def executar(historico, documentos, dia="2026-11-17", **opcoes):
    return modulo.associar(
        historico, documentos, "no_teste", "sala", dia,
        metodo="pwm",
        potencia_referencia_mw=10,
        **opcoes,
    )


def test_associacao_preserva_fontes_e_separa_passado_de_futuro():
    historico, emissao = criar_caso()
    documentos = [
        previsao(historico, emissao - timedelta(hours=1))
    ]
    original = deepcopy((historico, documentos))
    resultado = executar(historico, documentos)

    assert resultado["emissao_utc"] == emissao.isoformat()
    assert resultado["data_alvo_local"] == "2026-11-18"
    assert resultado["horas_historicas_completas"] == 1
    assert len(resultado["meteorologia_dia_alvo"]) == 24
    assert resultado["selecao_meteorologica"]["estado"] == "disponivel"

    historicas = resultado["energia_historica"]["resumos"]
    futuras = resultado["meteorologia_dia_alvo"]

    assert (
        max(linha["hora_utc"] for linha in historicas)
        < futuras[0]["hora_utc"]
    )
    assert all("energia_mWh" not in linha for linha in futuras)
    assert all(
        "meteo_temperature_2m" not in linha for linha in historicas
    )

    futuras[0]["meteo_temperature_2m"] = -100
    historicas[0]["energia_mWh"] = -1

    assert (historico, documentos) == original


def test_alinhamento_das_variaveis_e_fronteira_final():
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))
    resultado = executar(historico, [documento])
    horas = resultado["meteorologia_dia_alvo"]

    assert horas[0]["meteo_temperature_2m"] == 0
    assert horas[0]["meteo_cloud_cover"] == 0

    for campo in (
        "precipitation", "diffuse_radiation", "shortwave_radiation"
    ):
        assert horas[0][f"meteo_{campo}"] == 1
        assert horas[-1][f"meteo_{campo}"] == 24

    assert horas[-1]["meteo_temperature_2m"] == 23
    assert (
        horas[-1]["fim_hora_utc"]
        == resultado["fim_alvo_exclusivo_utc"]
    )
    assert (
        resultado["unidades_meteorologicas"]["meteo_precipitation"]
        == "mm"
    )


def test_preserva_origem_por_corrente_medida():
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))

    resultado = modulo.associar(
        historico, [documento], "no_teste", "sala", "2026-11-17",
        metodo="corrente", tensao_v=2,
    )
    hora = resultado["energia_historica"]["resumos"][0]

    assert hora["origem_energia"] == "corrente_medida_tensao_assumida"
    assert hora["energia_horaria_disponivel_mWh"] == pytest.approx(10)
    assert hora["potencia_referencia_mW"] is None


@pytest.mark.parametrize("fuso", ["Europe/Lisbon", "Europe/Zurich"])
@pytest.mark.parametrize(
    "dia,quantidade",
    [
        ("2026-03-28", 23),
        ("2026-10-24", 25),
        ("2026-11-17", 24),
    ],
)
def test_dia_civil_e_horas_legais(fuso, dia, quantidade):
    historico, emissao = criar_caso(dia, fuso)
    documento = previsao(historico, emissao - timedelta(hours=1))
    resultado = executar(historico, [documento], dia)
    horas = resultado["meteorologia_dia_alvo"]

    assert resultado["emissao_utc"] == emissao.isoformat()
    assert len(horas) == quantidade
    assert len({linha["hora_utc"] for linha in horas}) == quantidade
    assert len({linha["hora_local"] for linha in horas}) == quantidade
    assert datetime.fromisoformat(horas[0]["hora_local"]).hour == 0
    assert datetime.fromisoformat(horas[-1]["fim_hora_local"]).hour == 0


@pytest.mark.parametrize(
    "erro",
    [
        "historica",
        "outro_no",
        "coordenadas",
        "dia_alvo",
        "tardia",
        "fronteira",
    ],
)
def test_previsao_incompativel_fica_indisponivel(erro):
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))

    if erro == "historica":
        documento["aquisicao"]["tipo"] = "meteorologia_historica"
    elif erro == "outro_no":
        documento["no"]["no_id"] = "outro"
    elif erro == "coordenadas":
        documento["no"]["latitude"] += 1
    elif erro == "dia_alvo":
        documento["aquisicao"]["data_alvo_local"] = "2026-11-19"
    elif erro == "tardia":
        documento = previsao(
            historico, emissao + timedelta(minutes=1)
        )
    else:
        documento["meteorologia"]["hourly"]["precipitation"][-1] = None

    resultado = executar(historico, [documento])

    assert resultado["selecao_meteorologica"]["estado"] == "indisponivel"
    assert len(resultado["selecao_meteorologica"]["rejeitadas"]) == 1
    assert resultado["meteorologia_dia_alvo"] == []
    assert resultado["horas_historicas_completas"] == 1


def test_sem_previsoes_nao_fabrica_meteorologia():
    historico, _ = criar_caso()
    resultado = executar(historico, [])

    assert resultado["selecao_meteorologica"]["estado"] == "indisponivel"
    assert resultado["meteorologia_dia_alvo"] == []


def test_escolhe_a_aquisicao_elegivel_mais_recente():
    historico, emissao = criar_caso()
    documentos = [
        previsao(historico, emissao - timedelta(hours=3)),
        previsao(historico, emissao - timedelta(hours=2)),
        previsao(historico, emissao + timedelta(minutes=1)),
    ]
    resultado = executar(historico, documentos)

    assert resultado["selecao_meteorologica"]["indice_selecionado"] == 1


@pytest.mark.parametrize(
    "sensores,meteo,completas,estado",
    [
        (10, 5, 0, "disponivel"),
        (5, 10, 1, "indisponivel"),
    ],
)
def test_margens_independentes(sensores, meteo, completas, estado):
    historico, emissao = criar_caso()
    recebido = int((emissao - timedelta(minutes=7)).timestamp())

    for linha in historico["leituras"]:
        linha["recebido_ts"] = recebido

    documento = previsao(historico, emissao - timedelta(minutes=6))

    resultado = executar(
        historico,
        [documento],
        margem_sensores_minutos=sensores,
        margem_meteo_minutos=meteo,
    )

    assert resultado["horas_historicas_completas"] == completas
    assert resultado["selecao_meteorologica"]["estado"] == estado


@pytest.mark.parametrize(
    "idade,estado",
    [(12, "indisponivel"), (14, "disponivel")],
)
def test_idade_meteorologica_configuravel(idade, estado):
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=13))

    resultado = executar(
        historico, [documento], idade_maxima_horas=idade
    )
    assert resultado["selecao_meteorologica"]["estado"] == estado


def test_historico_antigo_sem_rececao_nao_ganha_disponibilidade():
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))

    for linha in historico["leituras"]:
        del linha["recebido_ts"]

    resultado = executar(historico, [documento])

    assert resultado["energia_historica"]["resumos"] == []
    assert resultado["horas_historicas_completas"] == 0
    assert resultado["selecao_meteorologica"]["estado"] == "disponivel"


def test_exclusao_interna_mantem_hora_incompleta():
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))
    historico["leituras"][120]["recebido_ts"] = int(emissao.timestamp())

    resultado = executar(historico, [documento])
    hora = resultado["energia_historica"]["resumos"][0]

    assert hora["segundos_integrados"] == 3570
    assert hora["energia_horaria_disponivel_mWh"] is None
    assert resultado["horas_historicas_completas"] == 0


def test_historico_anterior_nao_e_alinhado_com_a_hora_futura():
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))
    semana = 7 * 86400

    historico["de"] -= semana
    historico["ate"] -= semana

    for linha in historico["leituras"]:
        linha["ts"] -= semana
        linha["recebido_ts"] -= semana

    resultado = executar(historico, [documento])

    assert resultado["horas_historicas_completas"] == 1
    assert (
        resultado["energia_historica"]["resumos"][0]["hora_utc"]
        .startswith("2026-11-10")
    )
    assert (
        resultado["meteorologia_dia_alvo"][0]["hora_utc"]
        .startswith("2026-11-18")
    )


def test_leitura_do_dia_alvo_nao_entra_nas_entradas_historicas():
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))
    futuro = int((emissao + timedelta(days=1)).timestamp())

    historico["ate"] = futuro
    historico["leituras"].append({
        **historico["leituras"][0],
        "ts": futuro,
        "recebido_ts": futuro,
    })
    original = deepcopy(historico)

    resultado = executar(historico, [documento])
    energia = resultado["energia_historica"]

    assert energia["motivos"] == {"recebida_depois_corte": 1}
    assert all(
        linha["hora_utc"] < resultado["emissao_utc"]
        for linha in energia["resumos"]
    )
    assert historico == original


@pytest.mark.parametrize("dia", [None, "20261117", "2026-02-30"])
def test_rejeita_data_emissao_invalida(dia):
    historico, _ = criar_caso()

    with pytest.raises(ValueError, match="[Dd]ata"):
        executar(historico, [], dia)


def test_cli_so_le_ficheiros(tmp_path, monkeypatch, capsys):
    historico, emissao = criar_caso()
    documento = previsao(historico, emissao - timedelta(hours=1))

    origem = tmp_path / "historico.json"
    meteo = tmp_path / "previsao.json"

    origem.write_text(
        json.dumps(historico), encoding="utf-8-sig"
    )
    meteo.write_text(
        json.dumps(documento), encoding="utf-8"
    )
    originais = {
        p.name: p.read_bytes() for p in tmp_path.iterdir()
    }

    monkeypatch.setattr("sys.argv", [
        "programa",
        "--historico", str(origem),
        "--no", "no_teste",
        "--divisao", "sala",
        "--data-emissao", "2026-11-17",
        "--previsoes", str(meteo),
        "--metodo", "pwm",
        "--potencia-referencia-mw", "10",
    ])

    modulo.main()
    texto = capsys.readouterr().out

    assert "Estado da meteorologia: disponivel" in texto
    assert "Intervalos meteorológicos do dia alvo: 24" in texto
    assert {
        p.name: p.read_bytes() for p in tmp_path.iterdir()
    } == originais