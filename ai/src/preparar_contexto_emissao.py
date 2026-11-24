"""
Associa fontes disponíveis para uma emissão às 20h locais.

Mantém separados os resumos energéticos do passado e a meteorologia
prevista para o dia seguinte. Não cria alvos nem decide variáveis do modelo.
Não consulta APIs, não altera ficheiros e não treina modelos.
"""

import argparse
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ai.src.adquirir_previsao_meteorologica import (
    HORA_ANTERIOR,
    identificar_no,
)
from ai.src.preparar_energia_disponivel import preparar as preparar_energia
from ai.src.preparar_meteorologia import UNIDADES, preparar_meteorologia
from ai.src.selecionar_previsao_meteorologica import (
    selecionar as selecionar_meteo,
)


def associar(
    historico, documentos, no_esperado, divisao, data_emissao, *,
    metodo, tensao_v=None, potencia_referencia_mw=None,
    margem_sensores_minutos=5, margem_meteo_minutos=5,
    idade_maxima_horas=12, limite_intervalo=30,
):
    """
    Reúne fontes para uma emissão, sem as confundir com um dataset de treino.

    data_emissao: AAAA-MM-DD, no calendário local da instalação.
    As margens dos sensores e da meteorologia são independentes.
    Uma fonte indisponível permanece explicitamente indisponível.
    """
    no = identificar_no(historico, no_esperado)

    if not isinstance(data_emissao, str):
        raise ValueError("A data da emissão deve ser AAAA-MM-DD.")

    try:
        dia = date.fromisoformat(data_emissao)
    except ValueError:
        raise ValueError("Data da emissão inválida.") from None

    if dia.isoformat() != data_emissao:
        raise ValueError("A data da emissão deve ser AAAA-MM-DD.")

    zona = ZoneInfo(no["fuso"])
    emissao = datetime.combine(dia, time(20), tzinfo=zona)

    energia = preparar_energia(
        historico, no_esperado, divisao, emissao,
        metodo=metodo,
        tensao_v=tensao_v,
        potencia_referencia_mw=potencia_referencia_mw,
        margem_minutos=margem_sensores_minutos,
        limite_intervalo=limite_intervalo,
    )

    meteo = selecionar_meteo(
        documentos, historico, no_esperado, emissao,
        margem_minutos=margem_meteo_minutos,
        idade_maxima_horas=idade_maxima_horas,
    )

    horas_meteo = []
    documento = meteo["selecionada"]
    disponibilidade = None

    if documento is not None:
        disponibilidade = documento["aquisicao"]["disponivel_desde_utc"]
        linhas = preparar_meteorologia(documento["meteorologia"])

        # O seletor já verificou o dia completo e o instante final adicional.
        # Para [T, T+1), temperatura e outras variáveis instantâneas usam T.
        # Precipitação e radiação referentes à hora anterior usam T+1.
        for atual, seguinte in zip(linhas, linhas[1:]):
            inicio = datetime.fromisoformat(atual["instante_meteo_utc"])
            fim = datetime.fromisoformat(seguinte["instante_meteo_utc"])

            if fim - inicio != timedelta(hours=1):
                raise ValueError("Intervalo meteorológico inválido.")

            hora = {
                "no_id": no_esperado,
                "divisao": divisao,
                "hora_utc": inicio.isoformat(),
                "fim_hora_utc": fim.isoformat(),

                # Os offsets distinguem horas locais repetidas no outono.
                "hora_local": inicio.astimezone(zona).isoformat(),
                "fim_hora_local": fim.astimezone(zona).isoformat(),
                "meteo_tipo": "previsao_meteorologica",
            }

            for campo in UNIDADES:
                fonte = seguinte if campo in HORA_ANTERIOR else atual
                hora[f"meteo_{campo}"] = fonte[campo]

            horas_meteo.append(hora)

    # O diagnóstico contém índices das aquisições, limites e rejeições.
    # Não duplica a resposta meteorológica bruta no resultado.
    diagnostico_meteo = {
        campo: valor
        for campo, valor in meteo.items()
        if campo != "selecionada"
    }
    diagnostico_meteo["disponivel_desde_utc"] = disponibilidade

    return {
        "no_id": no_esperado,
        "divisao": divisao,
        "fuso": no["fuso"],
        "emissao_utc": meteo["emissao_utc"],
        "data_alvo_local": meteo["data_alvo_local"],
        "inicio_alvo_utc": meteo["inicio_alvo_utc"],
        "fim_alvo_exclusivo_utc": meteo["fim_alvo_exclusivo_utc"],
        "energia_historica": energia,
        "horas_historicas_completas": sum(
            linha["hora_completa"] for linha in energia["resumos"]
        ),
        "selecao_meteorologica": diagnostico_meteo,
        "meteorologia_dia_alvo": horas_meteo,
        "unidades_meteorologicas": {
            f"meteo_{campo}": unidade
            for campo, unidade in UNIDADES.items()
        },
    }


def main():
    """Lê fontes locais e apresenta o diagnóstico da associação."""
    parser = argparse.ArgumentParser(
        description="Associa fontes disponíveis para uma emissão às 20h locais."
    )
    parser.add_argument("--historico", type=Path, required=True)
    parser.add_argument("--no", required=True)
    parser.add_argument("--divisao", required=True)
    parser.add_argument(
        "--data-emissao", required=True, help="AAAA-MM-DD local"
    )
    parser.add_argument("--previsoes", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--metodo", choices=("corrente", "pwm"), required=True
    )
    parser.add_argument("--tensao", type=float)
    parser.add_argument("--potencia-referencia-mw", type=float)
    parser.add_argument("--margem-sensores-minutos", type=float, default=5)
    parser.add_argument("--margem-meteo-minutos", type=float, default=5)
    parser.add_argument("--idade-maxima-horas", type=float, default=12)
    parser.add_argument("--limite-intervalo", type=float, default=30)
    opcoes = parser.parse_args()

    try:
        historico = json.loads(
            opcoes.historico.read_text(encoding="utf-8-sig")
        )
        documentos = [
            json.loads(caminho.read_text(encoding="utf-8-sig"))
            for caminho in opcoes.previsoes
        ]

        resultado = associar(
            historico, documentos, opcoes.no, opcoes.divisao,
            opcoes.data_emissao,
            metodo=opcoes.metodo,
            tensao_v=opcoes.tensao,
            potencia_referencia_mw=opcoes.potencia_referencia_mw,
            margem_sensores_minutos=opcoes.margem_sensores_minutos,
            margem_meteo_minutos=opcoes.margem_meteo_minutos,
            idade_maxima_horas=opcoes.idade_maxima_horas,
            limite_intervalo=opcoes.limite_intervalo,
        )
    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    energia = resultado["energia_historica"]
    meteo = resultado["selecao_meteorologica"]

    print(f"Nó: {resultado['no_id']} | Divisão: {resultado['divisao']}")
    print(f"Emissão UTC: {resultado['emissao_utc']}")
    print(f"Dia alvo local: {resultado['data_alvo_local']}")
    print(f"Corte dos sensores UTC: {energia['corte_utc']}")
    print(f"Corte meteorológico UTC: {meteo['limite_superior_utc']}")
    print(
        f"Horas históricas completas: "
        f"{resultado['horas_historicas_completas']}"
    )

    completas = [
        linha for linha in energia["resumos"] if linha["hora_completa"]
    ]

    if completas:
        print(
            f"Primeira hora histórica completa: "
            f"{completas[0]['hora_utc']}"
        )
        print(
            f"Última hora histórica completa: "
            f"{completas[-1]['hora_utc']}"
        )
    else:
        print("Sem energia horária histórica completa disponível.")

    print(f"Estado da meteorologia: {meteo['estado']}")

    for item in meteo["rejeitadas"]:
        nome = opcoes.previsoes[item["indice"]].name
        print(f"Rejeitada: {nome} | {item['motivo']}")

    if meteo["indice_selecionado"] is not None:
        nome = opcoes.previsoes[meteo["indice_selecionado"]].name
        print(f"Previsão selecionada: {nome}")
        print(f"Disponível desde UTC: {meteo['disponivel_desde_utc']}")

    print(
        f"Intervalos meteorológicos do dia alvo: "
        f"{len(resultado['meteorologia_dia_alvo'])}"
    )
    print("Sem substituição por meteorologia histórica.")
    print("Não foi definida uma janela histórica mínima ou máxima.")
    print("Fontes associadas para inspeção; não é o dataset final de treino.")
    print("Alvos futuros não utilizados. Nenhum ficheiro criado ou alterado.")


if __name__ == "__main__":
    main()