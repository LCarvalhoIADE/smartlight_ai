"""
Prepara o alvo energético a partir de resumos horários.

Origens suportadas:
- Corrente medida com tensão assumida.
- Estimativa por PWM com potência de referência assumida.

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

ORIGEM_CORRENTE = "corrente_medida_tensao_assumida"
ORIGEM_PWM = "estimativa_pwm_potencia_assumida"

# Campos exigidos para ambas as origens.
CAMPOS_COMUNS = (
    "no_id",
    "divisao",
    "hora_utc",
    "energia_mWh",
    "energia_Wh",
    "segundos_integrados",
    "segundos_excluidos",
    "cobertura_proporcao",
    "limite_intervalo_segundos",
    "origem_energia",
)

# A saída conserva as duas referências possíveis.
# A referência que não se aplica fica None, ou vazia no CSV.
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
    "potencia_referencia_mW",
    "limite_intervalo_segundos",
    "origem_energia",
)


def ausente(valor):
    """Reconhece ausência sem confundir o valor zero com uma célula vazia."""
    return valor is None or (
        isinstance(valor, str) and not valor.strip()
    )


def numero(valor, campo):
    """Converte um número e rejeita booleanos, ausências e infinitos."""
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
    """Distingue energia ausente de energia calculada igual a zero."""
    if ausente(valor):
        return None

    convertido = numero(valor, campo)

    if convertido < 0:
        raise ValueError(f"{campo}: energia negativa.")

    return convertido


def validar_referencia(linha):
    """
    Valida a referência exigida pela origem energética.

    Não converte potência em tensão nem cria valores para campos
    que não pertencem ao método de cálculo.
    """
    origem = linha["origem_energia"]

    if origem == ORIGEM_CORRENTE:
        campo_obrigatorio = "tensao_assumida_v"
        campo_nao_aplicavel = "potencia_referencia_mW"
    elif origem == ORIGEM_PWM:
        campo_obrigatorio = "potencia_referencia_mW"
        campo_nao_aplicavel = "tensao_assumida_v"
    else:
        raise ValueError("Origem energética não suportada.")

    if campo_obrigatorio not in linha:
        raise ValueError(
            f"Falta o campo obrigatório {campo_obrigatorio}."
        )

    referencia = numero(linha[campo_obrigatorio], campo_obrigatorio)

    if referencia <= 0:
        raise ValueError(
            f"{campo_obrigatorio}: a referência deve ser positiva."
        )

    # Aceita a coluna não aplicável ausente ou vazia.
    # Um valor preenchido seria ambíguo e não deve ser descartado.
    if not ausente(linha.get(campo_nao_aplicavel)):
        raise ValueError(
            f"{campo_nao_aplicavel}: campo não aplicável à origem."
        )

    if origem == ORIGEM_CORRENTE:
        return referencia, None

    return None, referencia


def selecionar_alvo(linhas, no_esperado):
    """
    Valida os resumos e seleciona as horas energeticamente completas.

    Estruturas inválidas interrompem o processamento.
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

        if not set(CAMPOS_COMUNS).issubset(linha):
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

        # A cobertura declarada deve corresponder aos segundos integrados.
        if not 0 <= cobertura <= 1 or not math.isclose(
            cobertura,
            integrados / 3600,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError(f"Linha {indice}: cobertura incoerente.")

        energia_mwh = energia_opcional(linha["energia_mWh"], "energia_mWh")
        energia_wh = energia_opcional(linha["energia_Wh"], "energia_Wh")

        if (energia_mwh is None) != (energia_wh is None):
            raise ValueError(f"Linha {indice}: unidades energéticas incompletas.")

        if energia_mwh is not None and not math.isclose(
            energia_wh,
            energia_mwh / 1000,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError(f"Linha {indice}: unidades energéticas incoerentes.")

        # Ambos os produtores só calculam energia quando integram tempo.
        if (integrados == 0) != (energia_mwh is None):
            raise ValueError(
                f"Linha {indice}: energia incompatível com o tempo integrado."
            )

        limite = numero(
            linha["limite_intervalo_segundos"],
            "limite_intervalo_segundos",
        )

        if limite <= 0:
            raise ValueError(f"Linha {indice}: limite temporal inválido.")

        tensao, potencia = validar_referencia(linha)
        origem = linha["origem_energia"]

        # Uma divisão não pode misturar origens ou configurações neste lote.
        # Mudanças de configuração exigem tratamento por períodos separados.
        configuracao = (origem, tensao, potencia, limite)

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

        # Cria um novo registo, mantendo a origem e a referência aplicável.
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
            "potencia_referencia_mW": potencia,
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

        # Campos a mais produzem a chave None.
        # Campos a menos produzem valores None; no CSV, uma célula
        # intencionalmente vazia é representada por uma string vazia.
        if any(
            None in linha or any(valor is None for valor in linha.values())
            for linha in linhas
        ):
            raise ValueError("Existem linhas com número incorreto de campos.")

    resultado = selecionar_alvo(linhas, opcoes.no)

    if not resultado["aceites"]:
        raise ValueError("Não existem horas completas; nenhum CSV foi criado.")

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O modo x impede substituir um resultado anterior.
    # None é escrito como uma célula vazia.
    with destino.open("x", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(ficheiro, fieldnames=CAMPOS_SAIDA)
        escritor.writeheader()
        escritor.writerows(resultado["aceites"])

    origens = sorted({
        linha["origem_energia"] for linha in resultado["aceites"]
    })

    print(f"Resumos analisados: {resultado['total']}")
    print(f"Horas aceites: {len(resultado['aceites'])}")
    print(f"Excluídas por cobertura parcial: {resultado['excluidas_parciais']}")
    print(f"Excluídas sem cobertura: {resultado['excluidas_sem_cobertura']}")
    print(f"Origens preservadas: {', '.join(origens)}")
    print(f"CSV guardado em: {destino}")
    print("Critério inicial: 3 600 segundos integrados por hora.")
    print("Referências não aplicáveis ficam vazias.")
    print("Lacunas preservadas. Sem meteorologia nem treino de modelos.")


if __name__ == "__main__":
    main()