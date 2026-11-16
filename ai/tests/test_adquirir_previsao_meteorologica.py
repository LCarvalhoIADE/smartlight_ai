"""Testes locais com relógio, coordenadas e respostas fictícias."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from ai.src import adquirir_previsao_meteorologica as modulo
from ai.src.preparar_meteorologia import UNIDADES


@pytest.fixture
def historico():
    """Cria metadados fictícios, sem utilizar os dados dos colegas."""
    return {
        "no": {
            "no_id": "no_teste",
            "latitude": 40.0,
            "longitude": -8.0,
            "fuso": "Europe/Lisbon",
        }
    }


def criar_resposta(parametros):
    """Cria uma resposta horária com ambas as fronteiras incluídas."""
    inicio = datetime.fromisoformat(parametros["start_hour"])
    fim = datetime.fromisoformat(parametros["end_hour"])

    quantidade = int((fim - inicio).total_seconds() / 3600) + 1

    horas = {
        "time": [
            (inicio + timedelta(hours=i)).isoformat(
                timespec="minutes"
            )
            for i in range(quantidade)
        ]
    }

    for campo in UNIDADES:
        horas[campo] = [0] * quantidade

    return {
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly_units": {
            "time": "iso8601",
            **UNIDADES,
        },
        "hourly": horas,
    }


def executar(historico, consultar=None, inicio=None, fim=None):
    """Utiliza um relógio fixo, independente da data real."""
    inicio = inicio or datetime(
        2026, 11, 12, 19, 50,
        tzinfo=timezone.utc,
    )

    fim = fim or inicio + timedelta(seconds=2)
    momentos = iter([inicio, fim])

    return modulo.adquirir(
        historico,
        "no_teste",
        consultar=consultar or criar_resposta,
        relogio=lambda: next(momentos),
    )


def test_aquisicao_preserva_entrada_e_resposta(historico):
    """Confirma período, proveniência e momento de disponibilidade."""
    original = deepcopy(historico)
    recebidas = []

    def consultar(parametros):
        resposta = criar_resposta(parametros)
        recebidas.append(deepcopy(resposta))
        return resposta

    documento = executar(historico, consultar)
    aquisicao = documento["aquisicao"]

    assert historico == original
    assert documento["meteorologia"] == recebidas[0]
    assert aquisicao["tipo"] == "previsao_meteorologica"
    assert aquisicao["data_alvo_local"] == "2026-11-13"
    assert aquisicao["intervalos_horarios"] == 24
    assert aquisicao["instantes_recebidos"] == 25
    assert (
        aquisicao["disponivel_desde_utc"]
        == "2026-11-12T19:50:02+00:00"
    )


@pytest.mark.parametrize(
    "fuso",
    ["Europe/Lisbon", "Europe/Zurich"],
)
@pytest.mark.parametrize(
    "mes,dia,horas",
    [(3, 28, 23), (10, 24, 25)],
)
def test_mudanca_de_hora(historico, fuso, mes, dia, horas):
    """Verifica os dias com mudança de hora de primavera e outono."""
    historico["no"]["fuso"] = fuso

    inicio = datetime(
        2026, mes, dia, 18,
        tzinfo=timezone.utc,
    )

    documento = executar(historico, inicio=inicio)

    assert documento["aquisicao"]["intervalos_horarios"] == horas
    assert documento["aquisicao"]["instantes_recebidos"] == horas + 1


def test_dia_seguinte_respeita_data_local(historico):
    """Às 23h30 UTC já pode ser o dia seguinte em Zurique."""
    historico["no"]["fuso"] = "Europe/Zurich"

    inicio = datetime(
        2026, 11, 12, 23, 30,
        tzinfo=timezone.utc,
    )

    documento = executar(historico, inicio=inicio)
    aquisicao = documento["aquisicao"]

    assert aquisicao["data_alvo_local"] == "2026-11-14"
    assert (
        aquisicao["inicio_alvo_utc"]
        == "2026-11-13T23:00:00+00:00"
    )


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("latitude", None),
        ("latitude", True),
        ("latitude", 91),
        ("longitude", float("nan")),
        ("longitude", 181),
        ("fuso", "Fuso/Inexistente"),
        ("no_id", "outro_no"),
    ],
)
def test_rejeita_metadados_invalidos(historico, campo, valor):
    """Impede aquisições com identificação ou localização inválida."""
    historico["no"][campo] = valor

    with pytest.raises(ValueError):
        executar(historico)


@pytest.mark.parametrize(
    "campo,indice",
    [
        ("temperature_2m", 0),
        ("precipitation", -1),
        ("shortwave_radiation", -1),
    ],
)
def test_rejeita_nulos_necessarios(historico, campo, indice):
    """Exige os valores necessários para representar todo o dia alvo."""

    def consultar(parametros):
        resposta = criar_resposta(parametros)
        resposta["hourly"][campo][indice] = None
        return resposta

    with pytest.raises(ValueError, match="incompleta"):
        executar(historico, consultar)


def test_preserva_nulos_nao_utilizados(historico):
    """Permite nulos nos instantes que não pertencem ao cálculo alvo."""

    def consultar(parametros):
        resposta = criar_resposta(parametros)

        # A temperatura final já representa o dia seguinte ao alvo.
        resposta["hourly"]["temperature_2m"][-1] = None

        # A precipitação inicial representa a hora anterior ao alvo.
        resposta["hourly"]["precipitation"][0] = None

        return resposta

    documento = executar(historico, consultar)

    assert (
        documento["meteorologia"]["hourly"]["temperature_2m"][-1]
        is None
    )


@pytest.mark.parametrize(
    "problema",
    ["fim_ausente", "unidade", "erro_api"],
)
def test_rejeita_resposta_invalida(historico, problema):
    """Rejeita períodos incompletos, unidades erradas e erros da API."""

    def consultar(parametros):
        resposta = criar_resposta(parametros)

        if problema == "fim_ausente":
            for valores in resposta["hourly"].values():
                valores.pop()

        elif problema == "unidade":
            resposta["hourly_units"]["temperature_2m"] = "°F"

        else:
            return {
                "error": True,
                "reason": "Erro fictício",
            }

        return resposta

    with pytest.raises(ValueError):
        executar(historico, consultar)


def test_rejeita_recuo_do_relogio(historico):
    """O fim da consulta não pode ser anterior ao início."""
    inicio = datetime(
        2026, 11, 12, 19,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError, match="relógio recuou"):
        executar(
            historico,
            inicio=inicio,
            fim=inicio - timedelta(seconds=1),
        )


def test_rejeita_consulta_que_atravessa_inicio_do_alvo(historico):
    """Não apresenta como futura uma aquisição concluída após a meia-noite."""
    inicio = datetime(
        2026, 11, 12, 23, 59, 59,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError, match="dia alvo já começou"):
        executar(
            historico,
            inicio=inicio,
            fim=inicio + timedelta(seconds=2),
        )


@pytest.mark.parametrize("tipo", ["http", "rede", "json"])
def test_falhas_de_transporte_sem_expor_url(monkeypatch, tipo):
    """Simula falhas sem abrir ligações reais à Internet."""

    class RespostaInvalida:
        def __enter__(self):
            return self

        def __exit__(self, *argumentos):
            return False

        def read(self):
            return b"resposta-privada"

    def abrir(*argumentos, **opcoes):
        if tipo == "http":
            raise HTTPError(
                "localizacao-privada",
                503,
                "erro",
                None,
                None,
            )

        if tipo == "rede":
            raise URLError("localizacao-privada")

        return RespostaInvalida()

    monkeypatch.setattr(modulo, "urlopen", abrir)

    with pytest.raises(ValueError) as erro:
        modulo.pedir_previsao({"timezone": "GMT"})

    assert "localizacao-privada" not in str(erro.value)
    assert "resposta-privada" not in str(erro.value)


@pytest.mark.parametrize(
    "acompanhado,ignorado",
    [(0, 0), (1, 1)],
)
def test_rejeita_destino_desprotegido(
    tmp_path,
    monkeypatch,
    acompanhado,
    ignorado,
):
    """Simula o Git sem alterar o repositório do projeto."""
    monkeypatch.setattr(
        modulo,
        "AI_DIR",
        tmp_path / "ai",
    )

    def executar_git(argumentos, **opcoes):
        codigo = (
            acompanhado
            if argumentos[1] == "ls-files"
            else ignorado
        )

        return SimpleNamespace(returncode=codigo)

    monkeypatch.setattr(
        modulo.subprocess,
        "run",
        executar_git,
    )

    with pytest.raises(ValueError, match="ignorado"):
        modulo.guardar(
            {"teste": True},
            tmp_path / "ai/data/raw/teste.json",
        )


def test_guarda_sem_substituir(tmp_path, monkeypatch, historico):
    """Guarda um JSON novo e preserva-o numa tentativa de substituição."""
    monkeypatch.setattr(
        modulo,
        "AI_DIR",
        tmp_path / "ai",
    )

    monkeypatch.setattr(
        modulo.subprocess,
        "run",
        lambda argumentos, **opcoes: SimpleNamespace(
            returncode=(
                1 if argumentos[1] == "ls-files" else 0
            )
        ),
    )

    destino = tmp_path / "ai/data/raw/previsao_teste.json"
    documento = executar(historico)

    modulo.guardar(documento, destino)
    original = destino.read_bytes()

    assert (
        json.loads(destino.read_text(encoding="utf-8"))
        == documento
    )

    with pytest.raises(ValueError, match="já existe"):
        modulo.guardar(documento, destino)

    assert destino.read_bytes() == original