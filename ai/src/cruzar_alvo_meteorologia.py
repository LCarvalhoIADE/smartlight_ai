"""Cruza alvos energéticos completos com meteorologia histórica.

Não consulta serviços externos, não altera as fontes e não treina modelos.
O resultado serve para análise histórica; não representa informação
meteorológica disponível antecipadamente no momento de uma previsão.
"""

import argparse
import csv
import json
import math
from datetime import timedelta
from pathlib import Path

# Reutiliza as validações já existentes.
from ai.src.adquirir_meteorologia import identificar_no, definir_periodo
from ai.src.preparar_alvo_energia import CAMPOS_SAIDA, selecionar_alvo
from ai.src.preparar_meteorologia import preparar_meteorologia
from ai.src.cruzar_meteorologia import (
    ler_hora_utc,
    VARIAVEIS_INSTANTANEAS,
    VARIAVEIS_HORA_ANTERIOR,
)


AI_DIR = Path(__file__).resolve().parents[1]

# Conserva todos os campos do alvo e acrescenta a meteorologia.
CAMPOS_CRUZADOS = (
    *CAMPOS_SAIDA,
    "meteo_tipo",
    "meteo_instante_utc",
    "meteo_fim_intervalo_utc",
    *(f"meteo_{campo}" for campo in VARIAVEIS_INSTANTANEAS),
    *(f"meteo_{campo}" for campo in VARIAVEIS_HORA_ANTERIOR),
)


def mesma_coordenada(valor, esperado):
    """Compara coordenadas numéricas, rejeitando ausências e booleanos."""

    return (
        type(valor) in (int, float)
        and math.isfinite(valor)
        and math.isclose(valor, esperado, rel_tol=0, abs_tol=1e-9)
    )


def validar_associacao(documento, historico, no_esperado):
    """Confirma que o documento meteorológico pertence à instalação.

    Compara as coordenadas pedidas, não as coordenadas da célula
    meteorológica devolvidas pela Open-Meteo.
    """

    if not isinstance(documento, dict):
        raise ValueError("Esperado um documento meteorológico.")

    # Os dois documentos devem identificar o mesmo nó.
    no_historico = identificar_no(historico, no_esperado)
    no_meteo = identificar_no(documento, no_esperado)

    for campo in ("latitude", "longitude"):
        if not mesma_coordenada(no_meteo[campo], no_historico[campo]):
            raise ValueError(
                "As coordenadas meteorológicas diferem das do histórico."
            )

    if no_meteo["fuso"] != no_historico["fuso"]:
        raise ValueError("O fuso do nó difere entre as fontes.")

    aquisicao = documento.get("aquisicao")
    if not isinstance(aquisicao, dict):
        raise ValueError("Faltam os metadados da aquisição meteorológica.")

    # Não aceita uma previsão meteorológica como se fosse histórico.
    if aquisicao.get("tipo") != "meteorologia_historica":
        raise ValueError("Esperada meteorologia histórica.")

    parametros = aquisicao.get("parametros")
    if not isinstance(parametros, dict):
        raise ValueError("Faltam os parâmetros da aquisição.")

    # Verifica também a localização efetivamente usada no pedido.
    for campo in ("latitude", "longitude"):
        if not mesma_coordenada(
            parametros.get(campo), no_historico[campo]
        ):
            raise ValueError("As coordenadas do pedido são incompatíveis.")

    if parametros.get("timezone") != "GMT":
        raise ValueError("O pedido meteorológico deve utilizar GMT.")

    inicio = ler_hora_utc(aquisicao.get("inicio_alvo_utc"))
    fim = ler_hora_utc(aquisicao.get("fim_alvo_exclusivo_utc"))

    if inicio >= fim or inicio.hour != 0 or fim.hour != 0:
        raise ValueError("Período alvo meteorológico inválido.")

    # O formato de aquisição atual pede dias completos,
    # incluindo o dia posterior ao último dia alvo.
    inicio_esperado, fim_esperado, _ = definir_periodo(
        inicio.date().isoformat(),
        (fim - timedelta(days=1)).date().isoformat(),
    )

    if (
        inicio != inicio_esperado
        or fim != fim_esperado
        or parametros.get("start_date") != inicio.date().isoformat()
        or parametros.get("end_date") != fim.date().isoformat()
    ):
        raise ValueError("Datas do pedido incompatíveis com o período alvo.")

    return inicio, fim


def cruzar_alvo(alvos, documento, historico, no_esperado):
    """Devolve todas as linhas do alvo com meteorologia, ou lança erro.

    Não elimina silenciosamente horas incompletas, não cria horas
    para preencher lacunas e não modifica as entradas.
    """

    inicio_periodo, fim_periodo = validar_associacao(
        documento, historico, no_esperado
    )

    # Valida novamente energia, unidades, duplicados e referências.
    selecao = selecionar_alvo(alvos, no_esperado)

    # A entrada deve ser o alvo já selecionado, não um CSV energético
    # contendo horas parciais que seriam descartadas nesta etapa.
    if selecao["excluidas_parciais"] or selecao["excluidas_sem_cobertura"]:
        raise ValueError("O alvo contém horas sem cobertura completa.")

    # Reutiliza a validação horária da resposta original.
    meteorologia = preparar_meteorologia(
        documento.get("meteorologia")
    )
    indice = {
        ler_hora_utc(linha["instante_meteo_utc"]): linha
        for linha in meteorologia
    }

    resultado = []

    for alvo in selecao["aceites"]:
        inicio = ler_hora_utc(alvo["hora_utc"])
        fim = inicio + timedelta(hours=1)

        if inicio < inicio_periodo or fim > fim_periodo:
            raise ValueError("Uma hora do alvo está fora do período meteorológico.")

        # Para [10:00, 11:00), são necessários os instantes 10:00 e 11:00.
        if inicio not in indice or fim not in indice:
            raise ValueError("Falta meteorologia para uma hora do alvo.")

        linha = dict(alvo)
        linha["meteo_tipo"] = "meteorologia_historica"
        linha["meteo_instante_utc"] = inicio.isoformat()
        linha["meteo_fim_intervalo_utc"] = fim.isoformat()

        for campos, instante in (
            (VARIAVEIS_INSTANTANEAS, inicio),
            (VARIAVEIS_HORA_ANTERIOR, fim),
        ):
            for campo in campos:
                valor = indice[instante][campo]

                # Não preenche nulos nem elimina a hora afetada.
                # Interrompe para que a ausência seja investigada.
                if valor is None:
                    raise ValueError(
                        f"Meteorologia ausente: {campo} "
                        f"em {instante.isoformat()}."
                    )

                linha[f"meteo_{campo}"] = valor

        resultado.append(linha)

    return resultado


def ler_alvo(caminho):
    """Lê o CSV e rejeita cabeçalhos ou linhas estruturalmente inválidos."""

    with Path(caminho).open(
        "r", encoding="utf-8-sig", newline=""
    ) as ficheiro:
        leitor = csv.DictReader(ficheiro)
        campos = leitor.fieldnames

        if not campos or len(campos) != len(set(campos)):
            raise ValueError("Cabeçalho vazio ou com colunas repetidas.")

        linhas = list(leitor)

    # No CSV, uma célula vazia é "", enquanto campos em falta
    # produzem None. Campos adicionais produzem a chave None.
    if any(
        None in linha or any(valor is None for valor in linha.values())
        for linha in linhas
    ):
        raise ValueError("Linha CSV com número incorreto de campos.")

    return linhas


def guardar(linhas, destino):
    """Guarda um novo CSV dentro de processed, sem substituir ficheiros."""

    caminho = Path(destino).resolve()
    pasta = (AI_DIR / "data" / "processed").resolve()

    if not caminho.is_relative_to(pasta) or caminho.suffix.lower() != ".csv":
        raise ValueError("O destino deve ser um CSV em ai/data/processed.")

    if not linhas:
        raise ValueError("Não existem linhas para guardar.")

    if caminho.exists():
        raise ValueError("O destino já existe; não será substituído.")

    caminho.parent.mkdir(parents=True, exist_ok=True)

    # O modo x recusa substituir um ficheiro que entretanto seja criado.
    with caminho.open("x", encoding="utf-8", newline="") as ficheiro:
        try:
            escritor = csv.DictWriter(
                ficheiro, fieldnames=CAMPOS_CRUZADOS
            )
            escritor.writeheader()
            escritor.writerows(linhas)
        except BaseException:
            # Evita deixar um CSV parcial quando a escrita falha.
            ficheiro.close()
            caminho.unlink(missing_ok=True)
            raise

    return caminho


def main():
    """Lê as três fontes locais e cria o CSV histórico cruzado."""

    parser = argparse.ArgumentParser(
        description="Cruza alvo energético com meteorologia histórica."
    )
    parser.add_argument("--alvo", type=Path, required=True)
    parser.add_argument("--meteorologia", type=Path, required=True)
    parser.add_argument("--historico", type=Path, required=True)
    parser.add_argument("--no", required=True)
    parser.add_argument("--destino", type=Path, required=True)
    opcoes = parser.parse_args()

    try:
        alvos = ler_alvo(opcoes.alvo)
        documento = json.loads(
            opcoes.meteorologia.read_text(encoding="utf-8-sig")
        )
        historico = json.loads(
            opcoes.historico.read_text(encoding="utf-8-sig")
        )

        linhas = cruzar_alvo(alvos, documento, historico, opcoes.no)
        caminho = guardar(linhas, opcoes.destino)

    except (ValueError, OSError) as erro:
        parser.exit(1, f"Erro: {erro}\n")

    print(f"Nó: {opcoes.no}")
    print(f"Horas do alvo: {len(alvos)}")
    print(f"Linhas cruzadas: {len(linhas)}")
    print(f"Primeira hora UTC: {linhas[0]['hora_utc']}")
    print(f"Última hora UTC: {linhas[-1]['hora_utc']}")
    print(f"CSV guardado em: {caminho}")
    print("Origens energéticas, referências e lacunas preservadas.")
    print("Meteorologia histórica; não representa previsão antecipada.")
    print("Ainda não constitui o conjunto final de treino.")


if __name__ == "__main__":
    main()