"""Testa a importação de leituras TSV com dados fictícios.

Os ficheiros são criados na pasta temporária fornecida pelo pytest.
Nenhum teste lê ou altera o histórico real em ai/data/raw/.
"""

import pytest

# Importamos a função que queremos testar.
from ai.src.importar_leituras import importar_tsv


# \t representa uma tabulação: o separador utilizado nos ficheiros TSV.
# A ordem das colunas corresponde à exportação recebida do Luís.
CABECALHO = (
    "no_id\tdivisao\tts\tluz_raw\tluz_pct\tpresenca\tled_pct\tmodo"
)


def criar_tsv(tmp_path, linhas, cabecalho=CABECALHO):
    """Cria um ficheiro fictício e devolve o respetivo caminho.

    tmp_path: pasta temporária criada automaticamente pelo pytest.
    linhas: lista de linhas de dados, já separadas por tabulações.
    cabecalho: permite testar também cabeçalhos incorretos.
    """
    caminho = tmp_path / "leituras_teste.tsv"

    # \n representa uma mudança de linha.
    # Juntamos o cabeçalho às linhas de dados.
    conteudo = cabecalho + "\n" + "\n".join(linhas) + "\n"

    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def test_importa_tipos_e_preserva_ficheiro(tmp_path):
    """Verifica a conversão dos campos e a preservação do original."""
    # Preparação: criar uma leitura fictícia válida do no3.
    caminho = criar_tsv(
        tmp_path,
        ["no3\tsala\t1792891667\t1\tNULL\t1\t100\tauto"],
    )

    # Guardar os bytes antes da importação permite comparar
    # o conteúdo exato do ficheiro depois da execução.
    original = caminho.read_bytes()

    # Execução: no3 é o nó selecionado por defeito.
    resultado = importar_tsv(caminho)

    # Verificação: números são convertidos e NULL torna-se None.
    # Em Python, None representa ausência de valor.
    assert resultado == [{
        "no_id": "no3",
        "divisao": "sala",
        "ts": 1792891667,
        "luz_raw": 1.0,
        "luz_pct": None,
        "presenca": 1,
        "led_pct": 100,
        "modo": "auto",
    }]

    # Em Python, 1 == 1.0 é verdadeiro.
    # Por isso, verificamos também os tipos explicitamente.
    assert type(resultado[0]["ts"]) is int
    assert type(resultado[0]["luz_raw"]) is float
    assert type(resultado[0]["presenca"]) is int
    assert type(resultado[0]["led_pct"]) is int

    # O importador não pode modificar o ficheiro que recebeu.
    assert caminho.read_bytes() == original


def test_seleciona_no_pedido(tmp_path):
    """Verifica que a seleção do nó não mistura instalações."""
    # O ficheiro inclui dois nós no mesmo instante.
    caminho = criar_tsv(
        tmp_path,
        [
            "no3\tsala\t1792891667\t1\tNULL\t1\t100\tauto",
            "no1\tsala\t1792891667\t250\t25\t0\t0\tauto",
        ],
    )

    # Pedimos explicitamente o no1, em vez do no3.
    resultado = importar_tsv(caminho, no_esperado="no1")

    assert len(resultado) == 1
    assert resultado[0]["no_id"] == "no1"


# O pytest executa este teste duas vezes:
# uma com "NULL" e outra com uma célula vazia.
@pytest.mark.parametrize("ausente", ["NULL", ""])
def test_converte_ausencias_sem_perder_zero(tmp_path, ausente):
    """Distingue ausência de medição de uma medição igual a zero."""
    caminho = criar_tsv(
        tmp_path,
        [
            # Primeira leitura: luminosidade ausente.
            f"no3\tsala\t1792891667\t{ausente}\t{ausente}\t0\t0\tauto",

            # Segunda leitura: luminosidade com valor zero.
            "no3\tsala\t1792891682\t0\t0\t0\t0\tauto",
        ],
    )

    resultado = importar_tsv(caminho)

    # Ausências devem ser representadas por None.
    assert resultado[0]["luz_raw"] is None
    assert resultado[0]["luz_pct"] is None

    # Zero é um valor numérico e não deve desaparecer.
    assert resultado[1]["luz_raw"] == 0.0
    assert resultado[1]["luz_pct"] == 0.0


def test_preserva_negativo_para_validacao_posterior(tmp_path):
    """Garante que a importação não esconde leituras negativas."""
    caminho = criar_tsv(
        tmp_path,
        ["no3\tsala\t1792891667\t-1\t0\t0\t0\tauto"],
    )

    resultado = importar_tsv(caminho)

    # Importar é diferente de validar a qualidade.
    # O negativo é preservado nesta etapa para ser identificado depois.
    # Isto não significa que seja uma medição válida de luminosidade.
    assert resultado[0]["luz_raw"] == -1.0


# Executa o mesmo teste para cada campo que exige um inteiro.
@pytest.mark.parametrize("campo", ["ts", "presenca", "led_pct"])
def test_rejeita_inteiro_invalido(tmp_path, campo):
    """Verifica que campos inteiros rejeitam texto não numérico."""
    valores = [
        "no3", "sala", "1792891667", "1",
        "NULL", "1", "100", "auto",
    ]

    # Encontrar a posição do campo e substituir apenas esse valor.
    indice = CABECALHO.split("\t").index(campo)
    valores[indice] = "invalido"

    # Transformar a lista de valores numa linha TSV.
    caminho = criar_tsv(tmp_path, ["\t".join(valores)])

    # O teste passa se a função lançar ValueError com esta mensagem.
    # Se aceitar o valor inválido, o teste falha.
    with pytest.raises(ValueError, match=f"{campo} deve ser inteiro"):
        importar_tsv(caminho)


# As duas parametrizações combinam-se:
# dois campos × quatro valores = oito casos de teste.
@pytest.mark.parametrize("campo", ["luz_raw", "luz_pct"])
@pytest.mark.parametrize("valor", ["texto", "nan", "inf", "-inf"])
def test_rejeita_luminosidade_nao_numerica_ou_nao_finita(
    tmp_path, campo, valor
):
    """Rejeita texto, NaN e infinitos nos campos de luminosidade."""
    valores = [
        "no3", "sala", "1792891667", "1",
        "NULL", "1", "100", "auto",
    ]

    indice = CABECALHO.split("\t").index(campo)
    valores[indice] = valor
    caminho = criar_tsv(tmp_path, ["\t".join(valores)])

    # NaN significa "não é um número".
    # inf e -inf representam infinito positivo e negativo.
    # Nenhum destes valores representa uma medição finita.
    with pytest.raises(ValueError, match=campo):
        importar_tsv(caminho)


@pytest.mark.parametrize(
    "cabecalho, mensagem",
    [
        # Faltam cinco das colunas obrigatórias.
        ("no_id\tdivisao\tts", "Faltam colunas"),

        # A coluna modo aparece duas vezes.
        (CABECALHO + "\tmodo", "colunas repetidas"),
    ],
)
def test_rejeita_cabecalho_invalido(tmp_path, cabecalho, mensagem):
    """Verifica colunas obrigatórias em falta e nomes repetidos."""
    # Não precisamos de leituras: o erro está no cabeçalho.
    caminho = criar_tsv(tmp_path, [], cabecalho=cabecalho)

    with pytest.raises(ValueError, match=mensagem):
        importar_tsv(caminho)


@pytest.mark.parametrize(
    "linha",
    [
        # Sete campos: falta modo e o respetivo separador.
        "no3\tsala\t1792891667\t1\tNULL\t1\t100",

        # Nove campos: existe um valor adicional sem coluna.
        "no3\tsala\t1792891667\t1\tNULL\t1\t100\tauto\textra",
    ],
)
def test_rejeita_linha_com_numero_errado_de_campos(tmp_path, linha):
    """Exige que cada linha tenha tantos campos como o cabeçalho."""
    caminho = criar_tsv(tmp_path, [linha])

    # Um campo vazio entre separadores é diferente
    # de uma linha com um separador em falta.
    with pytest.raises(ValueError, match="estrutura inválida"):
        importar_tsv(caminho)


def test_rejeita_no_sem_leituras(tmp_path):
    """Verifica o erro quando o nó pedido não existe no ficheiro."""
    # O ficheiro contém apenas o no1.
    caminho = criar_tsv(
        tmp_path,
        ["no1\tsala\t1792891667\t250\t25\t0\t0\tauto"],
    )

    # Pedir no3 deve gerar uma mensagem clara.
    with pytest.raises(ValueError, match="Não existem leituras"):
        importar_tsv(caminho, no_esperado="no3")


@pytest.mark.parametrize("no_invalido", ["", " ", None, 3])
def test_rejeita_identificador_de_no_invalido(tmp_path, no_invalido):
    """Exige que o identificador do nó seja texto não vazio."""
    caminho = criar_tsv(tmp_path, [])

    # São inválidos: texto vazio, apenas espaços,
    # ausência de valor e um número em vez de texto.
    with pytest.raises(ValueError, match="indicar um nó válido"):
        importar_tsv(caminho, no_esperado=no_invalido)


def test_aceita_utf8_com_bom(tmp_path):
    """Verifica a leitura de UTF-8 com uma marca BOM inicial."""
    caminho = tmp_path / "com_bom.tsv"

    conteudo = (
        CABECALHO + "\n"
        "no3\tsala\t1792891667\t1\tNULL\t1\t100\tauto\n"
    )

    # Alguns programas acrescentam BOM ao guardar em UTF-8.
    # utf-8-sig cria essa marca neste ficheiro de teste.
    caminho.write_text(conteudo, encoding="utf-8-sig")

    # O importador deve reconhecer o cabeçalho normalmente.
    resultado = importar_tsv(caminho)

    assert len(resultado) == 1
    assert resultado[0]["no_id"] == "no3"


def test_rejeita_ficheiro_vazio(tmp_path):
    """Verifica que um ficheiro sem cabeçalho é rejeitado."""
    caminho = tmp_path / "vazio.tsv"
    caminho.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Cabeçalho ausente"):
        importar_tsv(caminho)