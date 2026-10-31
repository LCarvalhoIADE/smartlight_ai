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