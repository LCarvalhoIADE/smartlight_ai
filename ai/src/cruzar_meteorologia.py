"""Cruza resumos horários do no3 com meteorologia histórica.

Este cruzamento destina-se à análise do passado.
Não representa meteorologia que estava disponível antecipadamente
para uma previsão real.
"""

import csv
import json
from datetime import datetime, timedelta, timezone

from ai.src.agregar_por_hora import CAMPOS_HORARIOS, agregar
from ai.src.importar_leituras import importar_tsv
from ai.src.preparar_dados import AI_DIR
from ai.src.preparar_meteorologia import preparar_meteorologia


# Valores associados ao instante indicado pela fonte.
# Para o resumo [10:00, 11:00), utilizamos o instante das 10:00.
VARIAVEIS_INSTANTANEAS = (
    "cloud_cover",
    "temperature_2m",
    "relative_humidity_2m",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "is_day",
)

# Estas variáveis descrevem a hora anterior ao timestamp da fonte.
# Para o resumo [10:00, 11:00), utilizamos o timestamp das 11:00.
# Precipitação: quantidade acumulada; radiação: valor médio.
VARIAVEIS_HORA_ANTERIOR = (
    "precipitation",
    "diffuse_radiation",
    "shortwave_radiation",
)

# Guardamos os dois instantes usados para permitir verificar
# o alinhamento temporal de cada linha.
CAMPOS_CRUZADOS = (
    *CAMPOS_HORARIOS,
    "meteo_instante_utc",
    "meteo_fim_intervalo_utc",
    *(f"meteo_{campo}" for campo in VARIAVEIS_INSTANTANEAS),
    *(f"meteo_{campo}" for campo in VARIAVEIS_HORA_ANTERIOR),
)


def ler_hora_utc(texto):
    """Converte uma hora ISO 8601 com fuso UTC explícito."""

    if not isinstance(texto, str):
        raise ValueError("A hora deve ser texto ISO 8601.")

    try:
        instante = datetime.fromisoformat(texto)
    except ValueError as erro:
        raise ValueError(f"Hora inválida: {texto}.") from erro

    # As funções anteriores já produzem datas com +00:00.
    # Aqui não inferimos o fuso de uma data que não o tenha.
    if instante.tzinfo is None or instante.utcoffset() != timedelta(0):
        raise ValueError("A hora deve ter fuso UTC explícito.")

    if instante.minute or instante.second or instante.microsecond:
        raise ValueError("Esperado o início exato de uma hora.")

    return instante.astimezone(timezone.utc)


def cruzar(resumos, meteorologia):
    """Cruza listas já produzidas por agregar e preparar_meteorologia.

    Mantém todas as linhas dos resumos ou interrompe com erro.
    Não altera as entradas nem preenche valores meteorológicos nulos.

    Nesta etapa, a meteorologia fornecida deve corresponder à
    localização do no3. A localização não é inferida pelo código.
    """
    if not isinstance(resumos, list) or not resumos:
        raise ValueError("Esperada uma lista não vazia de resumos.")

    if not isinstance(meteorologia, list) or not meteorologia:
        raise ValueError("Esperada uma lista não vazia de meteorologia.")

    # Criar um índice permite encontrar rapidamente cada hora.
    # Não aceitamos duplicados, pois tornariam a associação ambígua.
    indice_meteo = {}

    for linha in meteorologia:
        instante = ler_hora_utc(linha["instante_meteo_utc"])

        if instante in indice_meteo:
            raise ValueError("Timestamp meteorológico duplicado.")

        indice_meteo[instante] = linha

    resultado = []
    identificadores = set()

    for resumo in resumos:
        # Evita aplicar por engano a meteorologia do no3 a outro nó.
        if resumo["no_id"] != "no3":
            raise ValueError("Este cruzamento está configurado para no3.")

        inicio = ler_hora_utc(resumo["hora_utc"])
        fim = inicio + timedelta(hours=1)

        chave = (resumo["no_id"], resumo["divisao"], inicio)
        if chave in identificadores:
            raise ValueError("Resumo horário duplicado.")
        identificadores.add(chave)

        # Exigimos os dois timestamps necessários ao cruzamento.
        # Uma hora em falta não deve apagar o resumo correspondente.
        if inicio not in indice_meteo or fim not in indice_meteo:
            raise ValueError(
                "Falta meteorologia para o intervalo "
                f"{inicio.isoformat()} a {fim.isoformat()}."
            )

        meteo_inicio = indice_meteo[inicio]
        meteo_fim = indice_meteo[fim]

        # Criar uma cópia preserva o resumo original.
        linha = dict(resumo)
        linha["meteo_instante_utc"] = inicio.isoformat()
        linha["meteo_fim_intervalo_utc"] = fim.isoformat()

        # O prefixo meteo_ distingue as variáveis externas
        # das medições e métricas provenientes do ESP32.
        for campo in VARIAVEIS_INSTANTANEAS:
            linha[f"meteo_{campo}"] = meteo_inicio[campo]

        for campo in VARIAVEIS_HORA_ANTERIOR:
            linha[f"meteo_{campo}"] = meteo_fim[campo]

        resultado.append(linha)

    return sorted(
        resultado,
        key=lambda linha: (
            linha["hora_utc"],
            linha["no_id"],
            linha["divisao"],
        ),
    )


def main():
    """Prepara as duas fontes e guarda apenas o novo CSV cruzado."""

    origem_leituras = AI_DIR / "data" / "raw" / "leituras.tsv"
    origem_meteo = (
        AI_DIR / "data" / "raw"
        / "no3_meteo_2026-10-24_2026-10-30.json"
    )
    destino = (
        AI_DIR / "data" / "processed"
        / "no3_historico_com_meteorologia.csv"
    )

    # Reutilizamos as funções em memória.
    # Não executamos os seus main(), nem substituímos os CSV anteriores.
    leituras = importar_tsv(origem_leituras, no_esperado="no3")
    resumos = agregar(leituras)

    dados_meteo = json.loads(
        origem_meteo.read_text(encoding="utf-8-sig")
    )
    meteorologia = preparar_meteorologia(dados_meteo)

    # Todas as associações são verificadas antes de abrir a saída.
    linhas = cruzar(resumos, meteorologia)

    destino.parent.mkdir(parents=True, exist_ok=True)

    # Apenas este CSV é substituído em execuções posteriores.
    # None é escrito como célula vazia, nunca como zero.
    with destino.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(
            ficheiro,
            fieldnames=CAMPOS_CRUZADOS,
        )
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"Resumos do ESP32: {len(resumos)}")
    print(f"Horas meteorológicas disponíveis: {len(meteorologia)}")
    print(f"Linhas cruzadas: {len(linhas)}")
    print(f"Primeira hora UTC: {linhas[0]['hora_utc']}")
    print(f"Última hora UTC: {linhas[-1]['hora_utc']}")
    print(f"CSV guardado em: {destino}")
    print("Horas parciais e valores nulos preservados.")
    print("Meteorologia histórica: não representa previsões antecipadas.")
    print("Sem cálculo de consumo nem treino de modelos.")


if __name__ == "__main__":
    main()