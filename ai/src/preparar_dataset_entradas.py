"""
Constrói entradas horárias para o dia seguinte, sem associar alvos.

A janela contém dias de 24 horas UTC e termina na última fronteira horária
anterior ou igual ao corte dos sensores. Só horas completas geram variáveis
energéticas. Não consulta APIs nem treina modelos.
"""

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from ai.src.preparar_alvo_energia import (
    ORIGEM_CORRENTE,
    ORIGEM_PWM,
    selecionar_alvo,
)
from ai.src.preparar_contexto_emissao import associar
from ai.src.preparar_meteorologia import UNIDADES


AI_DIR = Path(__file__).resolve().parents[1]


def construir(contexto, referencia, janela_dias=7):
    """Recebe o contexto validado e produz entradas, cobertura e diagnóstico."""
    if type(janela_dias) is not int or janela_dias <= 0:
        raise ValueError(
            "A janela deve ser um número inteiro positivo de dias."
        )

    energia = contexto["energia_historica"]
    meteo = contexto["selecao_meteorologica"]
    emissao = datetime.fromisoformat(contexto["emissao_utc"])
    corte = datetime.fromisoformat(energia["corte_utc"])
    fim = corte.replace(minute=0, second=0, microsecond=0)

    try:
        inicio = fim - timedelta(days=janela_dias)
    except OverflowError:
        raise ValueError(
            "Janela histórica fora do intervalo temporal."
        ) from None

    # Integração e disponibilidade já foram avaliadas no contexto.
    # Selecionamos horas inteiras, sem cortar previamente os pontos de apoio.
    janela = [
        linha
        for linha in energia["resumos"]
        if inicio <= datetime.fromisoformat(linha["hora_utc"]) < fim
    ]

    # Reutiliza apenas a validação e seleção de horas completas:
    # aqui estas linhas são entradas históricas, não alvos futuros.
    selecao = (
        selecionar_alvo(janela, contexto["no_id"]) if janela else None
    )
    completas = selecao["aceites"] if selecao else []

    for linha in janela:
        if linha["divisao"] != contexto["divisao"] or any(
            linha.get(campo) != valor
            for campo, valor in referencia.items()
        ):
            raise ValueError(
                "Divisão ou referência energética incompatível."
            )

    zona = ZoneInfo(contexto["fuso"])
    por_hora_local = defaultdict(list)

    for linha in completas:
        hora = (
            datetime.fromisoformat(linha["hora_utc"])
            .astimezone(zona)
            .hour
        )
        por_hora_local[hora].append(linha["energia_mWh"])

    ultima = completas[-1] if completas else None
    fim_ultima = (
        datetime.fromisoformat(ultima["hora_utc"]) + timedelta(hours=1)
        if ultima else None
    )

    previstas = janela_dias * 24
    parciais = sum(
        0 < linha["segundos_integrados"] < 3600 for linha in janela
    )

    cobertura = {
        "janela_dias": janela_dias,
        "inicio_janela_utc": inicio.isoformat(),
        "fim_janela_exclusivo_utc": fim.isoformat(),
        "horas_previstas_janela": previstas,
        "horas_completas_janela": len(completas),
        "horas_parciais_janela": parciais,
        "horas_sem_cobertura_janela": (
            previstas - len(completas) - parciais
        ),
        "cobertura_energetica_proporcao": (
            sum(linha["segundos_integrados"] for linha in janela)
            / (previstas * 3600)
        ),
    }

    indice_meteo = {
        linha["hora_utc"]: linha
        for linha in contexto["meteorologia_dia_alvo"]
    }
    instante = datetime.fromisoformat(contexto["inicio_alvo_utc"])
    fim_alvo = datetime.fromisoformat(
        contexto["fim_alvo_exclusivo_utc"]
    )
    linhas = []

    # O calendário existe mesmo quando não há meteorologia elegível.
    while instante < fim_alvo:
        local = instante.astimezone(zona)
        amostra = por_hora_local[local.hour]
        meteorologia = indice_meteo.get(instante.isoformat())

        if meteo["estado"] == "disponivel" and meteorologia is None:
            raise ValueError("Falta uma hora da previsão selecionada.")

        linha = {
            "versao_dataset": "entradas_v1",
            "finalidade": "entrada_previsao",
            "no_id": contexto["no_id"],
            "divisao": contexto["divisao"],
            "emissao_utc": contexto["emissao_utc"],
            "fuso": contexto["fuso"],
            "data_alvo_local": contexto["data_alvo_local"],
            "inicio_hora_alvo_utc": instante.isoformat(),
            "fim_hora_alvo_utc": (
                instante + timedelta(hours=1)
            ).isoformat(),
            "inicio_hora_alvo_local": local.isoformat(),
            "hora_local": local.hour,
            "dia_semana": local.weekday(),  # Segunda=0; domingo=6.
            "mes": local.month,
            **cobertura,
            **referencia,
            "ultima_hora_historica_utc": (
                ultima["hora_utc"] if ultima else None
            ),
            "energia_ultima_hora_mWh": (
                ultima["energia_mWh"] if ultima else None
            ),

            # Antiguidade contada desde o fim da última hora completa.
            "idade_ultima_hora_h": (
                (emissao - fim_ultima).total_seconds() / 3600
                if fim_ultima else None
            ),
            "energia_media_mesma_hora_mWh": (
                mean(amostra) if amostra else None
            ),
            "n_horas_mesma_hora": len(amostra),
            "estado_historico": (
                "horas_completas_disponiveis"
                if completas else "sem_horas_completas"
            ),
            "corte_sensores_utc": energia["corte_utc"],
            "margem_sensores_minutos": (
                emissao - corte
            ).total_seconds() / 60,
            "corte_meteo_utc": meteo["limite_superior_utc"],
            "margem_meteo_minutos": meteo["margem_minutos"],
            "idade_maxima_meteo_h": meteo["idade_maxima_horas"],
            "estado_meteorologia": meteo["estado"],
            "meteo_disponivel_desde_utc": meteo["disponivel_desde_utc"],
            "indice_previsao": meteo["indice_selecionado"],
        }

        for campo in UNIDADES:
            linha[f"meteo_{campo}"] = (
                meteorologia[f"meteo_{campo}"]
                if meteo["estado"] == "disponivel" else None
            )

        linhas.append(linha)
        instante += timedelta(hours=1)

    return {
        "linhas": linhas,
        "cobertura": cobertura,
        "resumos_historicos_janela": [
            dict(linha) for linha in janela
        ],
        "exclusoes_sensores": deepcopy(energia["excluidas"]),
        "selecao_meteorologica": deepcopy(meteo),
        "unidades_meteorologicas": dict(
            contexto["unidades_meteorologicas"]
        ),
    }


def preparar(
    historico, documentos, no_esperado, divisao, data_emissao, *,
    metodo, janela_dias=7, **opcoes,
):
    """Executa os módulos existentes antes de construir as entradas."""
    contexto = associar(
        historico, documentos, no_esperado, divisao, data_emissao,
        metodo=metodo, **opcoes,
    )

    referencia = {
        "origem_energia": (
            ORIGEM_PWM if metodo == "pwm" else ORIGEM_CORRENTE
        ),
        "tensao_assumida_v": opcoes.get("tensao_v"),
        "potencia_referencia_mW": opcoes.get("potencia_referencia_mw"),
        "limite_intervalo_segundos": opcoes.get("limite_intervalo", 30),
    }

    return construir(contexto, referencia, janela_dias)


def guardar(linhas, destino):
    """Guarda um CSV novo em processed, apenas se estiver ignorado pelo Git."""
    destino = Path(destino).resolve()
    pasta = (AI_DIR / "data/processed").resolve()

    if (
        not destino.is_relative_to(pasta)
        or destino.suffix.lower() != ".csv"
    ):
        raise ValueError(
            "O destino deve ser um CSV dentro de ai/data/processed."
        )

    if destino.exists():
        raise ValueError("O destino já existe; não será substituído.")

    if not linhas:
        raise ValueError("Não existem entradas para guardar.")

    raiz = AI_DIR.resolve().parent
    relativo = destino.relative_to(raiz).as_posix()

    verificacao = subprocess.run(
        ["git", "check-ignore", "-q", "--", relativo],
        cwd=raiz,
        capture_output=True,
        check=False,
    )

    if verificacao.returncode != 0:
        raise ValueError(
            "O destino deve estar ignorado e não acompanhado pelo Git."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)

    with destino.open("x", encoding="utf-8", newline="") as ficheiro:
        try:
            escritor = csv.DictWriter(
                ficheiro, fieldnames=list(linhas[0])
            )
            escritor.writeheader()

            # None é guardado como célula vazia.
            escritor.writerows(linhas)
            ficheiro.flush()
        except BaseException:
            ficheiro.close()
            destino.unlink(missing_ok=True)
            raise

    return destino


def main():
    parser = argparse.ArgumentParser(
        description="Prepara entradas horárias sem alvos futuros nem treino."
    )
    parser.add_argument("--historico", type=Path, required=True)
    parser.add_argument("--no", required=True)
    parser.add_argument("--divisao", required=True)
    parser.add_argument("--data-emissao", required=True)
    parser.add_argument("--previsoes", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--metodo", choices=("corrente", "pwm"), required=True
    )
    parser.add_argument("--tensao", type=float)
    parser.add_argument("--potencia-referencia-mw", type=float)
    parser.add_argument("--janela-dias", type=int, default=7)
    parser.add_argument("--margem-sensores-minutos", type=float, default=5)
    parser.add_argument("--margem-meteo-minutos", type=float, default=5)
    parser.add_argument("--idade-maxima-horas", type=float, default=12)
    parser.add_argument("--limite-intervalo", type=float, default=30)
    parser.add_argument("--destino", type=Path)
    opcoes = parser.parse_args()

    try:
        historico = json.loads(
            opcoes.historico.read_text(encoding="utf-8-sig")
        )
        documentos = [
            json.loads(p.read_text(encoding="utf-8-sig"))
            for p in opcoes.previsoes
        ]

        resultado = preparar(
            historico, documentos, opcoes.no, opcoes.divisao,
            opcoes.data_emissao,
            metodo=opcoes.metodo,
            janela_dias=opcoes.janela_dias,
            tensao_v=opcoes.tensao,
            potencia_referencia_mw=opcoes.potencia_referencia_mw,
            margem_sensores_minutos=opcoes.margem_sensores_minutos,
            margem_meteo_minutos=opcoes.margem_meteo_minutos,
            idade_maxima_horas=opcoes.idade_maxima_horas,
            limite_intervalo=opcoes.limite_intervalo,
        )

        destino = (
            guardar(resultado["linhas"], opcoes.destino)
            if opcoes.destino else None
        )
    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    cobertura = resultado["cobertura"]
    meteo = resultado["selecao_meteorologica"]

    print(f"Nó: {opcoes.no} | Divisão: {opcoes.divisao}")
    print(f"Emissão UTC: {meteo['emissao_utc']}")
    print(f"Dia alvo local: {meteo['data_alvo_local']}")
    print(
        f"Janela UTC: [{cobertura['inicio_janela_utc']}, "
        f"{cobertura['fim_janela_exclusivo_utc']})"
    )
    print(
        f"Horas previstas na janela: "
        f"{cobertura['horas_previstas_janela']}"
    )
    print(
        "Completas / parciais / sem cobertura: "
        f"{cobertura['horas_completas_janela']} / "
        f"{cobertura['horas_parciais_janela']} / "
        f"{cobertura['horas_sem_cobertura_janela']}"
    )
    print(
        "Cobertura energética da janela: "
        f"{cobertura['cobertura_energetica_proporcao']:.4%}"
    )
    print(f"Estado da meteorologia: {meteo['estado']}")

    for item in meteo["rejeitadas"]:
        print(f"Aquisição {item['indice']}: {item['motivo']}")

    print(f"Entradas horárias: {len(resultado['linhas'])}")
    print(
        f"CSV guardado em: {destino}"
        if destino else "Nenhum ficheiro criado."
    )
    print("Ausências preservadas; alvos futuros não incluídos.")
    print("Dados insuficientes não são declarados aptos para treino.")
    print("Configurações históricas do hardware ainda exigem validação.")


if __name__ == "__main__":
    main()