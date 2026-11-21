"""
Associa alvos energéticos após as horas previstas, sem alterar as entradas.

O limite de receção dos alvos é o momento da avaliação posterior.
Nunca se utiliza o corte da emissão anterior para calcular esses alvos.
Não consulta APIs nem treina modelos.
"""

import argparse
import json
from collections import Counter
from copy import deepcopy
from datetime import time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai.src.adquirir_previsao_meteorologica import (
    agora_utc, instante_utc, planear_periodo,
)
from ai.src.cruzar_alvo_meteorologia import ler_alvo as ler_csv
from ai.src.cruzar_meteorologia import ler_hora_utc
from ai.src.preparar_alvo_energia import ORIGEM_PWM, numero, validar_referencia
from ai.src.preparar_dataset_entradas import guardar
from ai.src.preparar_energia_disponivel import preparar as integrar_ate
from ai.src.selecionar_previsao_meteorologica import ler_instante


def validar_entradas(entradas, no_esperado, divisao):
    """Valida as chaves da associação e a referência de um único lote diário."""
    if not isinstance(entradas, list) or not entradas:
        raise ValueError("Esperada uma lista não vazia de entradas.")

    campos = {
        "versao_dataset", "finalidade", "no_id", "divisao", "fuso",
        "emissao_utc", "data_alvo_local", "inicio_hora_alvo_utc",
        "fim_hora_alvo_utc", "origem_energia", "limite_intervalo_segundos",
    }
    chaves = set()
    lote = None
    configuracao = None
    periodos = []

    for linha in entradas:
        if not isinstance(linha, dict) or not campos.issubset(linha):
            raise ValueError("Entrada com campos obrigatórios em falta.")

        if any(campo.startswith("alvo_") for campo in linha):
            raise ValueError("A entrada já contém campos de alvo.")

        if (
            linha["versao_dataset"] != "entradas_v1"
            or linha["finalidade"] != "entrada_previsao"
        ):
            raise ValueError("Versão ou finalidade das entradas incompatível.")

        if linha["no_id"] != no_esperado or linha["divisao"] != divisao:
            raise ValueError("Nó ou divisão diferente do pedido.")

        emissao = ler_instante(linha["emissao_utc"])

        try:
            zona = ZoneInfo(linha["fuso"])
        except (ZoneInfoNotFoundError, TypeError, ValueError):
            raise ValueError("Fuso das entradas inválido.") from None

        if emissao.astimezone(zona).time() != time(20):
            raise ValueError("Esperada uma emissão às 20h locais.")

        dia, inicio_dia, fim_dia = planear_periodo(linha["fuso"], emissao)

        if linha["data_alvo_local"] != dia.isoformat():
            raise ValueError("Dia alvo incompatível com a emissão.")

        identificacao = (emissao, linha["fuso"], inicio_dia, fim_dia)

        if lote is not None and identificacao != lote:
            raise ValueError("As entradas devem pertencer à mesma emissão.")

        lote = identificacao

        inicio = ler_hora_utc(linha["inicio_hora_alvo_utc"])
        fim = ler_hora_utc(linha["fim_hora_alvo_utc"])

        if fim - inicio != timedelta(hours=1) or not (
            inicio_dia <= inicio < fim <= fim_dia
        ):
            raise ValueError("Intervalo alvo inválido.")

        if inicio in chaves:
            raise ValueError("Entrada horária duplicada.")

        chaves.add(inicio)
        periodos.append((inicio, fim))

        tensao, potencia = validar_referencia(linha)
        limite = numero(linha["limite_intervalo_segundos"], "Limite")

        if limite <= 0:
            raise ValueError("Limite temporal inválido.")

        atual = (linha["origem_energia"], tensao, potencia, limite)

        if configuracao is not None and atual != configuracao:
            raise ValueError("Referências energéticas diferentes no lote.")

        configuracao = atual

    esperado = int((lote[3] - lote[2]).total_seconds() / 3600)

    if len(entradas) != esperado:
        raise ValueError("Faltam horas do dia alvo no dataset de entradas.")

    return lote, configuracao, periodos


def associar(
    entradas, historico_alvo, no_esperado, divisao, avaliacao, *,
    relogio=None,
):
    """Cria alvos e uma cópia associada, preservando todas as entradas."""
    avaliacao = instante_utc(avaliacao)
    agora = instante_utc((relogio or agora_utc)())

    if avaliacao > agora:
        raise ValueError("A avaliação não pode estar no futuro.")

    lote, configuracao, periodos = validar_entradas(
        entradas, no_esperado, divisao
    )

    if avaliacao < lote[0]:
        raise ValueError("A avaliação é anterior à emissão.")

    origem, tensao, potencia, limite = configuracao

    # Reutiliza a integração por segmentos com um novo instante de corte.
    # Margem zero: este corte é da avaliação posterior, não da previsão.
    resumo = integrar_ate(
        historico_alvo, no_esperado, divisao, avaliacao,
        metodo="pwm" if origem == ORIGEM_PWM else "corrente",
        tensao_v=tensao,
        potencia_referencia_mw=potencia,
        margem_minutos=0,
        limite_intervalo=limite,
    )

    if (
        historico_alvo["ate"] < lote[2].timestamp()
        or historico_alvo["de"] >= lote[3].timestamp()
    ):
        raise ValueError("O histórico consultado não abrange o dia alvo.")

    indice = {
        ler_hora_utc(linha["hora_utc"]): linha
        for linha in resumo["resumos"]
    }

    alvos = []
    associadas = []

    for entrada, (inicio, fim) in zip(entradas, periodos):
        hora = indice.get(inicio)
        integrados = hora["segundos_integrados"] if hora else 0
        excluidos = hora["segundos_excluidos"] if hora else 0

        if fim > avaliacao:
            estado = "hora_nao_terminada"
        elif integrados == 0:
            estado = "sem_cobertura"
        elif integrados < 3600:
            estado = "cobertura_parcial"
        else:
            estado = "disponivel"

        energia = (
            hora["energia_horaria_disponivel_mWh"]
            if estado == "disponivel" else None
        )

        if estado == "disponivel" and energia is None:
            raise ValueError("Hora completa sem energia válida.")

        alvo = {
            "no_id": no_esperado,
            "divisao": divisao,
            "inicio_hora_alvo_utc": inicio.isoformat(),
            "fim_hora_alvo_utc": fim.isoformat(),
            "alvo_versao": "alvos_v1",
            "alvo_estado": estado,
            "alvo_avaliado_em_utc": avaliacao.isoformat(),
            "alvo_energia_mWh": energia,
            "alvo_energia_Wh": None if energia is None else energia / 1000,
            "alvo_segundos_integrados": integrados,
            "alvo_segundos_excluidos": excluidos,
            "alvo_segundos_sem_intervalo": 3600 - integrados - excluidos,
            "alvo_cobertura_proporcao": integrados / 3600,
            "alvo_origem_energia": origem,
            "alvo_tensao_assumida_v": tensao,
            "alvo_potencia_referencia_mW": potencia,
            "alvo_limite_intervalo_segundos": limite,
        }

        alvos.append(alvo)

        # Mantém todos os campos das entradas com os valores originais.
        associadas.append({
            **deepcopy(entrada),
            **{
                campo: valor for campo, valor in alvo.items()
                if campo.startswith("alvo_")
            },
        })

    return {
        "alvos": alvos,
        "associadas": associadas,
        "estados": dict(Counter(alvo["alvo_estado"] for alvo in alvos)),
        "motivos_exclusao_leituras": resumo["motivos"],
        "exclusoes_leituras": resumo["excluidas"],
    }


def guardar_resultado(resultado, destino_alvos=None, destino_associado=None):
    """Usa a exportação protegida existente e remove apenas saídas novas se falhar."""
    if destino_alvos and destino_associado:
        if Path(destino_alvos).resolve() == Path(destino_associado).resolve():
            raise ValueError("Os destinos dos alvos e da associação devem diferir.")

    criados = []

    try:
        for campo, destino in (
            ("alvos", destino_alvos),
            ("associadas", destino_associado),
        ):
            if destino is not None:
                criados.append(guardar(resultado[campo], destino))
    except BaseException:
        for caminho in criados:
            caminho.unlink(missing_ok=True)
        raise

    return criados


def main():
    parser = argparse.ArgumentParser(
        description="Associa alvos posteriores sem modificar o CSV de entradas."
    )
    parser.add_argument("--entradas", type=Path, required=True)
    parser.add_argument("--historico-alvo", type=Path, required=True)
    parser.add_argument("--no", required=True)
    parser.add_argument("--divisao", required=True)
    parser.add_argument("--avaliacao", help="ISO 8601 com fuso; omissão: agora UTC")
    parser.add_argument("--destino-alvos", type=Path)
    parser.add_argument("--destino-associado", type=Path)
    opcoes = parser.parse_args()

    try:
        entradas = ler_csv(opcoes.entradas)
        historico = json.loads(
            opcoes.historico_alvo.read_text(encoding="utf-8-sig")
        )
        avaliacao = (
            ler_instante(opcoes.avaliacao) if opcoes.avaliacao else agora_utc()
        )

        resultado = associar(
            entradas, historico, opcoes.no, opcoes.divisao, avaliacao
        )

        caminhos = guardar_resultado(
            resultado, opcoes.destino_alvos, opcoes.destino_associado
        )
    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    print(f"Nó: {opcoes.no} | Divisão: {opcoes.divisao}")
    print(f"Avaliação UTC: {instante_utc(avaliacao).isoformat()}")
    print(f"Entradas preservadas: {len(resultado['associadas'])}")

    for estado, quantidade in sorted(resultado["estados"].items()):
        print(f"Alvos {estado}: {quantidade}")

    for motivo, quantidade in sorted(resultado["motivos_exclusao_leituras"].items()):
        print(f"Leituras excluídas: {motivo}: {quantidade}")

    for caminho in caminhos:
        print(f"CSV guardado em: {caminho}")

    if not caminhos:
        print("Nenhum ficheiro criado.")

    print("O corte da emissão não foi aplicado aos alvos.")
    print("Alvos ausentes não foram substituídos por zero.")
    print("Entradas originais preservadas. Sem treino de modelos.")


if __name__ == "__main__":
    main()