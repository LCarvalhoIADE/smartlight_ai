"""Associação posterior com dados fictícios e sem acesso à Internet."""

import csv
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from ai.src import associar_alvos_energia as modulo
from ai.src import preparar_dataset_entradas as dataset
from ai.tests.test_preparar_contexto_emissao import criar_caso, previsao


def criar_lote(dia="2026-11-17", fuso="Europe/Lisbon", metodo="pwm"):
    """Reutiliza o pipeline para criar entradas e uma hora alvo completa."""
    historico, emissao = criar_caso(dia, fuso)
    documento = previsao(historico, emissao - timedelta(hours=1))

    referencia = (
        {"potencia_referencia_mw": 10}
        if metodo == "pwm" else {"tensao_v": 2}
    )

    entradas = dataset.preparar(
        historico, [documento], "no_teste", "sala", dia,
        metodo=metodo, **referencia,
    )["linhas"]

    inicio = datetime.fromisoformat(entradas[0]["inicio_hora_alvo_utc"])
    avaliacao = datetime.fromisoformat(entradas[-1]["fim_hora_alvo_utc"])
    base = int(inicio.timestamp())

    alvo = deepcopy(historico)
    modelo = alvo["leituras"][0]
    alvo.update({
        "de": base,
        "ate": int(avaliacao.timestamp()),
        "leituras": [
            {**modelo, "ts": base + s, "recebido_ts": base + s}
            for s in range(0, 3601, 15)
        ],
    })

    return entradas, alvo, avaliacao


@pytest.fixture
def lote():
    return criar_lote()


def executar(lote, avaliacao=None):
    entradas, historico, momento = lote
    momento = avaliacao or momento

    return modulo.associar(
        entradas, historico, "no_teste", "sala", momento,
        relogio=lambda: momento,
    )


def test_associa_alvo_posterior_e_preserva_entradas(lote):
    original = deepcopy(lote)
    resultado = executar(lote)
    alvo = resultado["alvos"][0]

    assert resultado["estados"] == {"disponivel": 1, "sem_cobertura": 23}
    assert alvo["alvo_energia_mWh"] == pytest.approx(10)
    assert alvo["alvo_energia_Wh"] == pytest.approx(0.01)
    assert alvo["alvo_segundos_integrados"] == 3600

    for entrada, associada in zip(lote[0], resultado["associadas"]):
        assert {campo: associada[campo] for campo in entrada} == entrada

    assert all("energia_ultima_hora_mWh" not in a for a in resultado["alvos"])
    assert lote == original


def test_zero_valido_e_ausencia_sao_distintos(lote):
    for leitura in lote[1]["leituras"]:
        leitura["led_pct"] = 0

    alvos = executar(lote)["alvos"]

    assert alvos[0]["alvo_energia_mWh"] == 0
    assert alvos[1]["alvo_energia_mWh"] is None


def test_chegada_tardia_impede_hora_completa(lote):
    lote[1]["leituras"][-1]["recebido_ts"] = int(lote[2].timestamp()) + 1

    primeiro = executar(lote)
    alvo = primeiro["alvos"][0]

    assert alvo["alvo_estado"] == "cobertura_parcial"
    assert alvo["alvo_segundos_integrados"] == 3585
    assert alvo["alvo_energia_mWh"] is None
    assert primeiro["motivos_exclusao_leituras"] == {"recebida_depois_corte": 1}

    posterior = executar(lote, lote[2] + timedelta(seconds=1))

    assert posterior["alvos"][0]["alvo_estado"] == "disponivel"
    assert posterior["associadas"][0]["emissao_utc"] == lote[0][0]["emissao_utc"]


@pytest.mark.parametrize("valor", [None, "ausente", "inconsistente"])
def test_exclusao_intermedia_nao_cria_ponte(lote, valor):
    leitura = lote[1]["leituras"][100]

    if valor == "ausente":
        del leitura["recebido_ts"]
    else:
        leitura["recebido_ts"] = (
            leitura["ts"] - 1 if valor == "inconsistente" else None
        )

    alvo = executar(lote)["alvos"][0]

    assert alvo["alvo_segundos_integrados"] == 3570
    assert alvo["alvo_segundos_sem_intervalo"] == 30
    assert alvo["alvo_energia_mWh"] is None


def test_historico_sem_rececao_nao_comprova_disponibilidade(lote):
    for leitura in lote[1]["leituras"]:
        del leitura["recebido_ts"]

    resultado = executar(lote)

    assert resultado["estados"] == {"sem_cobertura": 24}
    assert len(resultado["exclusoes_leituras"]) == 241


def test_corrente_medida_utiliza_referencia_das_entradas():
    alvo = executar(criar_lote(metodo="corrente"))["alvos"][0]

    assert alvo["alvo_energia_mWh"] == pytest.approx(10)
    assert alvo["alvo_tensao_assumida_v"] == 2
    assert alvo["alvo_potencia_referencia_mW"] is None
    assert alvo["alvo_origem_energia"] == "corrente_medida_tensao_assumida"


def test_corrente_ausente_nao_e_substituida_por_pwm():
    lote = criar_lote(metodo="corrente")
    lote[1]["leituras"][100]["corrente_ma"] = None

    alvo = executar(lote)["alvos"][0]

    assert alvo["alvo_segundos_excluidos"] == 30
    assert alvo["alvo_energia_mWh"] is None


@pytest.mark.parametrize(
    "segundos,estado",
    [(3599, "hora_nao_terminada"), (3600, "disponivel")],
)
def test_fronteira_do_fim_da_hora(lote, segundos, estado):
    inicio = datetime.fromisoformat(lote[0][0]["inicio_hora_alvo_utc"])
    resultado = executar(lote, inicio + timedelta(seconds=segundos))

    assert resultado["alvos"][0]["alvo_estado"] == estado
    assert resultado["alvos"][1]["alvo_estado"] == "hora_nao_terminada"


def test_rejeita_avaliacao_futura(lote):
    with pytest.raises(ValueError, match="futuro"):
        modulo.associar(
            lote[0], lote[1], "no_teste", "sala", lote[2],
            relogio=lambda: lote[2] - timedelta(seconds=1),
        )


def test_rejeita_avaliacao_anterior_a_emissao(lote):
    momento = datetime.fromisoformat(lote[0][0]["emissao_utc"])

    with pytest.raises(ValueError, match="anterior"):
        executar(lote, momento - timedelta(seconds=1))


def test_rejeita_historico_de_outro_periodo(lote):
    antigo, _ = criar_caso()

    with pytest.raises(ValueError, match="dia alvo"):
        executar((lote[0], antigo, lote[2]))


@pytest.mark.parametrize("campo,valor", [
    ("no_id", "outro"),
    ("divisao", "quarto"),
    ("data_alvo_local", "2026-11-19"),
    ("versao_dataset", "desconhecida"),
    ("potencia_referencia_mW", 20),
    ("alvo_energia_mWh", 1),
])
def test_rejeita_entradas_incompativeis(lote, campo, valor):
    lote[0][0][campo] = valor

    with pytest.raises(ValueError):
        executar(lote)


@pytest.mark.parametrize("duplicar", [False, True])
def test_rejeita_horas_em_falta_ou_duplicadas(lote, duplicar):
    if duplicar:
        lote[0][1] = deepcopy(lote[0][0])
    else:
        lote[0].pop()

    with pytest.raises(ValueError):
        executar(lote)


@pytest.mark.parametrize(
    "dia,total",
    [("2026-03-28", 23), ("2026-10-24", 25)],
)
def test_preserva_dias_com_mudanca_de_hora(dia, total):
    resultado = executar(criar_lote(dia, "Europe/Zurich"))

    assert len(resultado["alvos"]) == total
    assert resultado["estados"] == {
        "disponivel": 1,
        "sem_cobertura": total - 1,
    }


def test_nao_soma_divisoes(lote):
    lote[1]["leituras"] += [
        {**linha, "divisao": "quarto"}
        for linha in lote[1]["leituras"]
    ]

    assert executar(lote)["alvos"][0]["alvo_energia_mWh"] == pytest.approx(10)


@pytest.fixture
def pasta_exportacao(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    (tmp_path / ".gitignore").write_text(
        "/ai/data/processed/\n",
        encoding="utf-8",
    )

    pasta = tmp_path / "ai/data/processed"
    pasta.mkdir(parents=True)

    monkeypatch.setattr(dataset, "AI_DIR", tmp_path / "ai")

    return pasta


def test_exporta_csvs_separados_e_preserva_entrada(lote, pasta_exportacao):
    entrada = pasta_exportacao / "entradas.csv"
    dataset.guardar(lote[0], entrada)
    original = entrada.read_bytes()

    lidas = modulo.ler_csv(entrada)
    resultado = executar((lidas, lote[1], lote[2]))

    destinos = modulo.guardar_resultado(
        resultado,
        pasta_exportacao / "alvos.csv",
        pasta_exportacao / "associado.csv",
    )

    assert len(destinos) == 2
    assert entrada.read_bytes() == original

    with destinos[1].open(encoding="utf-8", newline="") as ficheiro:
        linhas = list(csv.DictReader(ficheiro))

    assert {campo: linhas[0][campo] for campo in lidas[0]} == lidas[0]
    assert linhas[1]["alvo_energia_mWh"] == ""


def test_falha_na_segunda_saida_remove_so_primeira_nova(lote, pasta_exportacao):
    primeiro = pasta_exportacao / "alvos.csv"
    existente = pasta_exportacao / "existente.csv"
    existente.write_text("preservar", encoding="utf-8")

    with pytest.raises(ValueError, match="existe"):
        modulo.guardar_resultado(executar(lote), primeiro, existente)

    assert not primeiro.exists()
    assert existente.read_text(encoding="utf-8") == "preservar"


def test_destinos_iguais_rejeitados(lote, pasta_exportacao):
    destino = pasta_exportacao / "teste.csv"

    with pytest.raises(ValueError, match="diferir"):
        modulo.guardar_resultado(executar(lote), destino, destino)

    assert not destino.exists()


def test_cli_sem_destino_nao_escreve(lote, tmp_path, monkeypatch, capsys):
    entradas = tmp_path / "entradas.csv"

    with entradas.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(ficheiro, fieldnames=list(lote[0][0]))
        escritor.writeheader()
        escritor.writerows(lote[0])

    historico = tmp_path / "historico.json"
    historico.write_text(json.dumps(lote[1]), encoding="utf-8")

    antes = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    monkeypatch.setattr(modulo, "agora_utc", lambda: lote[2])
    monkeypatch.setattr(sys, "argv", [
        "modulo",
        "--entradas", str(entradas),
        "--historico-alvo", str(historico),
        "--no", "no_teste",
        "--divisao", "sala",
    ])

    modulo.main()

    assert "Alvos disponivel: 1" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == antes