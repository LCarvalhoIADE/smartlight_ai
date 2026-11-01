# Bibliotecas utilizadas nos testes.
# deepcopy permite criar uma cópia independente dos dados.
# pytest permite executar testes automáticos.
from copy import deepcopy

import pytest

# Importa a função que queremos testar.
from ai.src.preparar_dados import preparar


@pytest.fixture
def leitura():
    """Cria uma leitura fictícia válida para reutilização nos testes.
    Não são utilizados dados reais recolhidos pelo ESP32.
    """
    return {
        "no_id": "no3",
        "divisao": "teste",
        "ts": 1700000000,
        "luz_raw": 1,
        "luz_pct": None,
        "presenca": 1,
        "led_pct": 100,
        "modo": "auto",
        "hora": "2023-11-14 22:13:20",
    }


def test_preserva_nulo_e_dados_originais(leitura):
    """
    Verifica que o processamento mantém os valores nulos permitidos,
    converte a data para UTC e não altera os dados originais.
    """
    # Guarda uma cópia para comparação após o processamento.
    dados = [leitura]
    original = deepcopy(dados)

    resultado = preparar(dados)

    # Verifica os resultados esperados.
    assert resultado[0]["luz_pct"] is None
    assert resultado[0]["data_utc"] == "2023-11-14T22:13:20+00:00"
    assert dados == original


def test_ordena_por_timestamp(leitura):
    """
    Verifica que as leituras são ordenadas cronologicamente,
    mesmo quando são recebidas fora de ordem.
    """

    # Cria uma segunda leitura registada 15 segundos depois.
    posterior = {**leitura, "ts": leitura["ts"] + 15}

    # Envia primeiro a leitura mais recente.
    resultado = preparar([posterior, leitura])

    # Confirma que a leitura mais antiga aparece primeiro.
    assert [linha["ts"] for linha in resultado] == [
        leitura["ts"],
        posterior["ts"],
    ]


def test_rejeita_duplicados(leitura):
    """
    Verifica que duas leituras com a mesma identificação,
    divisão e timestamp são rejeitadas.
    """

    # O processamento deve produzir um ValueError.
    with pytest.raises(ValueError, match="duplicado"):
        preparar([leitura, leitura.copy()])


# Executa o mesmo teste com diferentes campos e valores inválidos.
# Cada combinação representa um caso de teste independente.
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("no_id", "outro_no"),  # Identificador de nó inesperado.
        ("divisao", " "),       # Divisão sem nome válido.
        ("ts", 0),              # Timestamp não positivo.
        ("ts", True),           # Timestamp do tipo booleano
        ("presenca", 2),        # Presença fora dos valores permitidos.
        ("led_pct", -1),        # Percentagem negativa.
        ("led_pct", 101),       # Percentagem superior a 100.
        ("luz_pct", 101),       # Luminosidade percentual superior a 100.
    ],
)
def test_rejeita_valores_invalidos(leitura, campo, valor):
    """
    Confirma que o programa rejeita diferentes valores inválidos
    através de uma exceção ValueError.
    """

    # Substitui o valor de um campo por um valor inválido.
    leitura[campo] = valor

    # Confirma que o programa identifica o problema.
    with pytest.raises(ValueError):
        preparar([leitura])


def test_rejeita_campo_em_falta(leitura):
    """
    Verifica que uma leitura é rejeitada quando falta
    um dos campos obrigatórios.
    """

    # Remove intencionalmente o campo presença.
    del leitura["presenca"]

    # Confirma que o programa identifica a ausência do campo.
    with pytest.raises(ValueError, match="faltam campos"):
        preparar([leitura])


def test_rejeita_lista_vazia():
    """
    Verifica que o programa não aceita uma lista
    sem quaisquer leituras.
    """
    
    with pytest.raises(ValueError, match="lista"):
        preparar([])
def test_prepara_leitura_sem_hora_e_com_luz_raw_nulo(leitura):
    """Aceita hora ausente e luminosidade nula sem alterar a entrada."""

    # Simula a estrutura do TSV: não existe o campo hora
    # e pode faltar uma medição de luminosidade.
    del leitura["hora"]
    leitura["luz_raw"] = None

    # Guarda uma cópia independente para verificar que a função
    # não modifica os dados que recebeu.
    dados = [leitura]
    original = deepcopy(dados)

    resultado = preparar(dados)

    # As medições ausentes devem continuar como None.
    # Não devem ser substituídas pelo valor zero.
    assert resultado[0]["luz_raw"] is None
    assert resultado[0]["luz_pct"] is None

    # A saída mantém a coluna hora, mas sem inventar um valor.
    assert resultado[0]["hora"] is None

    # A data UTC continua a ser calculada a partir do timestamp.
    assert resultado[0]["data_utc"] == "2023-11-14T22:13:20+00:00"

    # A entrada mantém-se intacta, incluindo a ausência de hora.
    assert dados == original
    assert "hora" not in dados[0]


def test_rejeita_coluna_luz_raw_em_falta(leitura):
    """Distingue uma coluna em falta de uma medição ausente."""

    # luz_raw=None é permitido, mas a coluna luz_raw deve existir.
    # Removê-la significa que a estrutura está incompleta.
    del leitura["luz_raw"]

    with pytest.raises(ValueError, match="faltam campos"):
        preparar([leitura])


def test_importacao_e_preparacao_tsv(tmp_path):
    """Verifica a integração entre importação e preparação."""

    # Esta função só é necessária neste teste de integração.
    from ai.src.importar_leituras import importar_tsv

    # tmp_path é uma pasta temporária criada pelo pytest.
    # O teste não utiliza nem modifica o histórico real.
    caminho = tmp_path / "historico_teste.tsv"

    # Cria duas leituras fictícias fora de ordem cronológica.
    # \t separa os campos e \n separa as linhas.
    # A leitura mais antiga tem luz_raw ausente.
    caminho.write_text(
        "no_id\tdivisao\tts\tluz_raw\tluz_pct\tpresenca\tled_pct\tmodo\n"
        "no3\tteste\t1700000015\t1\tNULL\t1\t100\tauto\n"
        "no3\tteste\t1700000000\tNULL\tNULL\t0\t0\tauto\n",
        encoding="utf-8",
    )

    # Primeiro, importar os dados e converter os tipos.
    importadas = importar_tsv(caminho)
    original = deepcopy(importadas)

    # Depois, validar e ordenar os dados importados.
    preparadas = preparar(importadas)

    # As duas leituras devem ser mantidas e ordenadas.
    assert len(preparadas) == 2
    assert [linha["ts"] for linha in preparadas] == [
        1700000000,
        1700000015,
    ]

    # A ausência de luminosidade é preservada.
    assert preparadas[0]["luz_raw"] is None
    assert preparadas[1]["luz_raw"] == 1.0
    assert all(linha["luz_pct"] is None for linha in preparadas)

    # O TSV não contém hora: a coluna fica nula na saída.
    assert all(linha["hora"] is None for linha in preparadas)

    # Confirmar a conversão temporal de ambas as leituras.
    assert [linha["data_utc"] for linha in preparadas] == [
        "2023-11-14T22:13:20+00:00",
        "2023-11-14T22:13:35+00:00",
    ]

    # A preparação não altera os dados devolvidos pelo importador.
    assert importadas == original
    assert all("hora" not in linha for linha in importadas)