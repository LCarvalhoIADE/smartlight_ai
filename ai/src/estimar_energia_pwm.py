"""
Estima energia horária a partir do PWM e de uma potência assumida.

Hipóteses:
- Potência proporcional a led_pct.
- Variação linear da potência entre leituras.
- Limite temporal configurável para integrar intervalos.

Não cria medições de corrente nem modifica o histórico original.
Os resultados são estimativas, não medições energéticas.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ai.src.validar_historico import validar_historico


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
    "potencia_referencia_mW",
    "limite_intervalo_segundos",
    "origem_energia",
)


def numero_positivo(valor, nome):
    """Exige um número positivo e finito, excluindo booleanos."""
    if (
        type(valor) not in (int, float)
        or not math.isfinite(valor)
        or valor <= 0
    ):
        raise ValueError(f"{nome}: esperado número positivo e finito.")

    return valor


def converter_pwm(valor):
    """Aceita uma percentagem numérica entre zero e 100."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError("led_pct inválido.")

    # A API pode devolver números como texto.
    if isinstance(valor, str):
        try:
            valor = float(valor)
        except ValueError:
            raise ValueError("led_pct não numérico.") from None

    if (
        type(valor) not in (int, float)
        or not math.isfinite(valor)
        or not 0 <= valor <= 100
    ):
        raise ValueError("led_pct deve estar entre zero e 100.")

    return valor


def estimar(
    resposta,
    no_esperado,
    divisao,
    potencia_referencia_mw,
    limite_intervalo=30,
):
    """
    Estima energia de uma divisão, preservando a entrada.

    A divisão é explícita porque divisões diferentes podem possuir
    LEDs e potências de referência diferentes.

    PWM inválido interrompe o processamento.
    Intervalos longos são excluídos, sem preenchimento de falhas.
    """
    referencia = numero_positivo(
        potencia_referencia_mw, "Potência de referência"
    )
    limite = numero_positivo(limite_intervalo, "Limite temporal")

    if not isinstance(divisao, str) or not divisao.strip():
        raise ValueError("Divisão inválida.")

    # Reutiliza a validação de estrutura, nó, período e duplicados.
    validar_historico(
        resposta,
        no_esperado=no_esperado,
        limite_intervalo=limite,
    )

    leituras = [
        leitura
        for leitura in resposta["leituras"]
        if leitura["divisao"] == divisao
    ]

    if not leituras:
        raise ValueError("Não existem leituras da divisão pedida.")

    # Cria novos pontos; não altera led_pct nem corrente_ma na entrada.
    pontos = sorted(
        (
            leitura["ts"],
            referencia * (converter_pwm(leitura["led_pct"]) / 100),
        )
        for leitura in leituras
    )

    resumos = {}

    def obter_resumo(inicio_hora):
        """Cria um resumo sem inventar energia antes da integração."""
        if inicio_hora not in resumos:
            resumos[inicio_hora] = {
                "no_id": no_esperado,
                "divisao": divisao,
                "hora_utc": datetime.fromtimestamp(
                    inicio_hora, timezone.utc
                ).isoformat(),
                "energia_mWh": None,
                "energia_Wh": None,
                "segundos_integrados": 0,
                "segundos_excluidos": 0,
                "cobertura_proporcao": 0.0,
                "potencia_referencia_mW": referencia,
                "limite_intervalo_segundos": limite,
                "origem_energia": "estimativa_pwm_potencia_assumida",
            }

        return resumos[inicio_hora]

    # Uma hora com uma leitura isolada fica com energia ausente.
    for ts, _ in pontos:
        obter_resumo((ts // 3600) * 3600)

    for (ts0, potencia0), (ts1, potencia1) in zip(pontos, pontos[1:]):
        duracao = ts1 - ts0
        inicio_segmento = ts0

        # Divide cada intervalo pelas fronteiras horárias UTC.
        while inicio_segmento < ts1:
            inicio_hora = (inicio_segmento // 3600) * 3600
            fim_segmento = min(ts1, inicio_hora + 3600)
            segundos = fim_segmento - inicio_segmento
            resumo = obter_resumo(inicio_hora)

            if duracao <= limite:
                # Interpola a potência nas extremidades do segmento.
                # Preserva a energia do trapézio ao repartir por horas.
                fracao_inicio = (inicio_segmento - ts0) / duracao
                fracao_fim = (fim_segmento - ts0) / duracao
                variacao = potencia1 - potencia0

                potencia_inicio = potencia0 + variacao * fracao_inicio
                potencia_fim = potencia0 + variacao * fracao_fim

                # mW × segundos / 3600 resulta em mWh.
                # A média é escrita desta forma para evitar somar
                # diretamente dois valores de potência muito elevados.
                energia = (
                    (potencia_inicio / 2 + potencia_fim / 2)
                    * (segundos / 3600)
                )

                anterior = resumo["energia_mWh"]
                total = (0.0 if anterior is None else anterior) + energia

                if not math.isfinite(total):
                    raise ValueError("Energia estimada fora do intervalo.")

                resumo["energia_mWh"] = total
                resumo["segundos_integrados"] += segundos
            else:
                # O intervalo permanece assinalado, sem estimar energia.
                resumo["segundos_excluidos"] += segundos

            inicio_segmento = fim_segmento

    for resumo in resumos.values():
        if resumo["energia_mWh"] is not None:
            resumo["energia_Wh"] = resumo["energia_mWh"] / 1000

        resumo["cobertura_proporcao"] = (
            resumo["segundos_integrados"] / 3600
        )

    return [resumos[hora] for hora in sorted(resumos)]


def main():
    """Lê um histórico e exporta a estimativa para um novo CSV local."""
    argumentos = argparse.ArgumentParser(
        description="Estima energia por PWM com potência assumida."
    )
    argumentos.add_argument("--origem", type=Path, required=True)
    argumentos.add_argument("--destino", type=Path, required=True)
    argumentos.add_argument("--no", required=True)
    argumentos.add_argument("--divisao", required=True)
    argumentos.add_argument(
        "--potencia-referencia-mw",
        type=float,
        required=True,
        help="Potência assumida em mW quando led_pct é 100.",
    )
    argumentos.add_argument("--limite-intervalo", type=float, default=30)
    opcoes = argumentos.parse_args()

    origem = opcoes.origem.resolve()
    destino = opcoes.destino.resolve()
    pasta_processed = (AI_DIR / "data/processed").resolve()

    if origem == destino:
        raise ValueError("Origem e destino devem ser diferentes.")

    if not destino.is_relative_to(pasta_processed):
        raise ValueError("O destino deve ficar em ai/data/processed.")

    if destino.suffix.lower() != ".csv":
        raise ValueError("O destino deve ter extensão .csv.")

    if destino.exists():
        raise ValueError("O destino já existe; não será substituído.")

    resposta = json.loads(origem.read_text(encoding="utf-8-sig"))

    resumos = estimar(
        resposta,
        no_esperado=opcoes.no,
        divisao=opcoes.divisao,
        potencia_referencia_mw=opcoes.potencia_referencia_mw,
        limite_intervalo=opcoes.limite_intervalo,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O modo x impede substituir resultados anteriores.
    with destino.open("x", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(ficheiro, fieldnames=CAMPOS_SAIDA)
        escritor.writeheader()
        escritor.writerows(resumos)

    energias = [
        resumo["energia_mWh"]
        for resumo in resumos
        if resumo["energia_mWh"] is not None
    ]

    print(f"Nó: {opcoes.no} | Divisão: {opcoes.divisao}")
    print(f"Resumos horários: {len(resumos)}")
    print(f"Potência assumida a 100%: {opcoes.potencia_referencia_mw:g} mW")
    print(
        "Segundos integrados: "
        f"{sum(r['segundos_integrados'] for r in resumos)}"
    )
    print(
        "Segundos excluídos: "
        f"{sum(r['segundos_excluidos'] for r in resumos)}"
    )

    if energias:
        print(f"Energia estimada nos intervalos integrados: {sum(energias):.6f} mWh")
    else:
        print("Energia estimada: indisponível; nenhum intervalo integrado.")

    print(f"CSV guardado em: {destino}")
    print("Origem: estimativa_pwm_potencia_assumida.")
    print("Não representa energia obtida de corrente medida.")
    print("Sem preenchimento de falhas nem extrapolação nas extremidades.")


if __name__ == "__main__":
    main()