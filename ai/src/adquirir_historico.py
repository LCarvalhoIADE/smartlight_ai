"""
Adquire históricos da API SmartLight e guarda-os localmente.

- Autentica através do cabeçalho X-Chave.
- Remove espaços acidentais nas extremidades da chave.
- Recolhe todas as páginas do período pedido.
- Valida o histórico antes de guardar.
- Preserva os metadados e os valores recebidos.
- Recusa substituir ficheiros existentes.
- Não consulta meteorologia nem calcula energia.
"""

import argparse
import getpass
import json
import os
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from ai.src.validar_historico import validar_historico


# Localiza a componente de IA e a raiz do repositório.
AI_DIR = Path(__file__).resolve().parents[1]
RAIZ_REPOSITORIO = AI_DIR.parent

# A chave nunca é acrescentada a este endereço.
ENDPOINT = "https://51-178-48-58.sslip.io/historico.php"


class SemRedirecionamentos(HTTPRedirectHandler):
    """Impede enviar a chave para outro destino por redirecionamento."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalizar_chave(chave):
    """Remove espaços exteriores e rejeita uma chave vazia ou malformada."""
    if not isinstance(chave, str):
        raise ValueError("Chave de acesso inválida.")

    # Remove espaços, tabulações e quebras de linha nas extremidades.
    # Estes caracteres podem aparecer ao copiar e colar a chave.
    chave = chave.strip()

    # Não corrigimos espaços interiores silenciosamente.
    # Nesse caso, a chave deve ser novamente introduzida.
    if not chave or any(caractere.isspace() for caractere in chave):
        raise ValueError("Chave vazia ou com espaços no interior.")

    return chave


def limites_utc(inicio, fim):
    """Converte datas inclusivas em limites Unix UTC para a API."""
    try:
        primeiro_dia = date.fromisoformat(inicio)
        ultimo_dia = date.fromisoformat(fim)

        if primeiro_dia > ultimo_dia:
            raise ValueError

        primeiro_instante = datetime.combine(
            primeiro_dia,
            time.min,
            tzinfo=timezone.utc,
        )

        # A data final é inclusiva.
        # Calculamos a meia-noite seguinte e retiramos um segundo.
        fim_exclusivo = datetime.combine(
            ultimo_dia + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

        de = int(primeiro_instante.timestamp())
        ate = int(fim_exclusivo.timestamp()) - 1

        if de <= 0:
            raise ValueError

    except (TypeError, ValueError, OverflowError):
        raise ValueError(
            "Usa datas válidas AAAA-MM-DD, com início anterior "
            "ou igual ao fim e timestamps positivos."
        ) from None

    return de, ate


def pedir_pagina(parametros, chave):
    """Executa um GET HTTPS com a chave apenas no cabeçalho X-Chave."""
    # Normaliza também aqui para proteger utilizações diretas da função.
    chave = normalizar_chave(chave)

    # Apenas os parâmetros de consulta são colocados no URL.
    # Os parâmetros gerados por adquirir não incluem credenciais.
    url = ENDPOINT + "?" + urlencode(parametros)

    pedido = Request(
        url,
        headers={
            "X-Chave": chave,
            "Accept": "application/json",
        },
    )

    # Mantém a validação HTTPS normal e bloqueia redirecionamentos.
    cliente = build_opener(SemRedirecionamentos())

    try:
        with cliente.open(pedido, timeout=60) as resposta:
            conteudo = resposta.read()

        return json.loads(conteudo.decode("utf-8-sig"))

    except HTTPError as erro:
        # Não apresenta o corpo da resposta nem os cabeçalhos.
        if erro.code == 403:
            raise RuntimeError(
                "HTTP 403: acesso recusado. Confirma a chave de leitura "
                "ou administração e o suporte a X-Chave no servidor."
            ) from None

        raise RuntimeError(
            f"A API respondeu com erro HTTP {erro.code}."
        ) from None

    except (URLError, TimeoutError, OSError):
        raise RuntimeError(
            "Não foi possível contactar a API."
        ) from None

    except (UnicodeError, ValueError):
        raise RuntimeError(
            "A API não devolveu JSON válido."
        ) from None


def adquirir(
    no_id,
    de,
    ate,
    chave,
    limite=10000,
    max_paginas=1000,
    consultar=None,
):
    """
    Reúne e valida as páginas de um nó e período.

    consultar permite substituir os pedidos HTTP por respostas fictícias
    nos testes. Em utilização normal, usa a função pedir_pagina.
    """
    if not isinstance(no_id, str) or not no_id.strip():
        raise ValueError("Identificador de nó inválido.")

    if (
        type(de) is not int
        or type(ate) is not int
        or de <= 0
        or de > ate
    ):
        raise ValueError("Limites temporais inválidos.")

    # Remove espaços exteriores antes de qualquer consulta.
    chave = normalizar_chave(chave)

    if type(limite) is not int or not 1 <= limite <= 10000:
        raise ValueError("O limite deve estar entre 1 e 10000.")

    if type(max_paginas) is not int or max_paginas <= 0:
        raise ValueError("O máximo de páginas deve ser positivo.")

    consultar = consultar or pedir_pagina
    leituras = []
    metadados = None
    desloca = 0
    ultimo_ts = None
    inicio_aquisicao = datetime.now(timezone.utc).isoformat()

    for numero_pagina in range(1, max_paginas + 1):
        # Os limites temporais ficam fixos durante toda a aquisição.
        # A chave é passada separadamente, nunca nestes parâmetros.
        parametros = {
            "no_id": no_id,
            "de": de,
            "ate": ate,
            "limite": limite,
            "desloca": desloca,
        }

        pagina = consultar(parametros, chave)

        if not isinstance(pagina, dict):
            raise ValueError("Resposta da API em formato inválido.")

        no = pagina.get("no")
        if not isinstance(no, dict) or no.get("no_id") != no_id:
            raise ValueError("A API devolveu um nó diferente do pedido.")

        # Confirma que todas as páginas correspondem ao mesmo período.
        if (
            type(pagina.get("de")) is not int
            or type(pagina.get("ate")) is not int
            or pagina["de"] != de
            or pagina["ate"] != ate
        ):
            raise ValueError("A API devolveu um período diferente.")

        if type(pagina.get("mais")) is not bool:
            raise ValueError("Indicador de paginação inválido.")

        linhas = pagina.get("leituras")
        if not isinstance(linhas, list) or len(linhas) > limite:
            raise ValueError("Lista de leituras inválida.")

        # No endpoint atual, uma página com continuação contém
        # a quantidade de leituras definida pelo limite.
        if pagina["mais"] and len(linhas) != limite:
            raise ValueError(
                "Página incompleta com indicação de continuação."
            )

        if metadados is None:
            metadados = dict(no)
        elif no != metadados:
            raise ValueError(
                "Os metadados do nó mudaram entre páginas."
            )

        # Confirma a ordem temporal dentro das páginas e entre páginas.
        # Timestamps iguais podem pertencer a divisões diferentes.
        for leitura in linhas:
            if not isinstance(leitura, dict):
                raise ValueError("Leitura em formato inválido.")

            ts = leitura.get("ts")
            if type(ts) is not int or not de <= ts <= ate:
                raise ValueError(
                    "Timestamp inválido ou fora do período."
                )

            if ultimo_ts is not None and ts < ultimo_ts:
                raise ValueError(
                    "As páginas não estão ordenadas por timestamp."
                )

            ultimo_ts = ts

        leituras.extend(linhas)
        desloca += len(linhas)

        if not pagina["mais"]:
            conjunto = {
                "no": metadados,
                "de": de,
                "ate": ate,
                "mais": False,
                "leituras": leituras,
                "aquisicao": {
                    "origem": "historico.php",
                    "inicio_utc": inicio_aquisicao,
                    "fim_utc": datetime.now(timezone.utc).isoformat(),
                    "paginas_recolhidas": numero_pagina,
                    "total_leituras": len(leituras),
                },
            }

            # Reutiliza a validação existente, incluindo duplicados.
            # Não guarda um conjunto vazio ou estruturalmente inválido.
            validar_historico(conjunto, no_esperado=no_id)
            return conjunto

    raise ValueError(
        "Foi atingido o máximo de páginas sem terminar a aquisição."
    )


def verificar_destino(destino):
    """Exige um ficheiro novo dentro de ai/data/raw e fora do Git."""
    destino = Path(destino).resolve()
    pasta_raw = (AI_DIR / "data/raw").resolve()

    if not destino.is_relative_to(pasta_raw):
        raise ValueError(
            "O destino deve ficar dentro de ai/data/raw."
        )

    if destino.suffix.lower() != ".json":
        raise ValueError("O destino deve ter extensão .json.")

    if destino.exists():
        raise ValueError(
            "O destino já existe; não será substituído."
        )

    relativo = destino.relative_to(
        RAIZ_REPOSITORIO.resolve()
    ).as_posix()

    try:
        acompanhado = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relativo],
            cwd=RAIZ_REPOSITORIO,
            capture_output=True,
            text=True,
            check=False,
        )

        ignorado = subprocess.run(
            ["git", "check-ignore", "-q", "--", relativo],
            cwd=RAIZ_REPOSITORIO,
            capture_output=True,
            text=True,
            check=False,
        )

    except OSError:
        raise RuntimeError(
            "Não foi possível executar o Git."
        ) from None

    # ls-files devolve 1 quando o caminho não está acompanhado.
    # check-ignore devolve 0 quando o caminho está ignorado.
    if acompanhado.returncode != 1 or ignorado.returncode != 0:
        raise ValueError(
            "O destino deve estar ignorado e não acompanhado pelo Git."
        )

    return destino


def guardar(conjunto, destino):
    """Guarda o conjunto validado sem substituir aquisições anteriores."""
    # Valida novamente para permitir utilizar esta função separadamente.
    no = conjunto.get("no", {}) if isinstance(conjunto, dict) else {}
    no_id = no.get("no_id") if isinstance(no, dict) else None
    validar_historico(conjunto, no_esperado=no_id)

    destino = verificar_destino(destino)

    # Prepara o JSON antes de abrir o ficheiro.
    # NaN e Infinity não pertencem ao formato JSON padrão.
    texto = json.dumps(
        conjunto,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)

    # O modo x cria exclusivamente um ficheiro novo.
    # Se a escrita falhar, remove apenas o ficheiro criado nesta operação.
    with destino.open("x", encoding="utf-8", newline="\n") as ficheiro:
        try:
            ficheiro.write(texto)
            ficheiro.write("\n")
            ficheiro.flush()
        except BaseException:
            ficheiro.close()
            destino.unlink(missing_ok=True)
            raise

    return destino


def main():
    """Recebe parâmetros, obtém a chave e executa a aquisição."""
    argumentos = argparse.ArgumentParser(
        description=(
            "Adquire um histórico SmartLight por dias completos UTC."
        )
    )
    argumentos.add_argument("--no", required=True)
    argumentos.add_argument(
        "--inicio",
        required=True,
        help="AAAA-MM-DD UTC",
    )
    argumentos.add_argument(
        "--fim",
        required=True,
        help="AAAA-MM-DD UTC inclusivo",
    )
    argumentos.add_argument("--destino", type=Path)
    argumentos.add_argument("--limite", type=int, default=10000)
    opcoes = argumentos.parse_args()

    try:
        de, ate = limites_utc(opcoes.inicio, opcoes.fim)

        # Evita separadores de caminhos no nome automático do ficheiro.
        caracteres_permitidos = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789_-"
        )

        if not opcoes.no or any(
            caractere not in caracteres_permitidos
            for caractere in opcoes.no
        ):
            raise ValueError(
                "Usa um identificador de nó com letras, números, _ ou -."
            )

        destino = opcoes.destino or (
            AI_DIR
            / "data/raw"
            / f"{opcoes.no}_historico_{opcoes.inicio}_{opcoes.fim}.json"
        )

        # Verifica o destino antes de pedir a chave ou contactar a API.
        verificar_destino(destino)

        # A variável de ambiente é opcional.
        # Mostra apenas a origem da chave, nunca o respetivo valor.
        chave = os.environ.get("SMARTLIGHT_API_CHAVE")

        if chave is not None and chave.strip():
            print("Autenticação: chave obtida da variável de ambiente.")
        else:
            print(
                "Introduz a chave de leitura ou administração. "
                "Os caracteres não serão apresentados."
            )
            chave = getpass.getpass("Chave da API: ")

        # A função adquirir normaliza a chave antes de a utilizar.
        conjunto = adquirir(
            opcoes.no,
            de,
            ate,
            chave,
            limite=opcoes.limite,
        )

        caminho = guardar(conjunto, destino)

    except (ValueError, RuntimeError, OSError) as erro:
        # Os erros de rede são apresentados sem cabeçalhos ou credenciais.
        argumentos.exit(1, f"Erro: {erro}\n")

    print(f"Nó: {conjunto['no']['no_id']}")
    print(f"Leituras guardadas: {len(conjunto['leituras'])}")
    print(f"Páginas: {conjunto['aquisicao']['paginas_recolhidas']}")
    print(f"JSON guardado em: {caminho}")
    print("Sem meteorologia nem cálculo energético.")


if __name__ == "__main__":
    main()