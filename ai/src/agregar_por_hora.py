"""
Agrupa as leituras do nó no3 por hora UTC e divisão.

Para cada grupo, calcula:
- Número de leituras.
- Instante da primeira e da última leitura.
- Proporção das leituras com presença.
- Intensidade média comandada ao LED.
- Luminosidade percentual média, quando disponível.
- Quantidade de leituras com luz_raw disponível.

Limitações:
- As médias não são ponderadas pelo tempo.
- Não são criadas linhas para horas sem leituras.
- Não é calculado consumo energético.
- A quantidade de leituras não comprova que a hora está completa.
- Um valor disponível de luz_raw não comprova a validade do sensor.
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

# Reutilizamos a importação TSV, a validação e o caminho da pasta ai.
from ai.src.importar_leituras import importar_tsv
from ai.src.preparar_dados import AI_DIR, preparar


# Define a ordem das colunas no CSV de saída.
# A nova contagem fica no fim para preservar a ordem das anteriores.
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
    "numero_leituras_luz_raw",
)


def agregar(dados):
    """Valida e agrupa leituras por nó, divisão e hora UTC.

    Entrada:
        Lista de dicionários provenientes do JSON ou do importador TSV.

    Saída:
        Lista de resumos horários, ordenados por hora, nó e divisão.

    A entrada não é modificada. Os erros identificados por preparar,
    incluindo duplicados, interrompem a agregação.

    Nesta etapa, usamos preparar com o nó no3 por defeito.
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

        # Identificamos o início da hora.
        # Exemplo: 23:18:09 pertence ao intervalo [23:00, 00:00).
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

        # Excluímos apenas os nulos da luminosidade percentual.
        # O valor zero é válido e deve participar na média.
        valores_luz = [
            linha["luz_pct"]
            for linha in linhas
            if linha["luz_pct"] is not None
        ]

        # Contamos valores disponíveis, incluindo zero.
        # Não calculamos uma média de luz_raw nem assumimos lux.
        # Esta contagem não verifica a qualidade física da medição.
        numero_luz_raw = sum(
            linha["luz_raw"] is not None
            for linha in linhas
        )

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

        # Sem medições percentuais, preservamos a ausência com None.
        luz_pct_media = (
            mean(valores_luz) if valores_luz else None
        )

        # Esta diferença mede a distância entre o primeiro e o último
        # registo do grupo. Pode incluir falhas internas.
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
            "numero_leituras_luz_raw": numero_luz_raw,
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
    """Lê a fonte escolhida, cria resumos e guarda um CSV local."""

    # Estas opções permitem escolher a fonte e o detalhe do terminal.
    argumentos = argparse.ArgumentParser(
        description="Agrupa leituras do no3 por hora UTC."
    )
    argumentos.add_argument(
        "--amostra",
        action="store_true",
        help="Usar a amostra JSON em vez do histórico TSV.",
    )
    argumentos.add_argument(
        "--detalhes",
        action="store_true",
        help="Apresentar cada resumo horário no terminal.",
    )
    opcoes = argumentos.parse_args()

    if opcoes.amostra:
        # Mantemos os caminhos anteriores para a amostra.
        origem = AI_DIR / "data" / "raw" / "no3_amostra.json"
        destino = AI_DIR / "data" / "processed" / "no3_por_hora.csv"

        # Aceita UTF-8 com ou sem a marca inicial BOM.
        dados = json.loads(origem.read_text(encoding="utf-8-sig"))
    else:
        # O histórico tem um ficheiro de saída próprio.
        # Assim, não substitui o CSV da amostra.
        origem = AI_DIR / "data" / "raw" / "leituras.tsv"
        destino = (
            AI_DIR / "data" / "processed" / "no3_historico_por_hora.csv"
        )
        dados = importar_tsv(origem, no_esperado="no3")

    # A validação e os cálculos acontecem antes de abrir a saída.
    # Erros nesta etapa não substituem o CSV existente.
    resumos = agregar(dados)

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O modo "w" substitui apenas o CSV selecionado em cada execução.
    # newline="" evita linhas em branco adicionais no Windows.
    with destino.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(
            ficheiro,
            fieldnames=CAMPOS_HORARIOS,
        )
        escritor.writeheader()

        # O módulo csv escreve None como uma célula vazia.
        escritor.writerows(resumos)

    print(f"Fonte: {origem.name}")
    print(f"Leituras utilizadas: {len(dados)}")
    print(f"Resumos horários criados: {len(resumos)}")
    print(f"Primeira hora UTC: {resumos[0]['hora_utc']}")
    print(f"Última hora UTC: {resumos[-1]['hora_utc']}")

    # A soma das contagens horárias deve abranger todas as leituras.
    total_luz_raw = sum(
        resumo["numero_leituras_luz_raw"] for resumo in resumos
    )
    print(f"Leituras com luz_raw disponível: {total_luz_raw}")
    print(f"Leituras com luz_raw ausente: {len(dados) - total_luz_raw}")

    # Só imprimimos todas as horas quando o utilizador pede detalhes.
    if opcoes.detalhes:
        for resumo in resumos:
            print(
                f"\nNó: {resumo['no_id']} | "
                f"Divisão: {resumo['divisao']} | "
                f"Hora UTC: {resumo['hora_utc']}"
            )
            print(f"Leituras: {resumo['numero_leituras']}")
            print(
                "Leituras com luz_raw disponível: "
                f"{resumo['numero_leituras_luz_raw']}"
            )
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