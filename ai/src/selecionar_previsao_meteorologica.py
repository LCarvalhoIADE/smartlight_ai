"""
Seleciona uma aquisição meteorológica disponível antes da emissão.

Regras iniciais:
- Margem de 5 minutos antes da emissão.
- Idade máxima de 12 horas, contada até à emissão.
- Mesmo nó, localização, fuso e dia alvo.
- Apenas previsões, nunca meteorologia histórica.
- Escolhe a aquisição elegível mais recente.

Os limites são configuráveis e provisórios.
Este módulo não consulta APIs, não altera ficheiros e não prevê energia.
"""

import argparse
import json
import math
from copy import deepcopy
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ai.src.adquirir_previsao_meteorologica import (
    ENDPOINT,
    HORA_ANTERIOR,
    identificar_no,
    instante_utc,
    planear_periodo,
)
from ai.src.preparar_meteorologia import (
    UNIDADES,
    preparar_meteorologia,
)


def ler_instante(valor):
    """Lê um instante ISO 8601 com fuso explícito e converte para UTC."""
    if not isinstance(valor, str):
        raise ValueError("Timestamp ausente ou inválido.")

    try:
        return instante_utc(datetime.fromisoformat(valor))
    except (ValueError, TypeError, OverflowError):
        raise ValueError(
            "Timestamp inválido ou sem fuso explícito."
        ) from None

def validar_limites(margem_minutos, idade_maxima_horas):
    """Valida os parâmetros antes de analisar qualquer aquisição."""
    for nome, valor in (
        ("margem", margem_minutos),
        ("idade máxima", idade_maxima_horas),
    ):
        if type(valor) not in (int, float) or not math.isfinite(valor):
            raise ValueError(f"A {nome} deve ser um número finito.")

    if margem_minutos < 0:
        raise ValueError("A margem não pode ser negativa.")

    if idade_maxima_horas <= 0:
        raise ValueError("A idade máxima deve ser positiva.")

    if margem_minutos > idade_maxima_horas * 60:
        raise ValueError(
            "A margem não pode ultrapassar a idade máxima."
        )

    try:
        margem = timedelta(minutes=margem_minutos)
        idade = timedelta(hours=idade_maxima_horas)
    except OverflowError:
        raise ValueError("Limites temporais demasiado elevados.") from None

    return margem, idade


def validar_candidato(
    documento,
    no,
    dia_alvo,
    inicio,
    fim,
    limite_inferior,
    limite_superior,
):
    """
    Valida uma aquisição e devolve o instante de disponibilidade.

    Uma aquisição inválida nunca é corrigida ou completada neste módulo.
    """
    candidato_no = identificar_no(documento, no["no_id"])

    # Exige a configuração geográfica esperada.
    # Alterações de localização devem ser tratadas explicitamente.
    if candidato_no["fuso"] != no["fuso"]:
        raise ValueError("Fuso diferente do esperado.")

    for campo in ("latitude", "longitude"):
        if not math.isclose(
            candidato_no[campo],
            no[campo],
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError("Localização diferente da esperada.")

    aquisicao = documento.get("aquisicao")

    if not isinstance(aquisicao, dict):
        raise ValueError("Metadados de aquisição ausentes.")

    if aquisicao.get("tipo") != "previsao_meteorologica":
        raise ValueError("A fonte não é uma previsão meteorológica.")

    if aquisicao.get("endpoint") != ENDPOINT:
        raise ValueError("Endpoint de previsão incompatível.")

    if aquisicao.get("data_alvo_local") != dia_alvo.isoformat():
        raise ValueError("Dia alvo diferente do esperado.")

    if (
        ler_instante(aquisicao.get("inicio_alvo_utc")) != inicio
        or ler_instante(aquisicao.get("fim_alvo_exclusivo_utc")) != fim
    ):
        raise ValueError("Fronteiras do dia alvo incompatíveis.")

    iniciado = ler_instante(aquisicao.get("inicio_consulta_utc"))
    concluido = ler_instante(aquisicao.get("fim_consulta_utc"))
    disponivel = ler_instante(aquisicao.get("disponivel_desde_utc"))

    # O contrato atual regista a disponibilidade no fim da consulta.
    if iniciado > concluido or disponivel != concluido:
        raise ValueError("Tempos de aquisição inconsistentes.")

    # Os dois limites são inclusivos.
    if disponivel < limite_inferior:
        raise ValueError("Aquisição demasiado antiga.")

    if disponivel > limite_superior:
        raise ValueError("Aquisição recebida depois do limite.")

    parametros = aquisicao.get("parametros")

    if not isinstance(parametros, dict):
        raise ValueError("Parâmetros do pedido ausentes.")

    # Confirma as coordenadas efetivamente utilizadas no pedido.
     # As coordenadas da grelha devolvida pela API podem ser diferentes.
    for campo in ("latitude", "longitude"):
        valor = parametros.get(campo)

        if (
            type(valor) not in (int, float)
            or not math.isfinite(valor)
            or not math.isclose(
                valor,
                no[campo],
                rel_tol=0,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("Coordenadas do pedido incompatíveis.")

    if parametros.get("timezone") != "GMT":
        raise ValueError("O pedido meteorológico não está em GMT.")

    if (
        parametros.get("start_hour")
        != inicio.strftime("%Y-%m-%dT%H:%M")
        or parametros.get("end_hour")
        != fim.strftime("%Y-%m-%dT%H:%M")
    ):
        raise ValueError("Período do pedido incompatível.")

    variaveis = parametros.get("hourly")

    if (
        not isinstance(variaveis, str)
        or set(variaveis.split(",")) != set(UNIDADES)
    ):
        raise ValueError("Variáveis do pedido incompatíveis.")

    # Reutiliza a validação existente de unidades, valores,
    # timestamps e continuidade horária.
    linhas = preparar_meteorologia(documento.get("meteorologia"))

    quantidade = int((fim - inicio).total_seconds() / 3600)

    if (
        len(linhas) != quantidade + 1
        or linhas[0]["instante_meteo_utc"] != inicio.isoformat()
        or linhas[-1]["instante_meteo_utc"] != fim.isoformat()
    ):
        raise ValueError("Cobertura meteorológica incompleta.")

    # Confirma também as contagens declaradas no envelope.
    for campo, esperado in (
        ("intervalos_horarios", quantidade),
        ("instantes_recebidos", quantidade + 1),
    ):
        valor = aquisicao.get(campo)

        if type(valor) is not int or valor != esperado:
            raise ValueError("Contagens meteorológicas inconsistentes.")

    for linha in linhas:
        instante = ler_instante(linha["instante_meteo_utc"])

        for campo in UNIDADES:
            necessario = (
                inicio < instante <= fim
                if campo in HORA_ANTERIOR
                else inicio <= instante < fim
            )

            if necessario and linha[campo] is None:
                raise ValueError(
                    f"Valor meteorológico necessário ausente: {campo}."
                )

    return disponivel


