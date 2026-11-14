"""Adquire meteorologia histórica para a localização de um nó.

Lê os metadados de um histórico SmartLight já guardado.
Não contacta a API SmartLight nem utiliza a sua chave.

Guarda a resposta meteorológica e a identificação da aquisição
num novo JSON local, sem modificar os ficheiros existentes.
"""

import argparse
import json
import math
import re
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Reutiliza as variáveis, unidades e validações já testadas.
from ai.src.preparar_meteorologia import UNIDADES, preparar_meteorologia


AI_DIR = Path(__file__).resolve().parents[1]
RAIZ_REPOSITORIO = AI_DIR.parent
PASTA_RAW = AI_DIR / "data" / "raw"

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

# Estas variáveis descrevem a hora anterior ao timestamp da fonte.
# Para analisar [23:00, 00:00), precisamos do instante das 00:00.
HORA_ANTERIOR = (
    "precipitation",
    "diffuse_radiation",
    "shortwave_radiation",
)


def coordenada(valor, nome, limite):
    """Valida uma coordenada sem aceitar texto, booleanos ou ausências."""

    if type(valor) not in (int, float):
        raise ValueError(f"{nome}: esperado um número.")

    if not math.isfinite(valor) or not -limite <= valor <= limite:
        raise ValueError(f"{nome}: valor fora do intervalo permitido.")

    # Zero é uma coordenada válida.
    return float(valor)


def identificar_no(historico, no_esperado):
    """Obtém apenas os metadados necessários, sem copiar credenciais."""

    if (
        not isinstance(no_esperado, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,32}", no_esperado) is None
    ):
        raise ValueError("Identificador de nó inválido.")

    if not isinstance(historico, dict):
        raise ValueError("Esperado um objeto JSON de histórico.")

    no = historico.get("no")

    if not isinstance(no, dict) or no.get("no_id") != no_esperado:
        raise ValueError("O histórico não corresponde ao nó pedido.")

    fuso = no.get("fuso")
    if not isinstance(fuso, str) or not fuso.strip():
        raise ValueError("Falta o fuso horário do nó.")

    # O fuso local fica registado, mas o pedido meteorológico usa UTC.
    # A interpretação dos dias civis locais será feita noutra etapa.
    return {
        "no_id": no_esperado,
        "latitude": coordenada(no.get("latitude"), "Latitude", 90),
        "longitude": coordenada(no.get("longitude"), "Longitude", 180),
        "fuso": fuso,
    }


def ler_data(texto):
    """Aceita uma data escrita exatamente como AAAA-MM-DD."""

    if (
        not isinstance(texto, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto) is None
    ):
        raise ValueError("As datas devem usar o formato AAAA-MM-DD.")

    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError("Data de calendário inválida.") from None


def definir_periodo(inicio, fim):
    """Define dias UTC inclusivos e acrescenta o dia da margem."""

    primeiro_dia = ler_data(inicio)
    ultimo_dia = ler_data(fim)

    if primeiro_dia > ultimo_dia:
        raise ValueError("O início não pode ser posterior ao fim.")

    try:
        dia_margem = ultimo_dia + timedelta(days=1)

        inicio_utc = datetime.combine(
            primeiro_dia, time.min, tzinfo=timezone.utc
        )
        fim_exclusivo = datetime.combine(
            dia_margem, time.min, tzinfo=timezone.utc
        )

        # A API recebe datas completas. Pedimos o dia seguinte,
        # embora o cruzamento só necessite do seu primeiro instante.
        fim_resposta = fim_exclusivo + timedelta(hours=23)
    except (ValueError, OverflowError):
        raise ValueError("Período fora do intervalo suportado.") from None

    return inicio_utc, fim_exclusivo, fim_resposta


def pedir_meteorologia(parametros):
    """Faz um pedido HTTPS, com timeout e mensagens de erro simples."""

    # Não existe chave SmartLight neste pedido.
    url = ENDPOINT + "?" + urlencode(parametros)
    pedido = Request(url, headers={"Accept": "application/json"})

    try:
        with urlopen(pedido, timeout=60) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except HTTPError as erro:
        raise ValueError(
            f"Open-Meteo devolveu HTTP {erro.code}. "
            "Verifica o período e a disponibilidade do serviço."
        ) from None
    except (URLError, TimeoutError, OSError):
        # Não mostramos o URL, para evitar divulgar a localização.
        raise ValueError(
            "Não foi possível contactar a Open-Meteo."
        ) from None
    except (UnicodeError, ValueError):
        raise ValueError(
            "A Open-Meteo não devolveu um JSON válido."
        ) from None


def validar_periodo_meteo(resposta, inicio_utc, fim_exclusivo, fim_resposta):
    """Valida a sequência horária e os valores necessários ao cruzamento."""

    # A função existente verifica unidades, valores, ordem,
    # duplicados, horas em falta e identificação UTC.
    linhas = preparar_meteorologia(resposta)

    primeiro = datetime.fromisoformat(
        linhas[0]["instante_meteo_utc"]
    )
    ultimo = datetime.fromisoformat(
        linhas[-1]["instante_meteo_utc"]
    )

    quantidade_esperada = int(
        (fim_resposta - inicio_utc).total_seconds() / 3600
    ) + 1

    if (
        primeiro != inicio_utc
        or ultimo != fim_resposta
        or len(linhas) != quantidade_esperada
    ):
        raise ValueError(
            "A resposta não cobre o período meteorológico pedido."
        )

    # Nesta aquisição, só aceitamos uma resposta pronta para o
    # cruzamento: sem nulos nos valores efetivamente necessários.
    # Não substituímos ausências por zero nem por previsões.
    for linha in linhas:
        instante = datetime.fromisoformat(
            linha["instante_meteo_utc"]
        )

        for campo in UNIDADES:
            if campo in HORA_ANTERIOR:
                necessario = inicio_utc < instante <= fim_exclusivo
            else:
                necessario = inicio_utc <= instante < fim_exclusivo

            if necessario and linha[campo] is None:
                raise ValueError(
                    f"Meteorologia incompleta: {campo} em "
                    f"{instante.isoformat()}. "
                    "Nenhum valor foi preenchido."
                )

    return linhas


def adquirir(historico, no_esperado, inicio, fim, consultar=None):
    """Adquire e valida meteorologia sem escrever ficheiros.

    consultar permite substituir a Internet por uma resposta
    fictícia nos testes.
    """

    no = identificar_no(historico, no_esperado)
    inicio_utc, fim_exclusivo, fim_resposta = definir_periodo(inicio, fim)

    parametros = {
        "latitude": no["latitude"],
        "longitude": no["longitude"],
        "start_date": inicio,
        "end_date": fim_exclusivo.date().isoformat(),
        "hourly": ",".join(UNIDADES),
        "timezone": "GMT",
        "timeformat": "iso8601",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "cell_selection": "land",
    }

    # Sem parâmetro models, utiliza a seleção padrão da API.
    # Registamos essa opção sem atribuir um modelo específico
    # que a resposta não identifica por variável.
    consulta = consultar if consultar is not None else pedir_meteorologia

    iniciado = datetime.now(timezone.utc).isoformat()
    resposta = consulta(dict(parametros))
    concluido = datetime.now(timezone.utc).isoformat()

    linhas = validar_periodo_meteo(
        resposta, inicio_utc, fim_exclusivo, fim_resposta
    )

    return {
        "no": no,
        "aquisicao": {
            "fonte": "Open-Meteo Historical Weather API",
            "tipo": "meteorologia_historica",
            "endpoint": ENDPOINT,
            "inicio_consulta_utc": iniciado,
            "fim_consulta_utc": concluido,
            "inicio_alvo_utc": inicio_utc.isoformat(),
            "fim_alvo_exclusivo_utc": fim_exclusivo.isoformat(),
            "margem_final_horas_necessarias": 1,
            "selecao_modelo": "padrao_da_api",
            "parametros": parametros,
            "horas_recebidas": len(linhas),
        },
        # Preserva os valores e metadados devolvidos pela API.
        # As coordenadas devolvidas podem ser as da célula da grelha,
        # diferentes das coordenadas pedidas para a instalação.
        "meteorologia": resposta,
    }


def verificar_destino(destino):
    """Exige um novo JSON dentro de raw e ignorado pelo Git."""

    caminho = Path(destino).resolve()
    pasta = PASTA_RAW.resolve()

    if not caminho.is_relative_to(pasta) or caminho.suffix.lower() != ".json":
        raise ValueError("O destino deve ser um JSON dentro de ai/data/raw.")

    if caminho.exists():
        raise ValueError("O destino já existe; não será substituído.")

    relativo = caminho.relative_to(RAIZ_REPOSITORIO.resolve()).as_posix()

    try:
        # Um ficheiro acompanhado pelo Git não deve receber dados reais,
        # mesmo que exista uma regra posterior no .gitignore.
        acompanhado = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relativo],
            cwd=RAIZ_REPOSITORIO,
            capture_output=True,
            check=False,
        )
        ignorado = subprocess.run(
            ["git", "check-ignore", "-q", "--", relativo],
            cwd=RAIZ_REPOSITORIO,
            capture_output=True,
            check=False,
        )
    except OSError:
        raise ValueError("Não foi possível verificar a proteção no Git.") from None

    if acompanhado.returncode != 1 or ignorado.returncode != 0:
        raise ValueError("O destino deve estar ignorado e não acompanhado pelo Git.")

    return caminho


def guardar(documento, destino):
    """Guarda um novo ficheiro; nunca substitui uma aquisição anterior."""

    caminho = verificar_destino(destino)

    # Serializa antes de abrir a saída para detetar valores incompatíveis.
    texto = json.dumps(
        documento, ensure_ascii=False, indent=2, allow_nan=False
    )

    caminho.parent.mkdir(parents=True, exist_ok=True)

    # O modo x protege também contra a criação do mesmo ficheiro
    # entre a verificação anterior e este momento.
    with caminho.open("x", encoding="utf-8", newline="\n") as ficheiro:
        try:
            ficheiro.write(texto + "\n")
        except BaseException:
            # Fecha antes de remover, para compatibilidade com Windows.
            ficheiro.close()
            caminho.unlink(missing_ok=True)
            raise

    return caminho


def main():
    """Lê os argumentos, adquire os dados e apresenta um resumo."""

    parser = argparse.ArgumentParser(
        description="Adquire meteorologia histórica por nó e dias UTC."
    )
    parser.add_argument("--historico", required=True)
    parser.add_argument("--no", required=True)
    parser.add_argument("--inicio", required=True, help="AAAA-MM-DD UTC")
    parser.add_argument("--fim", required=True, help="AAAA-MM-DD UTC inclusivo")
    parser.add_argument("--destino", required=True)
    argumentos = parser.parse_args()

    try:
        # Verifica a saída antes de fazer qualquer pedido à Internet.
        destino = verificar_destino(argumentos.destino)

        historico = json.loads(
            Path(argumentos.historico).read_text(encoding="utf-8-sig")
        )

        documento = adquirir(
            historico,
            argumentos.no,
            argumentos.inicio,
            argumentos.fim,
        )
        caminho = guardar(documento, destino)

    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    print(f"Nó: {documento['no']['no_id']}")
    print(f"Período alvo UTC: {argumentos.inicio} a {argumentos.fim}")
    print(f"Horas recebidas: {documento['aquisicao']['horas_recebidas']}")
    print(f"JSON guardado em: {caminho}")
    print("Inclui o dia adicional necessário à fronteira final.")
    print("Meteorologia histórica; não representa previsão antecipada.")
    print("Sem cruzamento com sensores nem treino de modelos.")


if __name__ == "__main__":
    main()