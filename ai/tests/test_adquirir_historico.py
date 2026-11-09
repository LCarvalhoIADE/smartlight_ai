"""Testa a aquisição com respostas fictícias, sem pedidos ao servidor."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ai.src import adquirir_historico as modulo


@pytest.fixture
def pagina():
    """Cria uma resposta fictícia completa com uma leitura."""
    return {
        "no": {
            "no_id": "no1",
            "latitude": 38.0,
            "longitude": -9.0,
            "fuso": "Europe/Lisbon",
        },
        "de": 1700000000,
        "ate": 1700000059,
        "mais": False,
        "leituras": [{
            "divisao": "teste",
            "ts": 1700000000,
            "luz_raw": 0,
            "luz_pct": None,
            "presenca": 0,
            "led_pct": 0,
            "corrente_ma": 0,
            "modo": "auto",
        }],
    }


def executar(pagina, consultar=None, **opcoes):
    """Usa uma chave fictícia e substitui a função de rede."""
    return modulo.adquirir(
        "no1",
        pagina["de"],
        pagina["ate"],
        "chave-ficticia",
        consultar=consultar or (lambda parametros, chave: deepcopy(pagina)),
        **opcoes,
    )


def test_recolhe_paginas_e_preserva_entrada(pagina):
    """Confirma deslocamentos, metadados e reunião das páginas."""
    primeira = deepcopy(pagina)
    primeira["mais"] = True

    segunda = deepcopy(pagina)
    segunda["leituras"][0]["ts"] += 15

    paginas = [primeira, segunda]
    original = deepcopy(paginas)
    pedidos = []

    def consultar(parametros, chave):
        pedidos.append(dict(parametros))
        assert chave == "chave-ficticia"
        assert "chave" not in parametros
        return paginas[len(pedidos) - 1]

    resultado = executar(pagina, consultar=consultar, limite=1)

    assert [pedido["desloca"] for pedido in pedidos] == [0, 1]
    assert len(resultado["leituras"]) == 2
    assert resultado["mais"] is False
    assert resultado["no"] == pagina["no"]
    assert resultado["aquisicao"]["paginas_recolhidas"] == 2
    assert paginas == original


def test_rejeita_duplicado_entre_paginas(pagina):
    """A última página não pode repetir a leitura da primeira."""
    primeira = deepcopy(pagina)
    primeira["mais"] = True
    paginas = iter([primeira, pagina])

    with pytest.raises(ValueError, match="duplicado"):
        executar(
            pagina,
            consultar=lambda parametros, chave: next(paginas),
            limite=1,
        )


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("mais", "false"),
        ("de", 1700000001),
        ("ate", 1700000060),
        ("leituras", None),
        ("no", {"no_id": "no3"}),
    ],
)
def test_rejeita_resposta_incoerente(pagina, campo, valor):
    """Não aceita respostas diferentes do contrato ou do pedido."""
    alterada = deepcopy(pagina)
    alterada[campo] = valor

    with pytest.raises(ValueError):
        executar(
            pagina,
            consultar=lambda parametros, chave: alterada,
        )


def test_rejeita_pagina_vazia_com_continuacao(pagina):
    pagina["leituras"] = []
    pagina["mais"] = True

    with pytest.raises(ValueError, match="Página incompleta"):
        executar(pagina)


def test_limita_numero_de_paginas(pagina):
    """Uma continuação interminável não provoca um ciclo infinito."""
    pagina["mais"] = True

    with pytest.raises(ValueError, match="máximo de páginas"):
        executar(pagina, limite=1, max_paginas=1)


def test_propaga_falha_de_rede(pagina):
    """Uma falha interrompe a aquisição, sem devolver dados incompletos."""
    def falhar(parametros, chave):
        raise RuntimeError("Não foi possível contactar a API.")

    with pytest.raises(RuntimeError, match="contactar"):
        executar(pagina, consultar=falhar)


def test_datas_inclusivas_utc():
    """Um pedido de um dia representa 86 400 segundos UTC."""
    de, ate = modulo.limites_utc("2026-11-02", "2026-11-02")
    assert ate - de + 1 == 86400


@pytest.mark.parametrize(
    "inicio,fim",
    [
        ("invalido", "2026-11-02"),
        ("2026-11-03", "2026-11-02"),
    ],
)
def test_rejeita_datas_invalidas(inicio, fim):
    with pytest.raises(ValueError, match="datas válidas"):
        modulo.limites_utc(inicio, fim)


def test_envia_chave_no_cabecalho(monkeypatch):
    """Inspeciona o pedido HTTP sem estabelecer uma ligação."""
    class RespostaFicticia:
        def __enter__(self):
            return self

        def __exit__(self, *argumentos):
            return False

        def read(self):
            return b'{"mais": false}'

    class ClienteFicticio:
        def open(self, pedido, timeout):
            cabecalhos = {
                nome.lower(): valor
                for nome, valor in pedido.header_items()
            }
            assert cabecalhos["x-chave"] == "segredo-ficticio"
            assert "segredo-ficticio" not in pedido.full_url
            assert timeout == 60
            return RespostaFicticia()

    monkeypatch.setattr(
        modulo, "build_opener", lambda *argumentos: ClienteFicticio()
    )

    assert modulo.pedir_pagina(
        {"no_id": "no1"}, "segredo-ficticio"
    ) == {"mais": False}


def test_guarda_sem_substituir(pagina, tmp_path, monkeypatch):
    """Simula um destino ignorado e verifica a proteção do original."""
    monkeypatch.setattr(modulo, "AI_DIR", tmp_path / "ai")
    monkeypatch.setattr(modulo, "RAIZ_REPOSITORIO", tmp_path)

    # Simula: ficheiro não acompanhado e abrangido pelo .gitignore.
    def git_ficticio(comando, **opcoes):
        codigo = 1 if comando[1] == "ls-files" else 0
        return SimpleNamespace(returncode=codigo)

    monkeypatch.setattr(modulo.subprocess, "run", git_ficticio)

    destino = tmp_path / "ai/data/raw/teste.json"
    modulo.guardar(pagina, destino)
    original = destino.read_bytes()

    with pytest.raises(ValueError, match="já existe"):
        modulo.guardar(pagina, destino)

    assert destino.read_bytes() == original


def test_rejeita_destino_nao_ignorado(tmp_path, monkeypatch):
    """Não permite guardar dados reais num caminho exposto ao Git."""
    monkeypatch.setattr(modulo, "AI_DIR", tmp_path / "ai")
    monkeypatch.setattr(modulo, "RAIZ_REPOSITORIO", tmp_path)

    monkeypatch.setattr(
        modulo.subprocess,
        "run",
        lambda *argumentos, **opcoes: SimpleNamespace(returncode=1),
    )

    with pytest.raises(ValueError, match="ignorado"):
        modulo.verificar_destino(tmp_path / "ai/data/raw/teste.json")
def test_remove_espacos_exteriores_da_chave():
    """Remove espaços e quebras de linha introduzidos ao copiar a chave."""
    assert modulo.normalizar_chave(
        " \tchave-ficticia\r\n"
    ) == "chave-ficticia"


@pytest.mark.parametrize(
    "chave",
    ["", "   ", None, "chave ficticia"],
)
def test_rejeita_chave_invalida(chave):
    """Rejeita chaves vazias, tipos inválidos e espaços interiores."""
    with pytest.raises(ValueError, match="Chave"):
        modulo.normalizar_chave(chave)


def test_aquisicao_utiliza_chave_normalizada(pagina):
    """Confirma que a consulta recebe a chave sem espaços exteriores."""
    def consultar(parametros, chave):
        # A chave segue separada dos parâmetros utilizados no URL.
        assert chave == "chave-ficticia"
        assert "chave" not in parametros
        assert "token" not in parametros

        return deepcopy(pagina)

    modulo.adquirir(
        "no1",
        pagina["de"],
        pagina["ate"],
        "  chave-ficticia  ",
        consultar=consultar,
    )