"""Valida e prepara a meteorologia horária guardada em JSON.

Não altera o original nem faz pedidos à Internet.
Não cruza ainda a meteorologia com as leituras do ESP32.
"""

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Localiza ai/ independentemente da pasta do terminal.
AI_DIR = Path(__file__).resolve().parents[1]

# Variáveis selecionadas no pedido e respetivas unidades.
# A ordem define também as colunas do CSV.
UNIDADES = {
    "cloud_cover": "%",
    "temperature_2m": "°C",
    "precipitation": "mm",
    "relative_humidity_2m": "%",
    "cloud_cover_low": "%",
    "cloud_cover_mid": "%",
    "cloud_cover_high": "%",
    "is_day": "",
    "diffuse_radiation": "W/m²",
    "shortwave_radiation": "W/m²",
}

# Estes campos representam percentagens.
PERCENTAGENS = (
    "cloud_cover",
    "relative_humidity_2m",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
)

# Estes campos não devem apresentar valores negativos.
NAO_NEGATIVOS = (
    "precipitation",
    "diffuse_radiation",
    "shortwave_radiation",
)


def preparar_meteorologia(dados):
    """Devolve linhas horárias validadas, sem modificar a entrada.

    Exige datas ordenadas, sem duplicados e separadas por uma hora.
    Valores meteorológicos nulos são preservados como None.
    A validação abrange apenas a componente horária.
    """

    # A resposta da API deve ser um objeto JSON, convertido em dict.
    if not isinstance(dados, dict):
        raise ValueError("Esperado um objeto JSON de meteorologia.")

    # Uma resposta de erro também pode ser JSON válido.
    if dados.get("error"):
        raise ValueError(
            f"Erro devolvido pela API: {dados.get('reason', 'sem motivo')}"
        )

    # Só interpretamos datas sem fuso explícito quando os metadados
    # confirmam que o pedido foi feito em GMT/UTC.
    desvio = dados.get("utc_offset_seconds")
    if type(desvio) is not int or desvio != 0:
        raise ValueError("Esperado um desvio UTC de zero segundos.")

    if dados.get("timezone") not in ("GMT", "UTC", "Etc/UTC", "Etc/GMT"):
        raise ValueError("Esperado um fuso horário GMT/UTC.")

    horarios = dados.get("hourly")
    unidades = dados.get("hourly_units")

    if not isinstance(horarios, dict) or not isinstance(unidades, dict):
        raise ValueError("Faltam os objetos hourly ou hourly_units.")

    if unidades.get("time") != "iso8601":
        raise ValueError("Esperadas datas no formato ISO 8601.")

    tempos = horarios.get("time")
    if not isinstance(tempos, list) or not tempos:
        raise ValueError("Esperada uma lista não vazia de datas horárias.")

    # Cada variável deve ter um valor por instante e a unidade esperada.
    # Não dependemos da ordem em que as variáveis aparecem no JSON.
    for campo, unidade in UNIDADES.items():
        valores = horarios.get(campo)

        if not isinstance(valores, list):
            raise ValueError(f"{campo}: lista ausente ou inválida.")

        if len(valores) != len(tempos):
            raise ValueError(f"{campo}: quantidade diferente das datas.")

        if unidades.get(campo) != unidade:
            raise ValueError(f"{campo}: unidade ausente ou inesperada.")

    resultado = []
    anterior = None

    for indice, texto in enumerate(tempos):
        numero = indice + 1

        # Não aceitamos uma data sem a componente horária.
        if not isinstance(texto, str) or "T" not in texto:
            raise ValueError(f"Instante {numero}: formato inválido.")

        try:
            instante = datetime.fromisoformat(texto)
        except ValueError as erro:
            raise ValueError(
                f"Instante {numero}: data inválida."
            ) from erro

        # O JSON pedido em GMT pode omitir o sufixo de fuso nas datas.
        # Os metadados já verificados permitem identificá-las como UTC.
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        else:
            # Rejeitamos contradições entre a data e os metadados UTC.
            if instante.utcoffset() != timedelta(0):
                raise ValueError(f"Instante {numero}: fuso incompatível.")
            instante = instante.astimezone(timezone.utc)

        # Cada instante deve corresponder ao início de uma hora.
        if instante.minute or instante.second or instante.microsecond:
            raise ValueError(f"Instante {numero}: não corresponde à hora certa.")

        # Esta regra deteta duplicados, ordem incorreta e horas em falta.
        # Não ordenamos nem preenchemos falhas silenciosamente.
        if anterior is not None:
            if instante - anterior != timedelta(hours=1):
                raise ValueError(
                    f"Instante {numero}: intervalo diferente de uma hora."
                )

        anterior = instante

        # O nome explicita que este é o timestamp da fonte meteorológica.
        # Ainda não é uma chave temporal alinhada com o resumo do ESP32.
        linha = {"instante_meteo_utc": instante.isoformat()}

        for campo in UNIDADES:
            valor = horarios[campo][indice]

            # Preservar ausência de informação sem a transformar em zero.
            if valor is None:
                linha[campo] = None
                continue

            # type exclui booleanos, que em Python se comportam como 0/1.
            if type(valor) not in (int, float) or not math.isfinite(valor):
                raise ValueError(
                    f"Instante {numero}: {campo} deve ser numérico e finito."
                )

            if campo in PERCENTAGENS and not 0 <= valor <= 100:
                raise ValueError(
                    f"Instante {numero}: {campo} fora de 0 a 100."
                )

            if campo in NAO_NEGATIVOS and valor < 0:
                raise ValueError(
                    f"Instante {numero}: {campo} negativo."
                )

            if campo == "is_day" and valor not in (0, 1):
                raise ValueError(
                    f"Instante {numero}: is_day deve ser 0 ou 1."
                )

            # Temperaturas negativas são permitidas.
            # Não inventamos limites físicos adicionais nesta etapa.
            linha[campo] = valor

        resultado.append(linha)

    return resultado


def main():
    """Lê o JSON local, valida as horas e exporta um CSV."""

    origem = (
        AI_DIR / "data" / "raw"
        / "no3_meteo_2026-10-24_2026-10-30.json"
    )
    destino = (
        AI_DIR / "data" / "processed"
        / "no3_meteo_2026-10-24_2026-10-30_horario.csv"
    )

    # Aceita ficheiros UTF-8 com ou sem a marca inicial BOM.
    dados = json.loads(origem.read_text(encoding="utf-8-sig"))
    linhas = preparar_meteorologia(dados)

    # Verificação específica deste ficheiro.
    # A função acima continua reutilizável para outros períodos.
    if (
        len(linhas) != 168
        or linhas[0]["instante_meteo_utc"] != "2026-10-24T00:00:00+00:00"
        or linhas[-1]["instante_meteo_utc"] != "2026-10-30T23:00:00+00:00"
    ):
        raise ValueError("O período não corresponde a 24–30/10/2026.")

    # Só abrimos a saída depois de todas as validações anteriores.
    destino.parent.mkdir(parents=True, exist_ok=True)

    # O CSV é substituído em cada execução; o JSON não é modificado.
    with destino.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(
            ficheiro,
            fieldnames=["instante_meteo_utc", *UNIDADES],
        )
        escritor.writeheader()
        escritor.writerows(linhas)

    # Apresentar um resumo curto, incluindo possíveis valores ausentes.
    nulos = {
        campo: sum(linha[campo] is None for linha in linhas)
        for campo in UNIDADES
    }

    print(f"Horas preparadas: {len(linhas)}")
    print(f"Início UTC: {linhas[0]['instante_meteo_utc']}")
    print(f"Fim UTC: {linhas[-1]['instante_meteo_utc']}")
    print(f"Valores nulos: {nulos}")
    print(f"CSV guardado em: {destino}")
    print("Dados diários mantidos no JSON original, ainda não validados.")
    print("Sem cruzamento com o ESP32 nem alteração dos timestamps da fonte.")


# Importar a função nos testes não executa a leitura nem a exportação.
if __name__ == "__main__":
    main()