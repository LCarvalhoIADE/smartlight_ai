"""Testes da aquisição meteorológica com dados inteiramente fictícios."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from ai.src import adquirir_meteorologia as modulo
from ai.src.preparar_meteorologia import UNIDADES


@pytest.fixture
def historico():
    """Metadados fictícios; não utiliza a localização de nenhum colega."""

    return {
        "no": {
            "no_id": "no_teste",
            "latitude": 40.0,
            "longitude": -8.0,
            "fuso": "Europe/Lisbon",
        },
        "leituras": [],
    }


@pytest.fixture
def resposta():
    """Dois dias horários: um dia alvo e o dia adicional pedido à API."""

    inicio = datetime(2026, 10, 1, tzinfo=timezone.utc)
    tempos = [
        (inicio + timedelta(hours=indice)).strftime("%Y-%m-%dT%H:%M")
        for indice in range(48)
    ]

    horarios = {"time": tempos}

    # Zero é válido para todas estas variáveis.
    # Os testes verificam que não é confundido com ausência.
    for campo in UNIDADES:
        horarios[campo] = [0] * 48

    return {
        "latitude": 40.01,
        "longitude": -8.01,
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly_units": {"time": "iso8601", **UNIDADES},
        "hourly": horarios,
    }


def adquirir_ficticio(historico, resposta):
    """Executa a aquisição substituindo o transporte HTTP."""

    return modulo.adquirir(
        historico,
        "no_teste",
        "2026-10-01",
        "2026-10-01",
        consultar=lambda parametros: resposta,
    )


def test_parametros_margem_e_preservacao(historico, resposta):
    """Confirma localização, UTC, margem e preservação das entradas."""

    original_historico = deepcopy(historico)
    original_resposta = deepcopy(resposta)
    pedidos = []

    def consultar(parametros):
        pedidos.append(parametros)
        return resposta

    resultado = modulo.adquirir(
        historico,
        "no_teste",
        "2026-10-01",
        "2026-10-01",
        consultar=consultar,
    )

    assert len(pedidos) == 1
    assert pedidos[0]["latitude"] == 40.0
    assert pedidos[0]["longitude"] == -8.0
    assert pedidos[0]["start_date"] == "2026-10-01"
    assert pedidos[0]["end_date"] == "2026-10-02"
    assert pedidos[0]["timezone"] == "GMT"
    assert pedidos[0]["hourly"].split(",") == list(UNIDADES)
    assert "chave" not in pedidos[0]

    assert resultado["no"]["no_id"] == "no_teste"
    assert resultado["aquisicao"]["horas_recebidas"] == 48
    assert resultado["aquisicao"]["tipo"] == "meteorologia_historica"
    assert resultado["meteorologia"] == original_resposta

    # A localização da grelha é preservada separadamente.
    assert resultado["no"]["latitude"] == 40.0
    assert resultado["meteorologia"]["latitude"] == 40.01
    assert historico == original_historico
    assert resposta == original_resposta


def test_rejeita_no_diferente(historico, resposta):
    """Impede associar a localização de uma instalação a outro nó."""

    historico["no"]["no_id"] = "outro_no"

    with pytest.raises(ValueError, match="nó pedido"):
        adquirir_ficticio(historico, resposta)


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("latitude", None),
        ("latitude", True),
        ("latitude", "40"),
        ("latitude", 91),
        ("longitude", -181),
        ("longitude", float("nan")),
        ("longitude", float("inf")),
    ],
)
def test_rejeita_coordenadas_invalidas(historico, resposta, campo, valor):
    """Rejeita ausências, tipos inadequados e coordenadas impossíveis."""

    historico["no"][campo] = valor

    with pytest.raises(ValueError):
        adquirir_ficticio(historico, resposta)


def test_aceita_coordenadas_zero(historico, resposta):
    """Zero não significa coordenada ausente."""

    historico["no"]["latitude"] = 0
    historico["no"]["longitude"] = 0

    resultado = adquirir_ficticio(historico, resposta)

    assert resultado["no"]["latitude"] == 0
    assert resultado["no"]["longitude"] == 0


@pytest.mark.parametrize(
    "inicio,fim",
    [
        ("2026-10-02", "2026-10-01"),
        ("01/10/2026", "2026-10-01"),
        ("2026-02-30", "2026-10-01"),
    ],
)
def test_rejeita_periodos_invalidos(inicio, fim):
    """Não aceita datas ambíguas, inexistentes ou invertidas."""

    with pytest.raises(ValueError):
        modulo.definir_periodo(inicio, fim)


def test_rejeita_resposta_de_erro(historico):
    """Um JSON de erro não é uma aquisição meteorológica válida."""

    with pytest.raises(ValueError, match="Erro devolvido"):
        adquirir_ficticio(
            historico,
            {"error": True, "reason": "Erro fictício"},
        )


def test_rejeita_periodo_incompleto(historico, resposta):
    """Uma resposta mais curta não pode ser aceite silenciosamente."""

    for valores in resposta["hourly"].values():
        valores.pop()

    with pytest.raises(ValueError, match="não cobre"):
        adquirir_ficticio(historico, resposta)


def test_rejeita_hora_duplicada(historico, resposta):
    """Reutiliza a verificação temporal do preparador existente."""

    resposta["hourly"]["time"][1] = resposta["hourly"]["time"][0]

    with pytest.raises(ValueError, match="intervalo"):
        adquirir_ficticio(historico, resposta)


def test_rejeita_unidade_incorreta(historico, resposta):
    """Não interpreta radiação com unidades incompatíveis."""

    resposta["hourly_units"]["shortwave_radiation"] = "kWh"

    with pytest.raises(ValueError, match="unidade"):
        adquirir_ficticio(historico, resposta)


@pytest.mark.parametrize(
    "campo,indice",
    [
        ("temperature_2m", 0),
        ("precipitation", 24),
        ("shortwave_radiation", 24),
    ],
)
def test_rejeita_nulo_necessario(historico, resposta, campo, indice):
    """Exige valores necessários, incluindo a fronteira de meia-noite."""

    resposta["hourly"][campo][indice] = None

    with pytest.raises(ValueError, match="Meteorologia incompleta"):
        adquirir_ficticio(historico, resposta)


def test_preserva_nulo_fora_do_periodo_necessario(historico, resposta):
    """Não exige as horas adicionais que não entram no cruzamento."""

    resposta["hourly"]["temperature_2m"][47] = None

    resultado = adquirir_ficticio(historico, resposta)

    assert resultado["meteorologia"]["hourly"]["temperature_2m"][47] is None


def test_transporte_sem_chave(monkeypatch, resposta):
    """Inspeciona o pedido HTTP sem contactar a Internet."""

    pedidos = []

    class RespostaFicticia:
        def __enter__(self):
            return self

        def __exit__(self, *argumentos):
            return False

        def read(self):
            return json.dumps(resposta).encode("utf-8")

    def abrir(pedido, timeout):
        pedidos.append((pedido, timeout))
        return RespostaFicticia()

    monkeypatch.setattr(modulo, "urlopen", abrir)

    resultado = modulo.pedir_meteorologia({"timezone": "GMT"})

    pedido, timeout = pedidos[0]
    assert pedido.full_url.startswith(modulo.ENDPOINT + "?")
    assert timeout == 60
    assert pedido.get_header("X-chave") is None
    assert "chave=" not in pedido.full_url
    assert resultado == resposta


@pytest.mark.parametrize("tipo", ["http", "rede", "json"])
def test_erros_do_transporte(monkeypatch, tipo):
    """Apresenta erros sem divulgar o URL ou a resposta bruta."""

    class RespostaInvalida:
        def __enter__(self):
            return self

        def __exit__(self, *argumentos):
            return False

        def read(self):
            return b"conteudo-interno-invalido"

    def abrir(*argumentos, **opcoes):
        if tipo == "http":
            raise HTTPError(
                "https://exemplo.invalid/localizacao-privada",
                503,
                "Erro fictício",
                None,
                None,
            )
        if tipo == "rede":
            raise URLError("localizacao-privada")

        return RespostaInvalida()

    monkeypatch.setattr(modulo, "urlopen", abrir)

    with pytest.raises(ValueError) as erro:
        modulo.pedir_meteorologia({"timezone": "GMT"})

    assert "localizacao-privada" not in str(erro.value)
    assert "conteudo-interno-invalido" not in str(erro.value)


def configurar_destino(monkeypatch, tmp_path, ignorado=True):
    """Simula o Git numa pasta temporária sem tocar no repositório real."""

    pasta_raw = tmp_path / "ai" / "data" / "raw"

    monkeypatch.setattr(modulo, "RAIZ_REPOSITORIO", tmp_path)
    monkeypatch.setattr(modulo, "PASTA_RAW", pasta_raw)

    def executar(argumentos, **opcoes):
        if argumentos[1] == "ls-files":
            return SimpleNamespace(returncode=1)

        return SimpleNamespace(returncode=0 if ignorado else 1)

    monkeypatch.setattr(modulo.subprocess, "run", executar)

    return pasta_raw / "meteo_teste.json"


def test_guarda_sem_substituir(monkeypatch, tmp_path, historico, resposta):
    """Guarda o JSON e recusa substituir uma aquisição existente."""

    destino = configurar_destino(monkeypatch, tmp_path)
    documento = adquirir_ficticio(historico, resposta)

    modulo.guardar(documento, destino)
    conteudo_original = destino.read_bytes()

    assert json.loads(destino.read_text(encoding="utf-8")) == documento

    with pytest.raises(ValueError, match="já existe"):
        modulo.guardar(documento, destino)

    assert destino.read_bytes() == conteudo_original


def test_rejeita_destino_nao_ignorado(monkeypatch, tmp_path):
    """Não permite guardar dados reais num destino desprotegido."""

    destino = configurar_destino(monkeypatch, tmp_path, ignorado=False)

    with pytest.raises(ValueError, match="ignorado"):
        modulo.guardar({"teste": True}, destino)

    assert not destino.exists()


def test_rejeita_destino_fora_de_raw(monkeypatch, tmp_path):
    """Impede guardar a aquisição noutras pastas do projeto."""

    configurar_destino(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="ai/data/raw"):
        modulo.guardar({"teste": True}, tmp_path / "meteo.json")


def test_rejeita_destino_acompanhado(monkeypatch, tmp_path):
    """Um caminho acompanhado pelo Git não pode receber a aquisição."""

    destino = configurar_destino(monkeypatch, tmp_path)

    monkeypatch.setattr(
        modulo.subprocess,
        "run",
        lambda *argumentos, **opcoes: SimpleNamespace(returncode=0),
    )

    with pytest.raises(ValueError, match="não acompanhado"):
        modulo.guardar({"teste": True}, destino)