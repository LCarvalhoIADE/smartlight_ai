"""Testes da análise de qualidade, usando apenas dados fictícios."""

from copy import deepcopy

import pytest

from ai.src.analisar_qualidade import analisar


@pytest.fixture
def criar_leitura():
    """Disponibiliza uma função para criar leituras fictícias."""

    def criar(ts=1700000000, divisao="sala"):
        # Os campos respeitam o formato exigido pela validação.
        # hora é apenas texto nesta versão; a análise utiliza ts.
        return {
            "no_id": "no3",
            "divisao": divisao,
            "ts": ts,
            "luz_raw": 1,
            "luz_pct": None,
            "presenca": 1,
            "led_pct": 100,
            "modo": "auto",
            "hora": "hora fictícia",
        }

    return criar


def test_resumo_e_preservacao(criar_leitura):
    """Confirma totais, nulos, UTC, ordenação e entrada intacta."""
    dados = [
        criar_leitura(1700000031),
        criar_leitura(1700000000),
        criar_leitura(1700000015),
    ]
    original = deepcopy(dados)

    resumo = analisar(dados)
    grupo = resumo["grupos"][0]

    assert resumo["total"] == 3
    assert resumo["inicio_utc"] == "2023-11-14T22:13:20+00:00"
    assert resumo["fim_utc"] == "2023-11-14T22:13:51+00:00"
    assert resumo["nulos"]["luz_pct"] == 3

    # Todos os restantes campos devem apresentar zero nulos.
    assert all(
        total == 0
        for campo, total in resumo["nulos"].items()
        if campo != "luz_pct"
    )

    assert grupo["intervalo_minimo"] == 15
    assert grupo["intervalo_maximo"] == 16
    assert grupo["alertas"] == []
    assert dados == original


@pytest.mark.parametrize(
    "intervalo,numero_alertas",
    [(30, 0), (31, 1)],
)
def test_fronteira_do_alerta(criar_leitura, intervalo, numero_alertas):
    """Exatamente 30 segundos é aceite; acima disso gera alerta."""
    dados = [
        criar_leitura(1700000000),
        criar_leitura(1700000000 + intervalo),
    ]

    grupo = analisar(dados)["grupos"][0]

    assert len(grupo["alertas"]) == numero_alertas

    # Quando existe alerta, verifica também o seu conteúdo.
    if numero_alertas:
        assert grupo["alertas"][0] == {
            "inicio_utc": "2023-11-14T22:13:20+00:00",
            "fim_utc": "2023-11-14T22:13:51+00:00",
            "intervalo_segundos": 31,
        }


def test_separa_divisoes(criar_leitura):
    """Uma leitura noutra divisão não pode esconder uma interrupção."""
    dados = [
        criar_leitura(1700000000, "sala"),
        criar_leitura(1700000020, "quarto"),
        criar_leitura(1700000040, "sala"),
    ]

    resumo = analisar(dados)
    grupos = {grupo["divisao"]: grupo for grupo in resumo["grupos"]}

    assert len(grupos) == 2
    assert grupos["sala"]["total"] == 2
    assert grupos["sala"]["intervalo_maximo"] == 40
    assert len(grupos["sala"]["alertas"]) == 1

    # Uma única leitura não permite calcular intervalos.
    assert grupos["quarto"]["total"] == 1
    assert grupos["quarto"]["intervalo_minimo"] is None
    assert grupos["quarto"]["intervalo_maximo"] is None
    assert grupos["quarto"]["alertas"] == []


def test_limite_personalizado(criar_leitura):
    """Confirma que é possível alterar o limite usado nos alertas."""
    dados = [
        criar_leitura(1700000000),
        criar_leitura(1700000040),
    ]

    resumo = analisar(dados, limite_intervalo=45)

    assert resumo["limite_intervalo"] == 45
    assert resumo["grupos"][0]["alertas"] == []


@pytest.mark.parametrize(
    "limite",
    [0, -1, True, "30", None, float("inf"), float("nan")],
)
def test_rejeita_limite_invalido(criar_leitura, limite):
    """Rejeita limites que não sejam números positivos e finitos."""
    with pytest.raises(ValueError, match="positivo e finito"):
        analisar([criar_leitura()], limite_intervalo=limite)


def test_reutiliza_validacao_de_duplicados(criar_leitura):
    """Confirma que a análise não ignora os erros da preparação."""
    leitura = criar_leitura()

    with pytest.raises(ValueError, match="duplicado"):
        analisar([leitura, leitura.copy()])