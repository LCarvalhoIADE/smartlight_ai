"""
Agrupa as leituras do nó no3 por hora UTC e divisão.

Para cada grupo, calcula:
- Número de leituras.
- Instante da primeira e da última leitura.
- Proporção das leituras com presença.
- Intensidade média comandada ao LED.
- Luminosidade percentual média, quando disponível.

Limitações:
- As médias não são ponderadas pelo tempo.
- Não são criadas linhas para horas sem leituras.
- Não é calculado consumo energético.
- A quantidade de leituras não comprova que a hora está completa.
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

# Reutilizamos a validação existente e o caminho da pasta ai.
from ai.src.preparar_dados import AI_DIR, preparar


# Define a ordem das colunas no CSV de saída.
CAMPOS_HORARIOS = (
    "no_id",
    "divisao",
    "hora_utc",
    "numero_leituras",
    "primeira_leitura_utc",
    "ultima_leitura_utc",
    "intervalo_observado_segundos",
    "presenca_proporcao",
    "led_pct_medio",
    "luz_pct_media",
    "numero_leituras_luz_pct",
)


def agregar(dados):
    """
    Valida e agrupa leituras por nó, divisão e hora UTC.

    Entrada:
        Lista de dicionários no formato das leituras originais.

    Saída:
        Lista de resumos horários, ordenados por hora, nó e divisão.

    A entrada não é modificada. Dados inválidos ou duplicados
    são rejeitados pela função preparar.

    Nesta versão, preparar aceita apenas o nó no3.
    """

    # Valida os dados, acrescenta data_utc e ordena por timestamp.
    leituras = preparar(dados)

    # Cada chave identifica uma hora de um nó e de uma divisão.
    grupos = defaultdict(list)

    for leitura in leituras:
        # Convertemos o timestamp diretamente para UTC.
        # Assim, a hora não depende do fuso horário do computador.
        instante = datetime.fromtimestamp(
            leitura["ts"],
            timezone.utc,
        )

        # Colocamos minutos e segundos a zero para identificar
        # o início da hora. Exemplo: 23:18:09 passa a 23:00:00.
        inicio_hora = instante.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        chave = (
            leitura["no_id"],
            leitura["divisao"],
            inicio_hora,
        )

        grupos[chave].append(leitura)

    resultado = []

    for (no_id, divisao, inicio_hora), linhas in grupos.items():
        # As linhas mantêm a ordem cronológica recebida de preparar.
        primeira = linhas[0]
        ultima = linhas[-1]

        # Excluímos apenas os nulos do cálculo da luminosidade.
        # O valor zero é válido e deve participar na média.
        valores_luz = [
            linha["luz_pct"]
            for linha in linhas
            if linha["luz_pct"] is not None
        ]

        # presenca contém 0 ou 1.
        # A soma conta quantas leituras indicam presença.
        # Por exemplo: [1, 0, 1, 0] resulta em 0.5, ou 50%.
        presenca_proporcao = (
            sum(linha["presenca"] for linha in linhas)
            / len(linhas)
        )

        # Cada leitura tem o mesmo peso nesta média.
        # Isto não representa energia consumida nem uma média
        # ponderada pelo tempo entre as leituras.
        led_pct_medio = mean(
            linha["led_pct"] for linha in linhas
        )

        # Se não houver medições de luminosidade percentual,
        # preservamos a ausência de informação com None.
        luz_pct_media = (
            mean(valores_luz) if valores_luz else None
        )

        # Esta diferença mede apenas a distância entre o primeiro
        # e o último registo do grupo. Pode conter falhas internas.
        # Não deve ser interpretada como cobertura contínua.
        intervalo_observado = ultima["ts"] - primeira["ts"]

        resultado.append({
            "no_id": no_id,
            "divisao": divisao,
            "hora_utc": inicio_hora.isoformat(),
            "numero_leituras": len(linhas),
            "primeira_leitura_utc": primeira["data_utc"],
            "ultima_leitura_utc": ultima["data_utc"],
            "intervalo_observado_segundos": intervalo_observado,
            "presenca_proporcao": presenca_proporcao,
            "led_pct_medio": led_pct_medio,
            "luz_pct_media": luz_pct_media,
            "numero_leituras_luz_pct": len(valores_luz),
        })

    # Ordenamos os resumos para obter uma saída previsível.
    return sorted(
        resultado,
        key=lambda linha: (
            linha["hora_utc"],
            linha["no_id"],
            linha["divisao"],
        ),
    )


def main():
    """Lê a amostra, cria os resumos e guarda um CSV local."""

    origem = AI_DIR / "data/raw/no3_amostra.json"
    destino = AI_DIR / "data/processed/no3_por_hora.csv"

    # Aceita ficheiros UTF-8 com ou sem a marca inicial BOM.
    dados = json.loads(
        origem.read_text(encoding="utf-8-sig")
    )

    # A validação e os cálculos acontecem antes de abrir a saída.
    # Se os dados forem inválidos, não substituímos o CSV existente.
    resumos = agregar(dados)

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O modo "w" substitui este CSV em cada execução.
    # newline="" evita linhas em branco adicionais no Windows.
    with destino.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as ficheiro:
        escritor = csv.DictWriter(
            ficheiro,
            fieldnames=CAMPOS_HORARIOS,
        )
        escritor.writeheader()

        # O módulo csv escreve None como uma célula vazia.
        escritor.writerows(resumos)

    print(f"Leituras utilizadas: {len(dados)}")
    print(f"Resumos horários criados: {len(resumos)}")

    for resumo in resumos:
        print(
            f"\nNó: {resumo['no_id']} | "
            f"Divisão: {resumo['divisao']} | "
            f"Hora UTC: {resumo['hora_utc']}"
        )
        print(f"Leituras: {resumo['numero_leituras']}")
        print(
            "Intervalo entre primeira e última leitura: "
            f"{resumo['intervalo_observado_segundos']} segundos"
        )
        print(
            "Leituras com presença: "
            f"{resumo['presenca_proporcao']:.1%}"
        )
        print(
            "Intensidade LED média nas leituras: "
            f"{resumo['led_pct_medio']:.2f}%"
        )

        if resumo["luz_pct_media"] is None:
            print("Luminosidade percentual média: sem dados.")
        else:
            print(
                "Luminosidade percentual média: "
                f"{resumo['luz_pct_media']:.2f}%"
            )

    print(f"\nCSV guardado em: {destino}")
    print("As médias descrevem apenas as leituras disponíveis.")
    print("Uma linha no CSV não comprova uma hora completa.")
    print("Sem cálculo de consumo nem preenchimento de falhas.")


# Permite importar agregar nos testes sem ler ou escrever ficheiros.
if __name__ == "__main__":
    main()