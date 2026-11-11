"""
Analisa a cobertura energética por dia UTC e divisão.

Reutiliza a validação e o cálculo energético existentes.
Localiza correntes ausentes por hora, sem alterar os dados.

Não preenche falhas, não estima energia em falta e não decide
quais as horas que serão utilizadas no treino.
"""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ai.src.calcular_energia import calcular
from ai.src.validar_historico import validar_historico


def analisar_cobertura(resposta, no_esperado, tensao_v=3.3, limite=30):
    """Devolve resumos diários, horas incompletas e ausências de corrente."""
    # Confirma a estrutura, o nó, os timestamps e os duplicados.
    validacao = validar_historico(
        resposta,
        no_esperado=no_esperado,
        limite_intervalo=limite,
    )

    de = validacao["de"]
    ate = validacao["ate"]

    # Nesta versão, o relatório compara dias UTC completos.
    # Os ficheiros criados pelo nosso adquiridor seguem esta convenção.
    if de % 86400 != 0 or (ate + 1) % 86400 != 0:
        raise ValueError("O relatório exige dias completos em UTC.")

    # Usa exatamente as mesmas regras do módulo energético.
    horarios = calcular(
        resposta,
        tensao_v=tensao_v,
        limite_intervalo=limite,
    )

    por_hora = {
        (linha["divisao"], linha["hora_utc"]): linha
        for linha in horarios
    }
    divisoes = sorted(
        {leitura["divisao"] for leitura in resposta["leituras"]}
    )

    # Conta apenas correntes explicitamente ausentes.
    # Correntes negativas ou não finitas são outro tipo de problema.
    ausencias = Counter()

    for leitura in resposta["leituras"]:
        if leitura["corrente_ma"] is None:
            hora_ts = (leitura["ts"] // 3600) * 3600
            hora_utc = datetime.fromtimestamp(
                hora_ts, timezone.utc
            ).isoformat()
            ausencias[(leitura["divisao"], hora_utc)] += 1

    diarios = []
    incompletas = []

    for divisao in divisoes:
        for inicio_dia in range(de, ate + 1, 86400):
            dia = datetime.fromtimestamp(
                inicio_dia, timezone.utc
            ).date().isoformat()

            completas = 0
            parciais = 0
            sem_cobertura = 0
            integrados_dia = 0
            excluidos_dia = 0
            sem_intervalo_dia = 0
            ausentes_dia = 0
            energias = []

            # Inspeciona todas as 24 horas, incluindo as que não
            # possuem uma linha no resultado do cálculo energético.
            for inicio_hora in range(
                inicio_dia, inicio_dia + 86400, 3600
            ):
                hora_utc = datetime.fromtimestamp(
                    inicio_hora, timezone.utc
                ).isoformat()

                chave = (divisao, hora_utc)
                linha = por_hora.get(chave)

                integrados = (
                    linha["segundos_integrados"] if linha else 0
                )
                excluidos = (
                    linha["segundos_excluidos"] if linha else 0
                )

                # Tempo sem um intervalo entre duas leituras:
                # por exemplo, antes da primeira ou após a última.
                sem_intervalo = 3600 - integrados - excluidos

                if sem_intervalo < 0:
                    raise ValueError(
                        "A contagem temporal ultrapassa uma hora."
                    )

                if integrados == 3600:
                    completas += 1
                elif integrados > 0:
                    parciais += 1
                else:
                    sem_cobertura += 1

                integrados_dia += integrados
                excluidos_dia += excluidos
                sem_intervalo_dia += sem_intervalo
                ausentes_dia += ausencias[chave]

                # None não é convertido em energia zero.
                if linha is not None and linha["energia_mWh"] is not None:
                    energias.append(linha["energia_mWh"])

                if integrados < 3600:
                    incompletas.append({
                        "divisao": divisao,
                        "hora_utc": hora_utc,
                        "segundos_integrados": integrados,
                        "segundos_excluidos": excluidos,
                        "segundos_sem_intervalo": sem_intervalo,
                        "correntes_ausentes": ausencias[chave],
                    })

            diarios.append({
                "divisao": divisao,
                "dia_utc": dia,
                "horas_completas": completas,
                "horas_parciais": parciais,
                "horas_sem_cobertura": sem_cobertura,
                "segundos_integrados": integrados_dia,
                "segundos_excluidos": excluidos_dia,
                "segundos_sem_intervalo": sem_intervalo_dia,
                "cobertura_proporcao": integrados_dia / 86400,
                "correntes_ausentes": ausentes_dia,
                "energia_integrada_mWh": (
                    sum(energias) if energias else None
                ),
            })

    return {
        "no_id": no_esperado,
        "diarios": diarios,
        "horas_incompletas": incompletas,
    }


def main():
    """Lê o JSON e apresenta um relatório sem escrever ficheiros."""
    argumentos = argparse.ArgumentParser(
        description="Analisa cobertura energética por dia UTC."
    )
    argumentos.add_argument("--origem", type=Path, required=True)
    argumentos.add_argument("--no", required=True)
    argumentos.add_argument("--tensao", type=float, default=3.3)
    argumentos.add_argument("--limite-intervalo", type=float, default=30)
    argumentos.add_argument(
        "--detalhes",
        action="store_true",
        help="Mostra individualmente as horas sem cobertura completa.",
    )
    opcoes = argumentos.parse_args()

    resposta = json.loads(
        opcoes.origem.read_text(encoding="utf-8-sig")
    )
    resultado = analisar_cobertura(
        resposta,
        no_esperado=opcoes.no,
        tensao_v=opcoes.tensao,
        limite=opcoes.limite_intervalo,
    )

    print(f"Nó: {resultado['no_id']}")
    print(f"Tensão assumida: {opcoes.tensao:g} V")
    print(f"Limite provisório: {opcoes.limite_intervalo:g} segundos")

    for dia in resultado["diarios"]:
        energia = dia["energia_integrada_mWh"]
        energia_texto = (
            "sem dados" if energia is None else f"{energia:.6f} mWh"
        )

        print(f"\nDia UTC: {dia['dia_utc']} | Divisão: {dia['divisao']}")
        print(
            "Horas completas / parciais / sem cobertura: "
            f"{dia['horas_completas']} / "
            f"{dia['horas_parciais']} / "
            f"{dia['horas_sem_cobertura']}"
        )
        print(f"Cobertura energética: {dia['cobertura_proporcao']:.4%}")
        print(f"Correntes ausentes: {dia['correntes_ausentes']}")
        print(f"Energia nos intervalos integrados: {energia_texto}")
        print(
            "Segundos integrados / excluídos / sem intervalo: "
            f"{dia['segundos_integrados']} / "
            f"{dia['segundos_excluidos']} / "
            f"{dia['segundos_sem_intervalo']}"
        )

    if opcoes.detalhes:
        print("\nHoras sem cobertura energética completa:")

        for hora in resultado["horas_incompletas"]:
            print(
                f"{hora['divisao']} | {hora['hora_utc']} | "
                f"integrados={hora['segundos_integrados']} s | "
                f"excluídos={hora['segundos_excluidos']} s | "
                f"sem intervalo={hora['segundos_sem_intervalo']} s | "
                f"correntes ausentes={hora['correntes_ausentes']}"
            )

    print("\nCobertura completa refere-se às regras de integração utilizadas.")
    print("Não comprova a precisão física das medições.")
    print("Nenhuma falha foi preenchida e nenhum critério de treino foi aplicado.")
    print("Original preservado. Nenhum ficheiro de saída criado.")


if __name__ == "__main__":
    main()