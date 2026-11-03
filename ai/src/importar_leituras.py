"""Importa leituras do TSV sem modificar o ficheiro original."""

import csv
import math
from pathlib import Path


# Localiza a pasta ai/ independentemente da pasta do terminal.
AI_DIR = Path(__file__).resolve().parents[1]

# Estes são os oito campos presentes na exportação da base de dados.
CAMPOS = (
    "no_id", "divisao", "ts", "luz_raw",
    "luz_pct", "presenca", "led_pct", "modo",
)

# Estes campos devem conter números inteiros.
CAMPOS_INTEIROS = ("ts", "presenca", "led_pct")

# A luminosidade pode conter casas decimais ou estar ausente.
CAMPOS_LUZ = ("luz_raw", "luz_pct")


def importar_tsv(caminho, no_esperado="no3"):
    """Lê o TSV e devolve as leituras do nó escolhido.

    Converte tipos, mas não aplica ainda todas as regras de qualidade.
    Por exemplo, valores negativos são preservados para análise posterior.
    """
    if not isinstance(no_esperado, str) or not no_esperado.strip():
        raise ValueError("É necessário indicar um nó válido.")

    leituras = []

    # utf-8-sig aceita UTF-8 com ou sem a marca inicial BOM.
    # O modo de abertura é apenas de leitura.
    with Path(caminho).open(
        "r", encoding="utf-8-sig", newline=""
    ) as ficheiro:
        leitor = csv.DictReader(ficheiro, delimiter="\t")

        # Confirmar a estrutura antes de interpretar os registos.
        colunas = leitor.fieldnames
        if colunas is None or len(colunas) != len(set(colunas)):
            raise ValueError("Cabeçalho ausente ou com colunas repetidas.")

        faltam = set(CAMPOS) - set(colunas)
        if faltam:
            raise ValueError(f"Faltam colunas: {', '.join(sorted(faltam))}.")

        for linha in leitor:
            numero = leitor.line_num

            # O DictReader usa None quando a linha tem campos a mais
            # ou quando faltam valores por ter menos separadores.
            if None in linha or any(v is None for v in linha.values()):
                raise ValueError(f"Linha {numero}: estrutura inválida.")

            # Importar apenas o nó pedido, sem misturar instalações.
            if linha["no_id"] != no_esperado:
                continue

            leitura = {campo: linha[campo] for campo in CAMPOS}

            for campo in CAMPOS_INTEIROS:
                try:
                    leitura[campo] = int(linha[campo])
                except ValueError as erro:
                    raise ValueError(
                        f"Linha {numero}: {campo} deve ser inteiro."
                    ) from erro

            for campo in CAMPOS_LUZ:
                texto = linha[campo].strip()

                # Ausência de medição é diferente de luminosidade zero.
                if texto == "NULL" or texto == "":
                    leitura[campo] = None
                    continue

                try:
                    valor = float(texto)
                except ValueError as erro:
                    raise ValueError(
                        f"Linha {numero}: {campo} deve ser numérico."
                    ) from erro

                # Não aceitar NaN ou infinito como medições numéricas.
                if not math.isfinite(valor):
                    raise ValueError(
                        f"Linha {numero}: {campo} deve ser finito."
                    )

                leitura[campo] = valor

            leituras.append(leitura)

    if not leituras:
        raise ValueError(f"Não existem leituras para o nó {no_esperado}.")

    return leituras


def main():
    """Importa o histórico do no3 e apresenta um resumo no terminal."""
    origem = AI_DIR / "data" / "raw" / "leituras.tsv"
    leituras = importar_tsv(origem, no_esperado="no3")

    print("Nó selecionado: no3")
    print(f"Leituras importadas: {len(leituras)}")

    # Contar ausências sem as preencher ou alterar.
    for campo in CAMPOS_LUZ:
        ausentes = sum(leitura[campo] is None for leitura in leituras)
        print(f"Valores ausentes em {campo}: {ausentes}")

    print("Importação concluída; validação de qualidade ainda pendente.")
    print("Ficheiro original preservado. Nenhum ficheiro de saída criado.")


if __name__ == "__main__":
    main()