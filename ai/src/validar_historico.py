"""
Valida um histórico local obtido de historico.php.

Verifica:
- Nó e período da resposta.
- Estrutura das leituras e timestamps UTC.
- Duplicados por divisão e timestamp.
- Intervalos entre leituras, separadamente por divisão.
- Instantes de chegada ao servidor, quando disponíveis.

Históricos antigos sem recebido_ts continuam aceites,
mas a disponibilidade das respetivas leituras é desconhecida.

Não modifica os dados, não filtra leituras para uma emissão,
não preenche falhas e não calcula energia.
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
        raise ValueError(
            f"{nome}: timestamp fora do intervalo."
        ) from erro

    return valor


def data_utc(ts):
    """Representa um timestamp Unix com o fuso UTC explícito."""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def resumir_rececao(linhas):
    """
    Resume a disponibilidade das leituras já validadas.

    Ausência do campo e valor nulo são contabilizados separadamente.
    Diferenças negativas são preservadas e sinalizadas, não corrigidas.
    """
    sem_campo = sum("recebido_ts" not in linha for linha in linhas)

    nulos = sum(
        "recebido_ts" in linha and linha["recebido_ts"] is None
        for linha in linhas
    )

    diferencas = [
        linha["recebido_ts"] - linha["ts"]
        for linha in linhas
        if linha.get("recebido_ts") is not None
    ]

    return {
        "sem_campo": sem_campo,
        "nulos": nulos,
        "desconhecida": sem_campo + nulos,
        "com_timestamp": len(diferencas),
        "anteriores_a_medicao": sum(
            diferenca < 0 for diferenca in diferencas
        ),
        # Estes valores incluem diferenças negativas.
        # Não são apresentados como atrasos válidos nesses casos.
        "diferenca_minima_segundos": (
            min(diferencas) if diferencas else None
        ),
        "diferenca_maxima_segundos": (
            max(diferencas) if diferencas else None
        ),
    }


def validar_historico(resposta, no_esperado, limite_intervalo=30):
    """
    Valida a resposta e devolve um resumo por divisão.

    A cobertura temporal depende do limite configurado.
    Não comprova validade física nem cobertura energética.

    recebido_ts é opcional para preservar compatibilidade.
    Quando existe e não é nulo, deve ser um timestamp válido.
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

    # Esta condição não prova, isoladamente, que todas as páginas
    # anteriores foram efetivamente recolhidas.
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

    # Mantém os campos obrigatórios anteriores.
    # recebido_ts não se torna obrigatório nos históricos antigos.
    campos = (
        "divisao", "ts", "luz_raw", "luz_pct",
        "presenca", "led_pct", "corrente_ma", "modo",
    )

    for numero, leitura in enumerate(leituras, start=1):
        if not isinstance(leitura, dict):
            raise ValueError(f"Leitura {numero}: formato inválido.")

        if not set(campos).issubset(leitura):
            raise ValueError(f"Leitura {numero}: faltam campos.")

        divisao = leitura["divisao"]
        if not isinstance(divisao, str) or not divisao.strip():
            raise ValueError(f"Leitura {numero}: divisão inválida.")

        ts = validar_timestamp(leitura["ts"], f"Leitura {numero}")

        # O intervalo pedido à API refere-se ao instante da medição.
        if not de <= ts <= ate:
            raise ValueError(
                f"Leitura {numero}: fora do período pedido."
            )

        recebido = leitura.get("recebido_ts")

        if recebido is not None:
            validar_timestamp(
                recebido,
                f"Leitura {numero}: recebido_ts",
            )

        # Não exige recebido_ts dentro de [de, ate]:
        # uma leitura pode ter sido reenviada depois desse período.
        # recebido_ts < ts é sinalizado no resumo, sem correção.
        chave = (divisao, ts)

        if chave in identificadores:
            raise ValueError(
                f"Leitura {numero}: registo duplicado."
            )

        identificadores.add(chave)
        grupos[divisao].append(leitura)

    resumos = []

    # A API inclui ambos os limites.
    # Para medir a duração, usamos [de, ate + 1).
    duracao_pedida = ate - de + 1

    for divisao, linhas in sorted(grupos.items()):
        # sorted cria outra lista e não altera a entrada.
        ordenadas = sorted(linhas, key=lambda linha: linha["ts"])
        primeiro = ordenadas[0]["ts"]
        ultimo = ordenadas[-1]["ts"]

        intervalos = [
            atual["ts"] - anterior["ts"]
            for anterior, atual in zip(ordenadas, ordenadas[1:])
        ]

        # A cobertura continua baseada em ts, não em recebido_ts.
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

        segundos_exteriores = (
            primeiro - de + (ate + 1 - ultimo)
        )

        resumos.append({
            "divisao": divisao,
            "leituras": len(ordenadas),
            "inicio_utc": data_utc(primeiro),
            "fim_utc": data_utc(ultimo),
            "intervalo_minimo": (
                min(intervalos) if intervalos else None
            ),
            "intervalo_maximo": (
                max(intervalos) if intervalos else None
            ),
            "alertas": sum(
                intervalo > limite_intervalo
                for intervalo in intervalos
            ),
            "segundos_intervalos_aceites": segundos_aceites,
            "segundos_intervalos_longos": segundos_longos,
            "segundos_exteriores": segundos_exteriores,
            "cobertura_temporal_proporcao": (
                segundos_aceites / duracao_pedida
            ),
            # Mantém as contagens anteriores.
            # O novo campo é tratado no resumo de disponibilidade.
            "nulos": {
                campo: sum(
                    linha[campo] is None for linha in ordenadas
                )
                for campo in campos
            },
            "disponibilidade": resumir_rececao(ordenadas),
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
    """Lê um histórico local e apresenta o resumo sem escrever ficheiros."""
    argumentos = argparse.ArgumentParser(
        description="Valida um histórico local da API SmartLight."
    )
    argumentos.add_argument("--origem", type=Path, required=True)
    argumentos.add_argument("--no", required=True)
    argumentos.add_argument(
        "--limite-intervalo",
        type=float,
        default=30,
    )
    opcoes = argumentos.parse_args()

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
    print(
        f"Limite provisório: {resumo['limite_intervalo']:g} segundos"
    )

    for grupo in resumo["grupos"]:
        print(f"\nDivisão: {grupo['divisao']}")
        print(f"Leituras: {grupo['leituras']}")
        print(f"Início UTC: {grupo['inicio_utc']}")
        print(f"Fim UTC: {grupo['fim_utc']}")
        print(
            "Intervalos mínimo/máximo (segundos): "
            f"{grupo['intervalo_minimo']} / "
            f"{grupo['intervalo_maximo']}"
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
        print(
            f"Segundos exteriores: {grupo['segundos_exteriores']}"
        )
        print(
            "Cobertura temporal segundo o limite: "
            f"{grupo['cobertura_temporal_proporcao']:.4%}"
        )
        print(f"Valores nulos: {grupo['nulos']}")

        disponibilidade = grupo["disponibilidade"]

        print(
            "recebido_ts ausente / nulo / com timestamp: "
            f"{disponibilidade['sem_campo']} / "
            f"{disponibilidade['nulos']} / "
            f"{disponibilidade['com_timestamp']}"
        )
        print(
            "Disponibilidade desconhecida: "
            f"{disponibilidade['desconhecida']}"
        )
        print(
            "Chegadas anteriores à medição: "
            f"{disponibilidade['anteriores_a_medicao']}"
        )

        if disponibilidade["com_timestamp"]:
            print(
                "Diferença chegada - medição, mínimo/máximo (s): "
                f"{disponibilidade['diferenca_minima_segundos']} / "
                f"{disponibilidade['diferenca_maxima_segundos']}"
            )

    print("\nCobertura temporal não equivale a cobertura energética.")
    print("Valores físicos dos sensores ainda não validados neste módulo.")
    print("Não foi aplicada seleção para um instante de emissão.")
    print("Diferenças temporais negativas exigem investigação.")
    print("Ficheiro original preservado. Nenhum ficheiro de saída criado.")


if __name__ == "__main__":
    main()