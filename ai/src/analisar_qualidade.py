"""
Analisa a qualidade de uma amostra de leituras do nó no3.

Apresenta:
- Número de leituras e período abrangido.
- Valores nulos por campo.
- Intervalos entre leituras de cada nó e divisão.
- Alertas de possíveis interrupções na recolha.

Não altera os dados originais, não preenche falhas
e não calcula consumo energético.
"""

import json
from collections import defaultdict

# Reutilizamos os caminhos, campos e validações do script anterior.
from ai.src.preparar_dados import AI_DIR, CAMPOS, preparar


def analisar(dados, limite_intervalo=30):
    """
    Valida as leituras e devolve um dicionário com o resumo.

    Parâmetros:
        dados: lista de leituras obtidas do JSON.
        limite_intervalo: intervalo máximo, em segundos, sem alerta.

    Resultado:
        Dicionário com totais, datas UTC, nulos e análise por divisão.

    Limitação:
        A função preparar mantém a validação restrita ao nó no3.
        Dados inválidos ou duplicados interrompem a análise com ValueError.
    """

    # O limite deve ser um número positivo e finito.
    # O uso de type também impede aceitar True e False como números.
    if type(limite_intervalo) not in (int, float) or not (
        0 < limite_intervalo < float("inf")
    ):
        raise ValueError(
            "O limite do intervalo deve ser positivo e finito."
        )

    # A validação existente cria novas linhas e ordena-as pelo timestamp.
    # A lista original recebida pela função permanece inalterada.
    leituras = preparar(dados)

    # Cada combinação de nó e divisão terá uma lista própria.
    # Assim, leituras de divisões diferentes não são comparadas entre si.
    grupos = defaultdict(list)

    for leitura in leituras:
        chave = (leitura["no_id"], leitura["divisao"])
        grupos[chave].append(leitura)

    resumo_grupos = []

    # Ordenamos os grupos para apresentar os resultados de forma estável.
    for (no_id, divisao), linhas in sorted(grupos.items()):
        intervalos = []
        alertas = []

        # zip junta cada leitura à seguinte:
        # primeira com segunda, segunda com terceira, e assim por diante.
        for anterior, atual in zip(linhas, linhas[1:]):

            # Os timestamps estão em segundos.
            # A diferença representa o tempo entre duas leituras.
            intervalo = atual["ts"] - anterior["ts"]
            intervalos.append(intervalo)

            # A recolha prevista ocorre aproximadamente a cada 15 segundos.
            # Mais de 30 segundos gera um alerta para investigar.
            # Exatamente 30 segundos não gera alerta.
            if intervalo > limite_intervalo:
                alertas.append({
                    "inicio_utc": anterior["data_utc"],
                    "fim_utc": atual["data_utc"],
                    "intervalo_segundos": intervalo,
                })

        # Uma única leitura não permite calcular intervalos.
        # Nesse caso usamos None, em vez de inventar um intervalo zero.
        resumo_grupos.append({
            "no_id": no_id,
            "divisao": divisao,
            "total": len(linhas),
            "inicio_utc": linhas[0]["data_utc"],
            "fim_utc": linhas[-1]["data_utc"],
            "intervalo_minimo": min(intervalos) if intervalos else None,
            "intervalo_maximo": max(intervalos) if intervalos else None,
            "alertas": alertas,
        })

    # Contamos os valores None de cada campo.
    # A validação anterior só permite nulos no campo luz_pct.
    nulos = {
        campo: sum(linha[campo] is None for linha in leituras)
        for campo in CAMPOS
    }

    # Devolver o resumo, em vez de apenas o imprimir, permite
    # testar os resultados e reutilizá-los noutros scripts.
    return {
        "total": len(leituras),
        "inicio_utc": leituras[0]["data_utc"],
        "fim_utc": leituras[-1]["data_utc"],
        "nulos": nulos,
        "limite_intervalo": limite_intervalo,
        "grupos": resumo_grupos,
    }


def main():
    """Lê a amostra local e apresenta o resumo no terminal."""

    # AI_DIR aponta para a pasta ai, definida no script de preparação.
    origem = AI_DIR / "data/raw/no3_amostra.json"

    # utf-8-sig permite ler UTF-8 com ou sem a marca inicial BOM,
    # que pode estar presente em ficheiros guardados no Windows.
    dados = json.loads(origem.read_text(encoding="utf-8-sig"))

    # Usa o limite padrão de 30 segundos.
    resumo = analisar(dados)

    print(f"Total de leituras: {resumo['total']}")
    print(f"Início UTC: {resumo['inicio_utc']}")
    print(f"Fim UTC: {resumo['fim_utc']}")
    print(f"Valores nulos: {resumo['nulos']}")

    # Apresentamos separadamente os resultados de cada nó e divisão.
    for grupo in resumo["grupos"]:
        print(
            f"\nNó: {grupo['no_id']} | Divisão: {grupo['divisao']}"
        )
        print(f"Leituras: {grupo['total']}")

        if grupo["intervalo_minimo"] is None:
            print(
                "Apenas uma leitura: não é possível calcular intervalos."
            )
        else:
            print(
                "Intervalos entre leituras: "
                f"{grupo['intervalo_minimo']}–"
                f"{grupo['intervalo_maximo']} segundos"
            )

        print(
            f"Intervalos superiores a "
            f"{resumo['limite_intervalo']} segundos: "
            f"{len(grupo['alertas'])}"
        )

        # Se não houver alertas, este ciclo não imprime nenhuma linha.
        for alerta in grupo["alertas"]:
            print(
                f"  {alerta['inicio_utc']} → {alerta['fim_utc']}: "
                f"{alerta['intervalo_segundos']} segundos"
            )

    # A ausência de alertas não prova que todo o histórico está completo.
    # Só analisámos os intervalos internos da amostra disponível.
    print(
        "\nOs alertas indicam possíveis interrupções, "
        "não perdas confirmadas."
    )
    print(
        "Análise limitada ao período da amostra. "
        "Dados originais preservados."
    )


# Executa main apenas quando este módulo é iniciado diretamente.
# Importar a função analisar nos testes não executa a leitura do ficheiro.
if __name__ == "__main__":
    main()