"""
Prepara o alvo energético a partir do CSV de energia horária.

Critério inicial:
- Aceitar apenas horas com 3 600 segundos integrados.
- Exigir energia válida e não negativa.
- Preservar energia zero quando a cobertura é completa.

Não preenche falhas, não acrescenta meteorologia e não treina modelos.
"""

import argparse
import csv
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


AI_DIR = Path(__file__).resolve().parents[1]

# Mantemos as unidades e as hipóteses utilizadas no cálculo.
CAMPOS_SAIDA = (
    "no_id",
    "divisao",
    "hora_utc",
    "energia_mWh",
    "energia_Wh",
    "segundos_integrados",
    "segundos_excluidos",
    "cobertura_proporcao",
    "tensao_assumida_v",
    "limite_intervalo_segundos",
    "origem_energia",
)


def numero(valor, campo):
    """Converte um valor numérico e rejeita booleanos, ausências e infinitos."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f"{campo}: valor numérico inválido.")

    try:
        convertido = float(valor)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{campo}: valor numérico inválido.") from None

    if not math.isfinite(convertido):
        raise ValueError(f"{campo}: valor não finito.")

    return convertido


def segundos(valor, campo):
    """Exige uma quantidade inteira de segundos entre zero e 3 600."""
    convertido = numero(valor, campo)

    if not convertido.is_integer() or not 0 <= convertido <= 3600:
        raise ValueError(f"{campo}: segundos inválidos.")

    return int(convertido)


def energia_opcional(valor, campo):
    """Distingue uma célula vazia de uma medição de energia igual a zero."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None

    convertido = numero(valor, campo)

    if convertido < 0:
        raise ValueError(f"{campo}: energia negativa.")

    return convertido


def selecionar_alvo(linhas, no_esperado):
    """
    Valida os resumos e seleciona as horas energeticamente completas.

    Dados estruturalmente inválidos interrompem o processamento.
    Horas válidas mas incompletas são excluídas e contabilizadas.
    A entrada permanece inalterada.
    """
    if not isinstance(no_esperado, str) or not no_esperado.strip():
        raise ValueError("Identificador de nó inválido.")

    if not isinstance(linhas, list) or not linhas:
        raise ValueError("Esperada uma lista não vazia de resumos.")

    aceites = []
    exclusoes = Counter()
    identificadores = set()
    hipoteses = {}

    for indice, linha in enumerate(linhas, start=1):
        if not isinstance(linha, dict):
            raise ValueError(f"Linha {indice}: formato inválido.")

        if not set(CAMPOS_SAIDA).issubset(linha):
            raise ValueError(f"Linha {indice}: faltam campos.")

        if linha["no_id"] != no_esperado:
            raise ValueError(f"Linha {indice}: nó inesperado.")

        divisao = linha["divisao"]
        if not isinstance(divisao, str) or not divisao.strip():
            raise ValueError(f"Linha {indice}: divisão inválida.")

        # Exige uma hora UTC explícita, sem minutos ou segundos.
        try:
            instante = datetime.fromisoformat(linha["hora_utc"])
        except (TypeError, ValueError):
            raise ValueError(f"Linha {indice}: hora inválida.") from None

        if (
            instante.utcoffset() != timedelta(0)
            or instante.minute != 0
            or instante.second != 0
            or instante.microsecond != 0
        ):
            raise ValueError(
                f"Linha {indice}: esperada uma fronteira horária UTC."
            )

        hora_utc = instante.isoformat()
        chave = (no_esperado, divisao, hora_utc)

        if chave in identificadores:
            raise ValueError(f"Linha {indice}: resumo duplicado.")

        identificadores.add(chave)

        integrados = segundos(
            linha["segundos_integrados"], "segundos_integrados"
        )
        excluidos = segundos(
            linha["segundos_excluidos"], "segundos_excluidos"
        )
        cobertura = numero(
            linha["cobertura_proporcao"], "cobertura_proporcao"
        )

        if integrados + excluidos > 3600:
            raise ValueError(f"Linha {indice}: duração superior a uma hora.")

        # Confirma que a percentagem corresponde aos segundos integrados.
        if not 0 <= cobertura <= 1 or not math.isclose(
            cobertura,
            integrados / 3600,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError(f"Linha {indice}: cobertura incoerente.")

        energia_mwh = energia_opcional(linha["energia_mWh"], "energia_mWh")
        energia_wh = energia_opcional(linha["energia_Wh"], "energia_Wh")

        # As duas unidades devem estar simultaneamente presentes ou ausentes.
        if (energia_mwh is None) != (energia_wh is None):
            raise ValueError(f"Linha {indice}: unidades energéticas incompletas.")

        if energia_mwh is not None and not math.isclose(
            energia_wh,
            energia_mwh / 1000,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError(f"Linha {indice}: unidades energéticas incoerentes.")

        # O produtor atual só calcula energia quando integra algum tempo.
        if (integrados == 0) != (energia_mwh is None):
            raise ValueError(
                f"Linha {indice}: energia incompatível com o tempo integrado."
            )

        tensao = numero(linha["tensao_assumida_v"], "tensao_assumida_v")
        limite = numero(
            linha["limite_intervalo_segundos"], "limite_intervalo_segundos"
        )

        if tensao <= 0 or limite <= 0:
            raise ValueError(f"Linha {indice}: hipótese de cálculo inválida.")

        origem = linha["origem_energia"]
        if origem != "corrente_medida_tensao_assumida":
            raise ValueError(
                f"Linha {indice}: origem energética ainda não suportada."
            )

        # Não mistura configurações de cálculo na mesma divisão.
        configuracao = (tensao, limite, origem)
        if divisao in hipoteses and hipoteses[divisao] != configuracao:
            raise ValueError(
                f"Linha {indice}: hipóteses diferentes na mesma divisão."
            )
        hipoteses[divisao] = configuracao

        if integrados == 0:
            exclusoes["sem_cobertura"] += 1
            continue

        if integrados < 3600:
            exclusoes["cobertura_parcial"] += 1
            continue

        # Cria um registo independente e preserva os instantes originais.
        aceites.append({
            "no_id": no_esperado,
            "divisao": divisao,
            "hora_utc": hora_utc,
            "energia_mWh": energia_mwh,
            "energia_Wh": energia_wh,
            "segundos_integrados": integrados,
            "segundos_excluidos": excluidos,
            "cobertura_proporcao": cobertura,
            "tensao_assumida_v": tensao,
            "limite_intervalo_segundos": limite,
            "origem_energia": origem,
        })

    return {
        "total": len(linhas),
        "aceites": sorted(
            aceites,
            key=lambda linha: (linha["hora_utc"], linha["divisao"]),
        ),
        "excluidas_sem_cobertura": exclusoes["sem_cobertura"],
        "excluidas_parciais": exclusoes["cobertura_parcial"],
    }


def main():
    """Lê o CSV energético e exporta as horas aceites para um novo CSV."""
    argumentos = argparse.ArgumentParser(
        description="Seleciona horas completas para o alvo energético."
    )
    argumentos.add_argument("--origem", type=Path, required=True)
    argumentos.add_argument("--destino", type=Path, required=True)
    argumentos.add_argument("--no", required=True)
    opcoes = argumentos.parse_args()

    origem = opcoes.origem.resolve()
    destino = opcoes.destino.resolve()
    pasta_processed = (AI_DIR / "data/processed").resolve()

    if origem == destino:
        raise ValueError("A origem e o destino devem ser diferentes.")

    if not destino.is_relative_to(pasta_processed):
        raise ValueError("O destino deve ficar dentro de ai/data/processed.")

    if destino.suffix.lower() != ".csv":
        raise ValueError("O destino deve ter extensão .csv.")

    if destino.exists():
        raise ValueError("O destino já existe; não será substituído.")

    with origem.open("r", encoding="utf-8-sig", newline="") as ficheiro:
        leitor = csv.DictReader(ficheiro)
        cabecalho = leitor.fieldnames

        if not cabecalho or len(cabecalho) != len(set(cabecalho)):
            raise ValueError("Cabeçalho vazio ou com colunas repetidas.")

        linhas = list(leitor)

        # DictReader usa a chave None quando uma linha tem campos a mais.
        if any(None in linha for linha in linhas):
            raise ValueError("Existem linhas com campos adicionais.")

    resultado = selecionar_alvo(linhas, opcoes.no)

    if not resultado["aceites"]:
        raise ValueError("Não existem horas completas; nenhum CSV foi criado.")

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O modo x impede substituir um resultado anterior.
    with destino.open("x", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(ficheiro, fieldnames=CAMPOS_SAIDA)
        escritor.writeheader()
        escritor.writerows(resultado["aceites"])

    print(f"Resumos analisados: {resultado['total']}")
    print(f"Horas aceites: {len(resultado['aceites'])}")
    print(f"Excluídas por cobertura parcial: {resultado['excluidas_parciais']}")
    print(f"Excluídas sem cobertura: {resultado['excluidas_sem_cobertura']}")
    print(f"CSV guardado em: {destino}")
    print("Critério inicial: 3 600 segundos integrados por hora.")
    print("Lacunas preservadas. Sem meteorologia nem treino de modelos.")


if __name__ == "__main__":
    main()