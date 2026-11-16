"""
Adquire uma previsão meteorológica para o próximo dia civil do nó.

Utiliza a localização e o fuso guardados no histórico do próprio nó.

Uma execução faz um pedido à Open-Meteo.
Não agenda tarefas, não treina modelos e não emite previsões energéticas.

Preserva a resposta meteorológica e o momento em que foi obtida.
"""

import argparse
import json
import math
import re
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Reutiliza as variáveis, unidades e validações meteorológicas existentes.
from ai.src.preparar_meteorologia import UNIDADES, preparar_meteorologia


# Localiza a componente de IA independentemente da pasta de execução.
AI_DIR = Path(__file__).resolve().parents[1]

# Este endpoint fornece previsões, não o arquivo meteorológico histórico.
ENDPOINT = "https://api.open-meteo.com/v1/forecast"

# Estas variáveis representam a hora anterior ao timestamp apresentado.
# As restantes variáveis utilizadas representam o instante indicado.
HORA_ANTERIOR = {
    "precipitation",
    "shortwave_radiation",
    "diffuse_radiation",
}


def agora_utc():
    """Obtém a hora real; nos testes utiliza-se um relógio fictício."""
    return datetime.now(timezone.utc)


def instante_utc(valor):
    """Exige um datetime com fuso explícito e normaliza-o para UTC."""
    if not isinstance(valor, datetime) or valor.utcoffset() is None:
        raise ValueError("O relógio deve fornecer um instante com fuso.")

    return valor.astimezone(timezone.utc)


def identificar_no(historico, no_esperado):
    """Seleciona os metadados necessários, sem copiar credenciais."""

    # O identificador também será utilizado no nome do ficheiro.
    if not isinstance(no_esperado, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,32}",
        no_esperado,
    ):
        raise ValueError("Identificador de nó inválido.")

    no = historico.get("no") if isinstance(historico, dict) else None

    if not isinstance(no, dict) or no.get("no_id") != no_esperado:
        raise ValueError("O histórico não corresponde ao nó pedido.")

    resultado = {"no_id": no_esperado}

    # Não aceita coordenadas ausentes, booleanas ou fora dos limites.
    for campo, limite in (("latitude", 90), ("longitude", 180)):
        valor = no.get(campo)

        if (
            type(valor) not in (int, float)
            or not math.isfinite(valor)
            or not -limite <= valor <= limite
        ):
            raise ValueError(f"Coordenada inválida: {campo}.")

        resultado[campo] = float(valor)

    # O fuso permite determinar o dia civil da instalação.
    fuso = no.get("fuso")

    if not isinstance(fuso, str) or not fuso.strip():
        raise ValueError("Falta o fuso do nó.")

    try:
        ZoneInfo(fuso)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(
            "Fuso não reconhecido. Confirma o nome e a disponibilidade "
            "da base de fusos horários tzdata."
        ) from None

    resultado["fuso"] = fuso
    return resultado


def planear_periodo(fuso, momento):
    """Calcula as duas meias-noites locais e converte-as para UTC."""
    zona = ZoneInfo(fuso)
    hoje_local = instante_utc(momento).astimezone(zona).date()
    dia_alvo = hoje_local + timedelta(days=1)

    # Não somamos simplesmente 24 horas em UTC.
    # Um dia local pode ter 23 ou 25 horas nas mudanças de hora.
    inicio_local = datetime.combine(
        dia_alvo,
        time.min,
        tzinfo=zona,
    )

    fim_local = datetime.combine(
        dia_alvo + timedelta(days=1),
        time.min,
        tzinfo=zona,
    )

    inicio = inicio_local.astimezone(timezone.utc)
    fim = fim_local.astimezone(timezone.utc)

    # O projeto utiliza intervalos alinhados com horas UTC completas.
    # Fusos com deslocamentos fracionários exigiriam outra agregação.
    if any(instante.minute or instante.second for instante in (inicio, fim)):
        raise ValueError(
            "O fuso não corresponde a fronteiras horárias UTC."
        )

    return dia_alvo, inicio, fim


def pedir_previsao(parametros):
    """Consulta a Open-Meteo sem utilizar a chave da API SmartLight."""
    pedido = Request(
        ENDPOINT + "?" + urlencode(parametros),
        headers={"Accept": "application/json"},
    )

    try:
        with urlopen(pedido, timeout=60) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    except HTTPError as erro:
        raise ValueError(
            f"Open-Meteo devolveu HTTP {erro.code}."
        ) from None

    except (URLError, OSError, TimeoutError):
        # Não mostra o URL, que contém as coordenadas da instalação.
        raise ValueError(
            "Não foi possível contactar a Open-Meteo."
        ) from None

    except (UnicodeError, ValueError):
        raise ValueError(
            "A resposta não contém JSON válido."
        ) from None


def adquirir(historico, no_esperado, consultar=None, relogio=None):
    """
    Adquire e valida a previsão, sem escrever ficheiros.

    O transporte e o relógio podem ser substituídos nos testes.
    O instante final da consulta regista quando recebemos a resposta.
    """
    no = identificar_no(historico, no_esperado)

    obter_hora = relogio if relogio is not None else agora_utc
    consulta = consultar if consultar is not None else pedir_previsao

    iniciado = instante_utc(obter_hora())

    dia_alvo, inicio, fim = planear_periodo(
        no["fuso"],
        iniciado,
    )

    parametros = {
        "latitude": no["latitude"],
        "longitude": no["longitude"],
        "hourly": ",".join(UNIDADES),
        "timezone": "GMT",
        "timeformat": "iso8601",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "cell_selection": "land",
        "start_hour": inicio.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": fim.strftime("%Y-%m-%dT%H:%M"),
    }

    # Inclui o instante final para obter a precipitação e a radiação
    # correspondentes à última hora do dia alvo.
    # Esse instante adicional não cria outra hora energética.
    resposta = consulta(dict(parametros))
    concluido = instante_utc(obter_hora())

    if concluido < iniciado:
        raise ValueError("O relógio recuou durante a consulta.")

    if concluido >= inicio:
        raise ValueError("O dia alvo já começou durante a consulta.")

    # Reutiliza a validação de unidades, tipos e continuidade horária.
    linhas = preparar_meteorologia(resposta)

    quantidade = int((fim - inicio).total_seconds() / 3600)

    if (
        len(linhas) != quantidade + 1
        or linhas[0]["instante_meteo_utc"] != inicio.isoformat()
        or linhas[-1]["instante_meteo_utc"] != fim.isoformat()
    ):
        raise ValueError(
            "A previsão não cobre exatamente o período pedido."
        )

    # Só exige valores nos instantes necessários para representar
    # os intervalos do dia alvo, respeitando o significado temporal.
    for linha in linhas:
        instante = datetime.fromisoformat(
            linha["instante_meteo_utc"]
        )

        for campo in UNIDADES:
            necessario = (
                inicio < instante <= fim
                if campo in HORA_ANTERIOR
                else inicio <= instante < fim
            )

            if necessario and linha[campo] is None:
                raise ValueError(
                    f"Previsão incompleta: {campo}."
                )

    return {
        "no": no,
        "aquisicao": {
            "tipo": "previsao_meteorologica",
            "fonte": "Open-Meteo Weather Forecast API",
            "endpoint": ENDPOINT,
            "inicio_consulta_utc": iniciado.isoformat(),
            "fim_consulta_utc": concluido.isoformat(),
            "disponivel_desde_utc": concluido.isoformat(),
            "data_alvo_local": dia_alvo.isoformat(),
            "inicio_alvo_utc": inicio.isoformat(),
            "fim_alvo_exclusivo_utc": fim.isoformat(),
            "intervalos_horarios": quantidade,
            "instantes_recebidos": len(linhas),
            "selecao_modelo": "padrao_da_api",
            "parametros": parametros,
        },

        # Preserva a resposta, incluindo as coordenadas da grelha.
        # Não inventa o momento de produção dos modelos meteorológicos.
        "meteorologia": resposta,
    }


def verificar_destino(destino):
    """Exige um JSON novo em raw, ignorado pelo Git e não versionado."""
    caminho = Path(destino).resolve()
    raiz = AI_DIR.parent.resolve()

    if (
        not caminho.is_relative_to((AI_DIR / "data/raw").resolve())
        or caminho.suffix.lower() != ".json"
    ):
        raise ValueError(
            "O destino deve ser um JSON em ai/data/raw."
        )

    if caminho.exists():
        raise ValueError(
            "O destino já existe; não será substituído."
        )

    relativo = caminho.relative_to(raiz).as_posix()

    try:
        acompanhado = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relativo],
            cwd=raiz,
            capture_output=True,
            check=False,
        )

        ignorado = subprocess.run(
            ["git", "check-ignore", "-q", "--", relativo],
            cwd=raiz,
            capture_output=True,
            check=False,
        )

    except OSError:
        raise ValueError(
            "Não foi possível verificar o Git."
        ) from None

    if acompanhado.returncode != 1 or ignorado.returncode != 0:
        raise ValueError(
            "O destino deve estar ignorado e não acompanhado."
        )

    return caminho


def guardar(documento, destino):
    """Escreve num ficheiro novo e remove saídas parciais em caso de erro."""
    caminho = verificar_destino(destino)

    # Serializa antes de abrir o ficheiro.
    # Não permite NaN nem infinitos no JSON.
    texto = json.dumps(
        documento,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )

    caminho.parent.mkdir(parents=True, exist_ok=True)

    # O modo x recusa substituir um ficheiro existente.
    with caminho.open(
        "x",
        encoding="utf-8",
        newline="\n",
    ) as ficheiro:
        try:
            ficheiro.write(texto + "\n")
        except BaseException:
            ficheiro.close()
            caminho.unlink(missing_ok=True)
            raise

    return caminho


def main():
    """Executa uma aquisição manual para amanhã no fuso do nó."""
    parser = argparse.ArgumentParser(
        description=(
            "Adquire previsão meteorológica para amanhã "
            "no fuso do nó."
        )
    )

    parser.add_argument("--historico", type=Path, required=True)
    parser.add_argument("--no", required=True)

    opcoes = parser.parse_args()

    try:
        historico = json.loads(
            opcoes.historico.read_text(encoding="utf-8-sig")
        )

        no = identificar_no(historico, opcoes.no)

        # Cada execução recebe um nome com o instante UTC.
        # O modo x continua a impedir qualquer substituição.
        marca = agora_utc().strftime("%Y%m%dT%H%M%S%fZ")

        destino = (
            AI_DIR
            / "data/raw"
            / f"{no['no_id']}_previsao_meteo_{marca}.json"
        )

        # Verifica a proteção antes de contactar a API.
        verificar_destino(destino)

        documento = adquirir(historico, opcoes.no)
        caminho = guardar(documento, destino)

    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    resumo = documento["aquisicao"]

    print(f"Nó: {opcoes.no}")
    print(f"Dia alvo local: {resumo['data_alvo_local']}")
    print(f"Intervalos horários: {resumo['intervalos_horarios']}")
    print(
        f"Instantes meteorológicos: {resumo['instantes_recebidos']}"
    )
    print(
        "Resposta obtida em UTC: "
        f"{resumo['disponivel_desde_utc']}"
    )
    print(f"JSON guardado em: {caminho}")
    print(
        "Aquisição manual; sem agendamento "
        "nem emissão de previsão energética."
    )
    print(
        "A elegibilidade para uma emissão às 20h "
        "ainda não é avaliada aqui."
    )


# Importar o módulo nos testes não realiza pedidos nem cria ficheiros.
if __name__ == "__main__":
    main()