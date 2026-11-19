"""Testa a energia disponível com dados fictícios e sem acesso à rede."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from ai.src import preparar_energia_disponivel as modulo


INICIO = datetime(2026, 11, 10, 18, tzinfo=timezone.utc)
BASE = int(INICIO.timestamp())
EMISSAO = INICIO + timedelta(hours=2)
CORTE = BASE + 6900


def historico(deslocamentos):
    """Potência fictícia de 10 mW em ambos os métodos: 2 V × 5 mA."""
    return {
        "no": {"no_id": "no_teste"},
        "de": BASE,
        "ate": BASE + 10799,
        "mais": False,
        "leituras": [
            {
                "divisao": "sala", "ts": BASE + segundos,
                "recebido_ts": BASE + segundos,
                "luz_raw": 1, "luz_pct": None, "presenca": 1,
                "led_pct": 100, "corrente_ma": 5.0, "modo": "auto",
            }
            for segundos in deslocamentos
        ],
    }


def executar(dados, metodo="pwm", **opcoes):
    parametros = (
        {"tensao_v": 2.0} if metodo == "corrente"
        else {"potencia_referencia_mw": 10.0}
    )
    parametros.update(opcoes)
    return modulo.preparar(
        dados, "no_teste", "sala", EMISSAO, metodo=metodo, **parametros
    )


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
def test_hora_completa_preserva_origem_referencias_e_entrada(metodo):
    dados = historico(range(0, 3601, 15))
    original = deepcopy(dados)
    resultado = executar(dados, metodo)
    hora = resultado["resumos"][0]

    assert hora["hora_completa"] is True
    assert hora["energia_horaria_disponivel_mWh"] == pytest.approx(10)
    assert hora["energia_Wh"] == pytest.approx(0.01)
    assert hora["segundos_sem_intervalo"] == 0
    assert hora["finalidade"] == "entrada_historica"

    if metodo == "corrente":
        assert hora["origem_energia"] == "corrente_medida_tensao_assumida"
        assert hora["tensao_assumida_v"] == 2
        assert hora["potencia_referencia_mW"] is None
    else:
        assert hora["origem_energia"] == "estimativa_pwm_potencia_assumida"
        assert hora["potencia_referencia_mW"] == 10
        assert hora["tensao_assumida_v"] is None

    hora["energia_mWh"] = -1
    assert dados == original


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
def test_reune_segmentos_sem_integrar_a_lacuna(metodo):
    dados = historico(range(0, 3601, 15))
    dados["leituras"][120]["recebido_ts"] = CORTE + 1
    resultado = executar(dados, metodo)
    hora = resultado["resumos"][0]

    assert resultado["segmentos"] == 2
    assert resultado["motivos"] == {"recebida_depois_corte": 1}
    assert hora["segundos_integrados"] == 3570
    assert hora["segundos_excluidos"] == 0
    assert hora["segundos_sem_intervalo"] == 30
    assert hora["energia_mWh"] == pytest.approx(10 * 3570 / 3600)
    assert hora["energia_horaria_disponivel_mWh"] is None
    assert hora["hora_completa"] is False


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
def test_corte_dentro_da_hora_nao_extrapola(metodo):
    dados = historico(range(3600, 7201, 15))
    hora = executar(dados, metodo)["resumos"][0]
    assert hora["segundos_integrados"] == 3300
    assert hora["segundos_sem_intervalo"] == 300
    assert hora["energia_horaria_disponivel_mWh"] is None


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
def test_endpoint_recebido_tarde_impede_hora_completa(metodo):
    dados = historico(range(0, 3601, 15))
    dados["leituras"][-1]["recebido_ts"] = CORTE + 1
    hora = executar(dados, metodo)["resumos"][0]
    assert hora["segundos_integrados"] == 3585
    assert hora["segundos_sem_intervalo"] == 15
    assert hora["hora_completa"] is False


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
def test_zero_completo_e_diferente_de_energia_ausente(metodo):
    dados = historico(range(0, 3601, 15))
    for linha in dados["leituras"]:
        linha["led_pct"] = 0
        linha["corrente_ma"] = 0

    resumos = executar(dados, metodo)["resumos"]
    assert resumos[0]["energia_horaria_disponivel_mWh"] == 0

    # A leitura isolada às 19h não fornece energia para 19h–20h.
    assert resumos[1]["energia_mWh"] is None
    assert resumos[1]["segundos_sem_intervalo"] == 3600


def test_corrente_ausente_nao_e_substituida_por_pwm():
    dados = historico((0, 15, 30))
    dados["leituras"][1]["corrente_ma"] = None
    hora = executar(dados, "corrente")["resumos"][0]
    assert hora["energia_mWh"] is None
    assert hora["segundos_integrados"] == 0
    assert hora["segundos_excluidos"] == 30
    assert hora["segundos_sem_intervalo"] == 3570


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
@pytest.mark.parametrize("limite,integrados", [(30, 15), (90, 90)])
def test_limite_configuravel_preservado(metodo, limite, integrados):
    hora = executar(
        historico((0, 15, 90)), metodo, limite_intervalo=limite
    )["resumos"][0]

    assert hora["segundos_integrados"] == integrados
    assert (
        hora["segundos_integrados"] + hora["segundos_excluidos"]
        + hora["segundos_sem_intervalo"]
    ) == 3600


@pytest.mark.parametrize("metodo", ["corrente", "pwm"])
def test_trapezio_repartido_na_fronteira_horaria(metodo):
    dados = historico((3590, 3610))
    dados["leituras"][0].update(led_pct=0, corrente_ma=0)
    linhas = executar(dados, metodo)["resumos"]

    assert [linha["segundos_integrados"] for linha in linhas] == [10, 10]
    assert [linha["energia_mWh"] for linha in linhas] == pytest.approx(
        [2.5 * 10 / 3600, 7.5 * 10 / 3600]
    )


def test_divisoes_nao_se_misturam():
    dados = historico((0, 15))
    dados["leituras"].extend([
        {**linha, "divisao": "quarto", "recebido_ts": None}
        for linha in list(dados["leituras"])
    ])

    resultado = executar(dados)
    assert resultado["total"] == resultado["selecionadas"] == 2
    assert resultado["excluidas"] == []
    assert all(
        linha["divisao"] == "sala" for linha in resultado["resumos"]
    )


def test_sem_disponibilidade_nao_calcula_nem_inventa_horas(monkeypatch):
    dados = historico((0, 15))
    for linha in dados["leituras"]:
        del linha["recebido_ts"]

    def proibido(*args, **kwargs):
        pytest.fail("O cálculo não deve receber uma seleção vazia.")

    monkeypatch.setattr(modulo, "estimar", proibido)
    resultado = executar(dados)

    assert resultado["resumos"] == []
    assert resultado["motivos"] == {"disponibilidade_desconhecida": 2}


def test_valor_futuro_invalido_nao_entra_no_calculo():
    dados = historico((0, 15, 30))
    dados["leituras"][-1].update(
        recebido_ts=CORTE + 1, led_pct="valor_invalido"
    )

    resultado = executar(dados)
    assert resultado["resumos"][0]["segundos_integrados"] == 15


@pytest.mark.parametrize(
    "opcoes",
    [
        {"metodo": "outro"},
        {"metodo": "corrente"},
        {"metodo": "corrente", "tensao_v": -1},
        {
            "metodo": "corrente",
            "tensao_v": 3.3,
            "potencia_referencia_mw": 17.9,
        },
        {"metodo": "pwm"},
        {"metodo": "pwm", "potencia_referencia_mw": True},
        {"metodo": "pwm", "potencia_referencia_mw": float("nan")},
        {
            "metodo": "pwm",
            "potencia_referencia_mw": 10,
            "tensao_v": 3.3,
        },
        {
            "metodo": "pwm",
            "potencia_referencia_mw": 10,
            "limite_intervalo": 0,
        },
    ],
)
def test_rejeita_configuracao_invalida(opcoes):
    with pytest.raises(ValueError):
        modulo.preparar(
            historico((0, 15)), "no_teste", "sala", EMISSAO, **opcoes
        )


def test_rejeita_divisao_inexistente():
    with pytest.raises(ValueError, match="divisão"):
        modulo.preparar(
            historico((0, 15)), "no_teste", "quarto", EMISSAO,
            metodo="pwm", potencia_referencia_mw=10,
        )


@pytest.mark.parametrize("margem,segundos", [(0, 3600), (10, 3000)])
def test_margem_dos_sensores_passada_ao_filtro(margem, segundos):
    dados = historico(range(3600, 7201, 15))
    hora = executar(dados, margem_minutos=margem)["resumos"][0]

    assert hora["margem_minutos"] == margem
    assert hora["segundos_integrados"] == segundos


def test_cli_preserva_ficheiro(tmp_path, monkeypatch, capsys):
    caminho = tmp_path / "historico.json"
    caminho.write_text(
        json.dumps(historico((0, 15))), encoding="utf-8-sig"
    )
    original = caminho.read_bytes()

    monkeypatch.setattr("sys.argv", [
        "programa", "--origem", str(caminho), "--no", "no_teste",
        "--divisao", "sala", "--emissao", EMISSAO.isoformat(),
        "--metodo", "pwm", "--potencia-referencia-mw", "10",
        "--detalhes",
    ])
    modulo.main()

    texto = capsys.readouterr().out
    assert (
        "Horas completas / parciais / sem cobertura: 0 / 1 / 0"
        in texto
    )
    assert "energia horária=indisponível" in texto
    assert caminho.read_bytes() == original
    assert list(tmp_path.iterdir()) == [caminho]