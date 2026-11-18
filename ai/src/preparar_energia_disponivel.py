"""
Prepara energia histórica disponível no instante de uma emissão.

Filtra as leituras, integra cada segmento separadamente e reúne os
resultados por hora UTC de uma divisão. Não prepara alvos futuros.
Não consulta APIs, não escreve ficheiros e não treina modelos.
"""

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from ai.src.calcular_energia import calcular
from ai.src.estimar_energia_pwm import estimar, numero_positivo
from ai.src.selecionar_leituras_disponiveis import selecionar


def preparar(
    resposta, no_esperado, divisao, emissao, *,
    metodo, tensao_v=None, potencia_referencia_mw=None,
    margem_minutos=5, limite_intervalo=30,
):
    """Devolve resumos disponíveis e motivos de exclusão, sem alterar a entrada."""
    if not isinstance(divisao, str) or not divisao.strip():
        raise ValueError("Divisão inválida.")
    numero_positivo(limite_intervalo, "Limite temporal")

    # As referências são explícitas e nunca são copiadas de outro nó.
    if metodo == "corrente":
        numero_positivo(tensao_v, "Tensão assumida")
        if potencia_referencia_mw is not None:
            raise ValueError("Potência de referência não se aplica à corrente.")
    elif metodo == "pwm":
        numero_positivo(potencia_referencia_mw, "Potência de referência")
        if tensao_v is not None:
            raise ValueError("Tensão não se aplica ao método PWM.")
    else:
        raise ValueError("Método inválido: use corrente ou pwm.")

    selecao = selecionar(resposta, no_esperado, emissao, margem_minutos)
    total = sum(linha["divisao"] == divisao for linha in resposta["leituras"])
    if not total:
        raise ValueError("Não existem leituras da divisão pedida.")

    segmentos = [
        item for item in selecao["segmentos"] if item["divisao"] == divisao
    ]
    excluidas = [
        item for item in selecao["excluidas"] if item["divisao"] == divisao
    ]
    por_hora = {}

    for segmento in segmentos:
        # Não concatenar segmentos: uma exclusão tem de continuar a ser
        # uma interrupção, mesmo que os pontos vizinhos distem só 30 s.
        parcial = {**resposta, "leituras": segmento["leituras"]}
        if metodo == "corrente":
            linhas = calcular(parcial, tensao_v, limite_intervalo)
        else:
            linhas = estimar(
                parcial, no_esperado, divisao,
                potencia_referencia_mw, limite_intervalo,
            )

        for linha in linhas:
            hora = linha["hora_utc"]
            if hora not in por_hora:
                resumo = dict(linha)
                resumo.update({
                    "energia_mWh": None,
                    "energia_Wh": None,
                    "segundos_integrados": 0,
                    "segundos_excluidos": 0,
                    "tensao_assumida_v": tensao_v,
                    "potencia_referencia_mW": potencia_referencia_mw,
                    "emissao_utc": selecao["emissao_utc"],
                    "corte_utc": selecao["corte_utc"],
                    "margem_minutos": margem_minutos,
                    "finalidade": "entrada_historica",
                })
                por_hora[hora] = resumo

            resumo = por_hora[hora]
            for campo in ("segundos_integrados", "segundos_excluidos"):
                resumo[campo] += linha[campo]

            # None continua ausente; zero medido/estimado continua zero.
            energia = linha["energia_mWh"]
            if energia is not None:
                anterior = resumo["energia_mWh"]
                soma = (0.0 if anterior is None else anterior) + energia
                if not math.isfinite(soma):
                    raise ValueError("Energia consolidada não finita.")
                resumo["energia_mWh"] = soma

    resumos = []
    for hora in sorted(por_hora):
        resumo = por_hora[hora]
        integrados = resumo["segundos_integrados"]
        excluidos = resumo["segundos_excluidos"]
        if integrados < 0 or excluidos < 0 or integrados + excluidos > 3600:
            raise ValueError("Contabilização temporal inconsistente.")

        # São segundos sem um intervalo formado por pontos disponíveis.
        # Incluem extremidades e lacunas; não são energia igual a zero.
        resumo["segundos_sem_intervalo"] = 3600 - integrados - excluidos
        resumo["cobertura_proporcao"] = integrados / 3600
        resumo["hora_completa"] = integrados == 3600
        energia = resumo["energia_mWh"]
        if resumo["hora_completa"] and energia is None:
            raise ValueError("Hora completa sem energia válida.")

        resumo["energia_Wh"] = None if energia is None else energia / 1000

        # Esta coluna só fornece energia horária quando a hora é completa.
        # energia_mWh conserva o subtotal dos intervalos integrados para auditoria.
        resumo["energia_horaria_disponivel_mWh"] = (
            energia if resumo["hora_completa"] else None
        )
        resumos.append(resumo)

    return {
        "no_id": no_esperado,
        "divisao": divisao,
        "emissao_utc": selecao["emissao_utc"],
        "corte_utc": selecao["corte_utc"],
        "total": total,
        "selecionadas": sum(len(item["leituras"]) for item in segmentos),
        "excluidas": excluidas,
        "motivos": dict(Counter(item["motivo"] for item in excluidas)),
        "segmentos": len(segmentos),
        "resumos": resumos,
    }


def main():
    """Apresenta os resultados em memória, sem criar um CSV."""
    parser = argparse.ArgumentParser(
        description="Prepara energia histórica disponível por emissão e divisão."
    )
    parser.add_argument("--origem", type=Path, required=True)
    parser.add_argument("--no", required=True)
    parser.add_argument("--divisao", required=True)
    parser.add_argument("--emissao", required=True, help="ISO 8601 com fuso")
    parser.add_argument("--metodo", choices=("corrente", "pwm"), required=True)
    parser.add_argument("--tensao", type=float)
    parser.add_argument("--potencia-referencia-mw", type=float)
    parser.add_argument("--margem-minutos", type=float, default=5)
    parser.add_argument("--limite-intervalo", type=float, default=30)
    parser.add_argument("--detalhes", action="store_true")
    opcoes = parser.parse_args()

    try:
        resposta = json.loads(opcoes.origem.read_text(encoding="utf-8-sig"))
        resultado = preparar(
            resposta, opcoes.no, opcoes.divisao,
            datetime.fromisoformat(opcoes.emissao),
            metodo=opcoes.metodo,
            tensao_v=opcoes.tensao,
            potencia_referencia_mw=opcoes.potencia_referencia_mw,
            margem_minutos=opcoes.margem_minutos,
            limite_intervalo=opcoes.limite_intervalo,
        )
    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    linhas = resultado["resumos"]
    completas = sum(linha["hora_completa"] for linha in linhas)
    sem_cobertura = sum(linha["segundos_integrados"] == 0 for linha in linhas)
    parciais = len(linhas) - completas - sem_cobertura

    print(f"Nó: {resultado['no_id']} | Divisão: {resultado['divisao']}")
    print(f"Emissão UTC: {resultado['emissao_utc']}")
    print(f"Corte UTC: {resultado['corte_utc']}")
    print(f"Método: {opcoes.metodo}")
    if opcoes.metodo == "pwm":
        print(f"Potência assumida a 100%: {opcoes.potencia_referencia_mw:g} mW")
    else:
        print(f"Tensão assumida: {opcoes.tensao:g} V")

    print(f"Leituras analisadas: {resultado['total']}")
    print(f"Leituras selecionadas: {resultado['selecionadas']}")
    print(f"Leituras excluídas: {len(resultado['excluidas'])}")
    for motivo, quantidade in sorted(resultado["motivos"].items()):
        print(f"  {motivo}: {quantidade}")
    print(f"Segmentos integrados separadamente: {resultado['segmentos']}")
    print(f"Resumos horários: {len(linhas)}")
    print(
        "Horas completas / parciais / sem cobertura: "
        f"{completas} / {parciais} / {sem_cobertura}"
    )

    if opcoes.detalhes:
        for linha in linhas:
            energia = linha["energia_horaria_disponivel_mWh"]
            texto = "indisponível" if energia is None else f"{energia:.6f} mWh"
            print(
                f"{linha['hora_utc']} | integrados={linha['segundos_integrados']} s | "
                f"excluídos={linha['segundos_excluidos']} s | "
                f"sem intervalo={linha['segundos_sem_intervalo']} s | "
                f"energia horária={texto}"
            )

    print("Contagens apenas das horas representadas nos resumos.")
    print("Horas ausentes não foram criadas nem preenchidas.")
    print("Energia horária disponível exige 3 600 segundos integrados.")
    print("A origem energética e as referências constam de cada resumo.")
    print("Apenas entradas históricas. Os alvos futuros permanecem separados.")
    print("Nenhum ficheiro criado ou alterado. Sem treino de modelos.")


if __name__ == "__main__":
    main()