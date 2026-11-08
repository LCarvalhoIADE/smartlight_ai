"""
Calcula energia horária a partir de corrente medida e tensão assumida.

Hipóteses desta versão:
- Tensão constante, por omissão 3,3 V.
- Variação linear da potência entre duas leituras válidas.
- Intervalo máximo de 30 segundos, configurável e provisório.

As correntes medidas são preservadas, incluindo pequenos valores
registados durante transições do PWM. Segundo o responsável pelo
firmware, a média do INA219 abrange aproximadamente 70 ms.

A cobertura corresponde ao tempo incluído na integração.
Os períodos exteriores à primeira e à última leitura ficam sem estimativa.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]

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
def numero_finito(valor):
    """Aceita números reais finitos, excluindo valores booleanos."""
    return type(valor) in (int, float) and math.isfinite(valor)


def calcular(resposta, tensao_v=3.3, limite_intervalo=30):
    """
    Devolve resumos horários para as divisões de um único nó.

    Recebe a resposta JSON de historico.php já convertida num dicionário.
    A entrada permanece intacta.

    Corrente ausente, negativa ou não finita torna inválidos os
    intervalos que utilizam essa leitura. Esses períodos são contabilizados
    como excluídos. Estruturas inválidas e duplicados geram ValueError.
    """
    # Valida os parâmetros físicos e temporais do cálculo.
    if not numero_finito(tensao_v) or tensao_v <= 0:
        raise ValueError("A tensão deve ser positiva e finita.")

    if not numero_finito(limite_intervalo) or limite_intervalo <= 0:
        raise ValueError("O limite deve ser positivo e finito.")

    if not isinstance(resposta, dict):
        raise ValueError("Esperada uma resposta JSON em formato de objeto.")

    # Exige uma resposta completa para evitar processar apenas uma página.
    if resposta.get("mais") is not False:
        raise ValueError("A resposta deve ter mais=false.")

    no = resposta.get("no")
    if not isinstance(no, dict):
        raise ValueError("Faltam os metadados do nó.")

    no_id = no.get("no_id")
    if not isinstance(no_id, str) or not no_id.strip():
        raise ValueError("Identificador do nó inválido.")

    leituras = resposta.get("leituras")
    if not isinstance(leituras, list) or not leituras:
        raise ValueError("Esperada uma lista não vazia de leituras.")

    grupos = defaultdict(list)
    identificadores = set()

    for numero, leitura in enumerate(leituras, start=1):
        if not isinstance(leitura, dict):
            raise ValueError(f"Leitura {numero}: formato inválido.")

        if not {"divisao", "ts", "corrente_ma"}.issubset(leitura):
            raise ValueError(f"Leitura {numero}: faltam campos.")

        divisao = leitura["divisao"]
        ts = leitura["ts"]
        corrente = leitura["corrente_ma"]

        if not isinstance(divisao, str) or not divisao.strip():
            raise ValueError(f"Leitura {numero}: divisão inválida.")

        if type(ts) is not int or ts <= 0:
            raise ValueError(f"Leitura {numero}: timestamp inválido.")

        # Confirma que o timestamp pode ser convertido para uma data UTC.
        try:
            datetime.fromtimestamp(ts, timezone.utc)
        except (ValueError, OverflowError, OSError) as erro:
            raise ValueError(
                f"Leitura {numero}: timestamp fora do intervalo."
            ) from erro

        chave = (divisao, ts)
        if chave in identificadores:
            raise ValueError(f"Leitura {numero}: registo duplicado.")
        identificadores.add(chave)

        # Aceita números JSON ou texto numérico devolvido pela API.
        # None representa uma medição ausente.
        if isinstance(corrente, str):
            try:
                corrente = float(corrente)
            except ValueError as erro:
                raise ValueError(
                    f"Leitura {numero}: corrente não numérica."
                ) from erro

        if corrente is not None and type(corrente) not in (int, float):
            raise ValueError(f"Leitura {numero}: tipo de corrente inválido.")

        # V × mA produz mW.
        # Correntes inválidas ficam assinaladas para excluir os intervalos.
        potencia = None
        if numero_finito(corrente) and corrente >= 0:
            potencia = tensao_v * corrente
            if not math.isfinite(potencia):
                raise ValueError(f"Leitura {numero}: potência fora do intervalo.")

        grupos[divisao].append((ts, potencia))

    resumos = {}

    for divisao, pontos in grupos.items():
        pontos.sort(key=lambda ponto: ponto[0])

        # Cria também uma linha para horas que tenham uma leitura isolada.
        # A energia fica ausente até existir um intervalo válido integrado.
        def obter_resumo(inicio_hora):
            chave = (divisao, inicio_hora)
            if chave not in resumos:
                resumos[chave] = {
                    "no_id": no_id,
                    "divisao": divisao,
                    "hora_utc": datetime.fromtimestamp(
                        inicio_hora, timezone.utc
                    ).isoformat(),
                    "energia_mWh": None,
                    "energia_Wh": None,
                    "segundos_integrados": 0,
                    "segundos_excluidos": 0,
                    "cobertura_proporcao": 0.0,
                    "tensao_assumida_v": tensao_v,
                    "limite_intervalo_segundos": limite_intervalo,
                    "origem_energia": "corrente_medida_tensao_assumida",
                }
            return resumos[chave]

        for ts, _ in pontos:
            obter_resumo((ts // 3600) * 3600)

        for anterior, atual in zip(pontos, pontos[1:]):
            ts_anterior, potencia_anterior = anterior
            ts_atual, potencia_atual = atual
            duracao = ts_atual - ts_anterior

            valido = (
                duracao <= limite_intervalo
                and potencia_anterior is not None
                and potencia_atual is not None
            )

            # Divide o intervalo nas fronteiras das horas UTC.
            # Cada segmento pertence ao intervalo [início, fim).
            inicio_segmento = ts_anterior

            while inicio_segmento < ts_atual:
                inicio_hora = (inicio_segmento // 3600) * 3600
                fim_segmento = min(ts_atual, inicio_hora + 3600)
                segundos = fim_segmento - inicio_segmento
                resumo = obter_resumo(inicio_hora)

                if valido:
                    # Interpola a potência nas duas extremidades do segmento.
                    # Isto preserva o resultado do trapézio original ao
                    # repartir a energia entre horas diferentes.
                    fracao_inicio = (
                        inicio_segmento - ts_anterior
                    ) / duracao
                    fracao_fim = (
                        fim_segmento - ts_anterior
                    ) / duracao

                    variacao = potencia_atual - potencia_anterior
                    potencia_inicio = (
                        potencia_anterior + variacao * fracao_inicio
                    )
                    potencia_fim = (
                        potencia_anterior + variacao * fracao_fim
                    )

                    energia = (
                        (potencia_inicio + potencia_fim)
                        / 2
                        * segundos
                        / 3600
                    )

                    if resumo["energia_mWh"] is None:
                        resumo["energia_mWh"] = 0.0

                    resumo["energia_mWh"] += energia
                    resumo["segundos_integrados"] += segundos
                else:
                    # Uma medição inválida mantém a separação entre intervalos.
                    # A sua remoção ligaria artificialmente pontos mais distantes.
                    resumo["segundos_excluidos"] += segundos

                inicio_segmento = fim_segmento

    for resumo in resumos.values():
        if resumo["energia_mWh"] is not None:
            resumo["energia_Wh"] = resumo["energia_mWh"] / 1000

        # Cada hora UTC tem 3 600 segundos.
        resumo["cobertura_proporcao"] = (
            resumo["segundos_integrados"] / 3600
        )

    return sorted(
        resumos.values(),
        key=lambda resumo: (resumo["hora_utc"], resumo["divisao"]),
    )


def main():
    """Lê o JSON local e exporta a energia horária para CSV."""
    argumentos = argparse.ArgumentParser(
        description="Calcula energia horária com corrente medida."
    )
    argumentos.add_argument(
        "--origem",
        type=Path,
        default=AI_DIR / "data/raw/no1_historico_2026-11-02.json",
    )
    argumentos.add_argument(
        "--destino",
        type=Path,
        default=AI_DIR / "data/processed/no1_energia_2026-11-02.csv",
    )
    argumentos.add_argument("--tensao", type=float, default=3.3)
    argumentos.add_argument("--limite-intervalo", type=float, default=30)
    opcoes = argumentos.parse_args()

    # Impede que o destino coincida com o ficheiro original.
    if opcoes.origem.resolve() == opcoes.destino.resolve():
        raise ValueError("A origem e o destino devem ser diferentes.")

    resposta = json.loads(
        opcoes.origem.read_text(encoding="utf-8-sig")
    )
    resumos = calcular(
        resposta,
        tensao_v=opcoes.tensao,
        limite_intervalo=opcoes.limite_intervalo,
    )

    # Todos os cálculos e validações terminam antes de abrir o CSV.
    opcoes.destino.parent.mkdir(parents=True, exist_ok=True)
    with opcoes.destino.open(
        "w", encoding="utf-8", newline=""
    ) as ficheiro:
        escritor = csv.DictWriter(ficheiro, fieldnames=CAMPOS_SAIDA)
        escritor.writeheader()
        escritor.writerows(resumos)

    # Os totais abrangem exclusivamente os intervalos integrados.
    total_mwh = sum(
        resumo["energia_mWh"]
        for resumo in resumos
        if resumo["energia_mWh"] is not None
    )
    integrados = sum(r["segundos_integrados"] for r in resumos)
    excluidos = sum(r["segundos_excluidos"] for r in resumos)

    print(f"Nó: {resposta['no']['no_id']}")
    print(f"Leituras recebidas: {len(resposta['leituras'])}")
    print(f"Resumos horários: {len(resumos)}")
    print(f"Tensão assumida: {opcoes.tensao:g} V")
    print(f"Limite provisório: {opcoes.limite_intervalo:g} segundos")
    print(f"Segundos integrados, somados por divisão: {integrados}")
    print(f"Segundos excluídos, somados por divisão: {excluidos}")
    print(f"Energia nos intervalos integrados: {total_mwh:.6f} mWh")
    print(f"Energia nos intervalos integrados: {total_mwh / 1000:.9f} Wh")
    print(f"CSV guardado em: {opcoes.destino}")


# Permite importar as funções nos testes sem executar main().
if __name__ == "__main__":
    main()