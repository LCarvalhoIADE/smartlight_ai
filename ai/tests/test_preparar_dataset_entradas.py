"""Testes do contrato das entradas; reutiliza fontes fictícias já existentes."""

import csv
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from ai.src import preparar_dataset_entradas as modulo
from ai.src.preparar_contexto_emissao import associar
from ai.tests.test_preparar_contexto_emissao import criar_caso, previsao


REFERENCIA = {
    "origem_energia": "estimativa_pwm_potencia_assumida",
    "tensao_assumida_v": None,
    "potencia_referencia_mW": 10.0,
    "limite_intervalo_segundos": 30,
}


def criar_contexto(
    horas=None, dia="2026-11-17", fuso="Europe/Lisbon"
):
    historico, emissao = criar_caso(dia, fuso)
    documento = previsao(
        historico, emissao - timedelta(hours=1)
    )

    contexto = associar(
        historico, [documento], "no_teste", "sala", dia,
        metodo="pwm", potencia_referencia_mw=10,
    )

    if horas is not None:
        modelo = contexto["energia_historica"]["resumos"][0]
        contexto["energia_historica"]["resumos"] = [
            {
                **modelo,
                "hora_utc": hora,
                "energia_mWh": energia,
                "energia_Wh": (
                    None if energia is None else energia / 1000
                ),
                "segundos_integrados": segundos,
                "segundos_excluidos": 0,
                "cobertura_proporcao": segundos / 3600,
                "hora_completa": segundos == 3600,
            }
            for hora, energia, segundos in horas
        ]

    return contexto


def test_janela_cobertura_medias_e_antiguidade():
    contexto = criar_contexto([
        ("2026-11-10T18:00:00+00:00", 9, 3600),  # Antes da janela.
        ("2026-11-10T19:00:00+00:00", 2, 3600),  # Fronteira incluída.
        ("2026-11-11T19:00:00+00:00", 6, 3600),
        ("2026-11-13T04:00:00+00:00", 1, 1800),  # Fora da média.
        ("2026-11-14T04:00:00+00:00", None, 0),
        ("2026-11-17T18:00:00+00:00", 4, 3600),
        ("2026-11-17T19:00:00+00:00", 1, 900),   # Depois da janela.
    ])
    original = deepcopy(contexto)

    resultado = modulo.construir(contexto, REFERENCIA)
    cobertura = resultado["cobertura"]
    por_hora = {
        linha["hora_local"]: linha for linha in resultado["linhas"]
    }

    assert (
        cobertura["inicio_janela_utc"]
        == "2026-11-10T19:00:00+00:00"
    )
    assert (
        cobertura["fim_janela_exclusivo_utc"]
        == "2026-11-17T19:00:00+00:00"
    )
    assert cobertura["horas_previstas_janela"] == 168
    assert cobertura["horas_completas_janela"] == 3
    assert cobertura["horas_parciais_janela"] == 1
    assert cobertura["horas_sem_cobertura_janela"] == 164
    assert cobertura["cobertura_energetica_proporcao"] == pytest.approx(
        3.5 / 168
    )
    assert por_hora[19]["energia_media_mesma_hora_mWh"] == 4
    assert por_hora[19]["n_horas_mesma_hora"] == 2
    assert por_hora[4]["energia_media_mesma_hora_mWh"] is None
    assert por_hora[4]["n_horas_mesma_hora"] == 0
    assert por_hora[0]["energia_ultima_hora_mWh"] == 4
    assert por_hora[0]["idade_ultima_hora_h"] == 1

    resultado["selecao_meteorologica"]["rejeitadas"].append({
        "motivo": "teste"
    })
    assert contexto == original


def test_janela_configuravel_sem_historico_nao_inventa_zero():
    contexto = criar_contexto([
        ("2026-11-10T19:00:00+00:00", 2, 3600),
    ])

    resultado = modulo.construir(
        contexto, REFERENCIA, janela_dias=1
    )

    assert resultado["cobertura"]["horas_sem_cobertura_janela"] == 24

    for linha in resultado["linhas"]:
        assert linha["energia_ultima_hora_mWh"] is None
        assert linha["idade_ultima_hora_h"] is None
        assert linha["energia_media_mesma_hora_mWh"] is None
        assert linha["estado_historico"] == "sem_horas_completas"


def test_zero_completo_e_preservado():
    contexto = criar_contexto([
        ("2026-11-17T18:00:00+00:00", 0, 3600),
    ])

    linhas = modulo.construir(contexto, REFERENCIA)["linhas"]
    hora = next(
        linha for linha in linhas if linha["hora_local"] == 18
    )

    assert hora["energia_media_mesma_hora_mWh"] == 0
    assert hora["energia_ultima_hora_mWh"] == 0
    assert hora["n_horas_mesma_hora"] == 1


@pytest.mark.parametrize("fuso", ["Europe/Lisbon", "Europe/Zurich"])
@pytest.mark.parametrize(
    "dia,quantidade",
    [("2026-03-28", 23), ("2026-10-24", 25)],
)
def test_dataset_preserva_calendario_nas_mudancas_de_hora(
    fuso, dia, quantidade
):
    contexto = criar_contexto(dia=dia, fuso=fuso)
    resultado = modulo.construir(contexto, REFERENCIA)
    linhas = resultado["linhas"]

    assert len(linhas) == quantidade
    assert len({
        (
            linha["no_id"],
            linha["divisao"],
            linha["emissao_utc"],
            linha["inicio_hora_alvo_utc"],
        )
        for linha in linhas
    }) == quantidade

    assert len({
        linha["inicio_hora_alvo_local"] for linha in linhas
    }) == quantidade

    assert resultado["cobertura"]["horas_previstas_janela"] == 168
    assert all(linha["dia_semana"] == 6 for linha in linhas)


def test_horas_historicas_repetidas_contam_separadamente():
    contexto = criar_contexto(
        [
            ("2026-10-25T00:00:00+00:00", 2, 3600),
            ("2026-10-25T01:00:00+00:00", 6, 3600),
        ],
        dia="2026-10-26",
    )

    linhas = modulo.construir(contexto, REFERENCIA)["linhas"]
    hora = next(
        linha for linha in linhas if linha["hora_local"] == 1
    )

    assert hora["n_horas_mesma_hora"] == 2
    assert hora["energia_media_mesma_hora_mWh"] == 4


def test_sem_meteorologia_preserva_as_linhas_e_os_nulos():
    historico, _ = criar_caso()

    resultado = modulo.preparar(
        historico, [], "no_teste", "sala", "2026-11-17",
        metodo="pwm", potencia_referencia_mw=10,
    )

    assert len(resultado["linhas"]) == 24

    for linha in resultado["linhas"]:
        assert linha["estado_meteorologia"] == "indisponivel"
        assert linha["meteo_temperature_2m"] is None
        assert linha["meteo_disponivel_desde_utc"] is None
        assert linha["horas_completas_janela"] == 1


def test_intervalos_de_apoio_fora_da_janela_fecham_a_primeira_hora():
    historico, emissao = criar_caso()
    documento = previsao(
        historico, emissao - timedelta(hours=1)
    )
    inicio = int(
        datetime(2026, 11, 10, 19, tzinfo=timezone.utc).timestamp()
    )
    modelo = historico["leituras"][0]

    historico["leituras"] = [
        {
            **modelo,
            "ts": inicio + segundo,
            "recebido_ts": inicio + segundo,
        }
        for segundo in range(-10, 3606, 15)
    ]
    historico["de"] = inicio - 10
    historico["ate"] = inicio + 3605

    resultado = modulo.preparar(
        historico, [documento], "no_teste", "sala", "2026-11-17",
        metodo="pwm", potencia_referencia_mw=10,
    )
    hora = next(
        linha for linha in resultado["linhas"]
        if linha["hora_local"] == 19
    )

    assert hora["n_horas_mesma_hora"] == 1
    assert hora["energia_media_mesma_hora_mWh"] == pytest.approx(10)


def test_dados_do_dia_alvo_nao_alteram_as_entradas():
    historico, emissao = criar_caso()
    documentos = [
        previsao(historico, emissao - timedelta(hours=1))
    ]
    opcoes = {
        "metodo": "pwm",
        "potencia_referencia_mw": 10,
    }

    antes = modulo.preparar(
        historico, documentos, "no_teste", "sala", "2026-11-17",
        **opcoes,
    )

    futuro = int((emissao + timedelta(days=1)).timestamp())
    historico["ate"] = futuro
    historico["leituras"].append({
        **historico["leituras"][0],
        "ts": futuro,
        "recebido_ts": futuro,
        "led_pct": 0,
    })
    original = deepcopy(historico)

    depois = modulo.preparar(
        historico, documentos, "no_teste", "sala", "2026-11-17",
        **opcoes,
    )

    assert antes["linhas"] == depois["linhas"]
    assert historico == original
    assert all(
        "energia_mWh" not in linha
        and "alvo_energia_mWh" not in linha
        for linha in depois["linhas"]
    )


def test_rejeita_mistura_de_referencias_no_resumo():
    contexto = criar_contexto([
        ("2026-11-16T18:00:00+00:00", 2, 3600),
        ("2026-11-17T18:00:00+00:00", 4, 3600),
    ])
    contexto["energia_historica"]["resumos"][1][
        "potencia_referencia_mW"
    ] = 20

    with pytest.raises(ValueError):
        modulo.construir(contexto, REFERENCIA)


def test_dataset_preserva_corrente_medida_e_tensao_assumida():
    historico, _ = criar_caso()

    resultado = modulo.preparar(
        historico, [], "no_teste", "sala", "2026-11-17",
        metodo="corrente", tensao_v=2,
    )
    linha = resultado["linhas"][0]

    assert linha["origem_energia"] == "corrente_medida_tensao_assumida"
    assert linha["tensao_assumida_v"] == 2
    assert linha["potencia_referencia_mW"] is None
    assert linha["energia_ultima_hora_mWh"] == pytest.approx(10)


@pytest.mark.parametrize("janela", [0, -1, True, 1.5, 10**30])
def test_janela_invalida(janela):
    with pytest.raises(ValueError, match="[Jj]anela"):
        modulo.construir(criar_contexto(), REFERENCIA, janela)


@pytest.fixture
def repositorio_temporario(tmp_path, monkeypatch):
    """Git real, apenas numa pasta temporária com dados fictícios."""
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        check=True,
    )
    (tmp_path / ".gitignore").write_text(
        "/ai/data/processed/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(modulo, "AI_DIR", tmp_path / "ai")
    return tmp_path


def test_csv_preserva_zero_nulos_e_recusa_substituir(
    repositorio_temporario,
):
    raiz = repositorio_temporario
    destino = raiz / "ai/data/processed/entradas.csv"

    contexto = criar_contexto([
        ("2026-11-17T18:00:00+00:00", 0, 3600),
    ])
    linhas = modulo.construir(contexto, REFERENCIA)["linhas"]

    modulo.guardar(linhas, destino)
    original = destino.read_bytes()

    with destino.open(encoding="utf-8", newline="") as ficheiro:
        lidas = list(csv.DictReader(ficheiro))

    assert len(lidas) == 24
    assert lidas[0]["energia_media_mesma_hora_mWh"] == ""
    assert float(lidas[18]["energia_media_mesma_hora_mWh"]) == 0

    with pytest.raises(ValueError, match="existe"):
        modulo.guardar(linhas, destino)

    assert destino.read_bytes() == original


def test_recusa_destino_nao_ignorado(repositorio_temporario):
    raiz = repositorio_temporario
    (raiz / ".gitignore").write_text("", encoding="utf-8")
    destino = raiz / "ai/data/processed/entradas.csv"

    with pytest.raises(ValueError, match="ignorado"):
        modulo.guardar([{"teste": 1}], destino)

    assert not destino.exists()


def test_recusa_caminho_ja_acompanhado_pelo_git(
    repositorio_temporario,
):
    raiz = repositorio_temporario
    destino = raiz / "ai/data/processed/entradas.csv"
    destino.parent.mkdir(parents=True)
    destino.write_text("anterior", encoding="utf-8")

    subprocess.run(
        ["git", "add", "-f", str(destino)],
        cwd=raiz,
        check=True,
    )

    # Continua acompanhado no índice deste Git temporário.
    destino.unlink()

    with pytest.raises(ValueError, match="ignorado"):
        modulo.guardar([{"teste": 1}], destino)

    assert not destino.exists()


@pytest.mark.parametrize(
    "relativo",
    ["fora.csv", "ai/data/processed/saida.json"],
)
def test_recusa_local_ou_extensao_errada(
    repositorio_temporario, relativo
):
    with pytest.raises(ValueError, match="CSV"):
        modulo.guardar(
            [{"teste": 1}],
            repositorio_temporario / relativo,
        )


def test_cli_sem_destino_nao_cria_ficheiros(
    tmp_path, monkeypatch, capsys
):
    historico, emissao = criar_caso()
    documento = previsao(
        historico, emissao - timedelta(hours=1)
    )

    origem = tmp_path / "historico.json"
    meteo = tmp_path / "previsao.json"

    origem.write_text(
        json.dumps(historico), encoding="utf-8-sig"
    )
    meteo.write_text(
        json.dumps(documento), encoding="utf-8"
    )
    original = {
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

    assert "Entradas horárias: 24" in capsys.readouterr().out
    assert {
        p.name: p.read_bytes() for p in tmp_path.iterdir()
    } == original