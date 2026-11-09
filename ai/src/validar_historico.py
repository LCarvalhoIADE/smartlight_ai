"""
Valida um histórico local obtido de historico.php.

Verifica:
- Nó e período da resposta.
- Estrutura das leituras e timestamps UTC.
- Duplicados por divisão e timestamp.
- Intervalos entre leituras, separadamente por divisão.

Não modifica os dados, não preenche falhas e não calcula energia.
"""

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def validar_timestamp(valor, nome):
    """Exige segundos Unix inteiros, positivos e convertíveis para UTC."""
    # bool é excluído, embora em Python seja uma subclasse de int.
    if type(valor) is not int or valor <= 0:
        raise ValueError(f"{nome}: timestamp inválido.")

    try:
        datetime.fromtimestamp(valor, timezone.utc)
    except (ValueError, OverflowError, OSError) as erro:
        raise ValueError(f"{nome}: timestamp fora do intervalo.") from erro

    return valor


def data_utc(ts):
    """Representa um timestamp Unix como texto com o fuso UTC explícito."""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def validar_historico(resposta, no_esperado, limite_intervalo=30):
    """
    Valida a resposta e devolve um resumo por divisão.

    O limite é uma hipótese configurável para sinalizar intervalos longos.
    A cobertura abaixo é temporal e depende dessa hipótese; não comprova
    a validade física dos sensores nem corresponde à cobertura energética.
    """
    if not isinstance(no_esperado, str) or not no_esperado.strip():
        raise ValueError("Identificador do nó esperado inválido.")

    if (
        type(limite_intervalo) not in (int, float)
        or not math.isfinite(limite_intervalo)
        or limite_intervalo <= 0
    ):
        raise ValueError("O limite deve ser positivo e finito.")

    if not isinstance(resposta, dict):
        raise ValueError("Esperado um objeto JSON.")

    # Esta condição é necessária, mas não prova, por si só,
    # que todas as páginas anteriores foram recolhidas.
    if resposta.get("mais") is not False:
        raise ValueError("O histórico ainda indica páginas pendentes.")

    no = resposta.get("no")
    if not isinstance(no, dict) or no.get("no_id") != no_esperado:
        raise ValueError("O nó não corresponde ao esperado.")

    de = validar_timestamp(resposta.get("de"), "de")
    ate = validar_timestamp(resposta.get("ate"), "ate")

    if de > ate:
        raise ValueError("O início do período é posterior ao fim.")

    leituras = resposta.get("leituras")
    if not isinstance(leituras, list) or not leituras:
        raise ValueError("Esperada uma lista não vazia de leituras.")

    grupos = defaultdict(list)
    identificadores = set()
    campos = (
        "divisao", "ts", "luz_raw", "luz_pct",
        "presenca", "led_pct", "corrente_ma", "modo",
    )

    # A validação é feita antes de produzir qualquer resumo.
    for numero, leitura in enumerate(leituras, start=1):
        if not isinstance(leitura, dict):
            raise ValueError(f"Leitura {numero}: formato inválido.")

        if not set(campos).issubset(leitura):
            raise ValueError(f"Leitura {numero}: faltam campos.")

        divisao = leitura["divisao"]
        if not isinstance(divisao, str) or not divisao.strip():
            raise ValueError(f"Leitura {numero}: divisão inválida.")

        ts = validar_timestamp(leitura["ts"], f"Leitura {numero}")

        if not de <= ts <= ate:
            raise ValueError(f"Leitura {numero}: fora do período pedido.")

        chave = (divisao, ts)
        if chave in identificadores:
            raise ValueError(f"Leitura {numero}: registo duplicado.")

        identificadores.add(chave)
        grupos[divisao].append(leitura)

    resumos = []

    # A API inclui os dois limites. Para medir a duração pedida,
    # representamos o período como [de, ate + 1).
    duracao_pedida = ate - de + 1

    for divisao, linhas in sorted(grupos.items()):
        # sorted cria outra lista, preservando a ordem da entrada.
        ordenadas = sorted(linhas, key=lambda linha: linha["ts"])
        primeiro = ordenadas[0]["ts"]
        ultimo = ordenadas[-1]["ts"]

        intervalos = [
            atual["ts"] - anterior["ts"]
            for anterior, atual in zip(ordenadas, ordenadas[1:])
        ]

        # Conta tempo apenas entre pares suficientemente próximos.
        # A classificação não depende da corrente ou do estado do LED.
        segundos_aceites = sum(
            intervalo
            for intervalo in intervalos
            if intervalo <= limite_intervalo
        )
        segundos_longos = sum(
            intervalo
            for intervalo in intervalos
            if intervalo > limite_intervalo
        )

        # Não extrapolamos antes da primeira ou depois da última leitura.
        segundos_exteriores = (
            primeiro - de + (ate + 1 - ultimo)
        )

        resumos.append({
            "divisao": divisao,
            "leituras": len(ordenadas),
            "inicio_utc": data_utc(primeiro),
            "fim_utc": data_utc(ultimo),
            "intervalo_minimo": min(intervalos) if intervalos else None,
            "intervalo_maximo": max(intervalos) if intervalos else None,
            "alertas": sum(
                intervalo > limite_intervalo for intervalo in intervalos
            ),
            "segundos_intervalos_aceites": segundos_aceites,
            "segundos_intervalos_longos": segundos_longos,
            "segundos_exteriores": segundos_exteriores,
            "cobertura_temporal_proporcao": (
                segundos_aceites / duracao_pedida
            ),
            # Conta apenas ausências explícitas (None).
            # Zero não é tratado como ausência de medição.
            "nulos": {
                campo: sum(linha[campo] is None for linha in ordenadas)
                for campo in campos
            },
        })

    return {
        "no_id": no_esperado,
        "total": len(leituras),
        "de": de,
        "ate": ate,
        "limite_intervalo": limite_intervalo,
        "grupos": resumos,
    }


def main():
    """Lê um ficheiro local e apresenta a validação no terminal."""
    argumentos = argparse.ArgumentParser(
        description="Valida um histórico local da API SmartLight."
    )
    argumentos.add_argument("--origem", type=Path, required=True)
    argumentos.add_argument("--no", required=True)
    argumentos.add_argument("--limite-intervalo", type=float, default=30)
    opcoes = argumentos.parse_args()

    # utf-8-sig aceita JSON com ou sem o BOM criado pelo PowerShell.
    resposta = json.loads(
        opcoes.origem.read_text(encoding="utf-8-sig")
    )
    resumo = validar_historico(
        resposta,
        no_esperado=opcoes.no,
        limite_intervalo=opcoes.limite_intervalo,
    )

    print(f"Nó: {resumo['no_id']}")
    print(f"Leituras validadas: {resumo['total']}")
    print("Duplicados: 0 | Leituras fora do período: 0")
    print(f"Limite provisório: {resumo['limite_intervalo']:g} segundos")

    for grupo in resumo["grupos"]:
        print(f"\nDivisão: {grupo['divisao']}")
        print(f"Leituras: {grupo['leituras']}")
        print(f"Início UTC: {grupo['inicio_utc']}")
        print(f"Fim UTC: {grupo['fim_utc']}")
        print(
            "Intervalos mínimo/máximo (segundos): "
            f"{grupo['intervalo_minimo']} / {grupo['intervalo_maximo']}"
        )
        print(f"Intervalos superiores ao limite: {grupo['alertas']}")
        print(
            "Segundos em intervalos aceites: "
            f"{grupo['segundos_intervalos_aceites']}"
        )
        print(
            "Segundos em intervalos longos: "
            f"{grupo['segundos_intervalos_longos']}"
        )
        print(f"Segundos exteriores: {grupo['segundos_exteriores']}")
        print(
            "Cobertura temporal segundo o limite: "
            f"{grupo['cobertura_temporal_proporcao']:.4%}"
        )
        print(f"Valores nulos: {grupo['nulos']}")

    print("\nCobertura temporal não equivale a cobertura energética.")
    print("Valores físicos dos sensores ainda não validados neste módulo.")
    print("Ficheiro original preservado. Nenhum ficheiro de saída criado.")


if __name__ == "__main__":
    main()