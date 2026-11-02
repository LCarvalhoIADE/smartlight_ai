# Bibliotecas necessárias para ler o JSON, criar CSV,
# trabalhar com datas e localizar ficheiros.
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


# Localiza a pasta principal da componente de IA,
# independentemente da pasta a partir da qual o programa é executado.
AI_DIR = Path(__file__).resolve().parents[1]

# Colunas mantidas na saída para preservar a compatibilidade
# com os scripts de análise e com a exportação para CSV.
CAMPOS = (
    "no_id", "divisao", "ts", "luz_raw", "luz_pct",
    "presenca", "led_pct", "modo", "hora",
)

# O TSV não contém hora. Esse campo é opcional porque
# o instante da leitura já está identificado pelo timestamp ts.
CAMPOS_OBRIGATORIOS = tuple(
    campo for campo in CAMPOS if campo != "hora"
)

# Estas colunas devem existir, mas podem não ter uma medição.
# None significa ausência de valor, não uma medição igual a zero.
CAMPOS_ACEITAM_NULO = ("luz_raw", "luz_pct")


def preparar(dados, no_esperado="no3"):
    """Valida e ordena leituras, acrescentando a data em UTC.

    Aceita leituras com ou sem o campo hora e preserva valores
    ausentes de luminosidade, sem modificar os dados originais.
    """

    # Confirma que os dados são uma lista e que não está vazia.
    if not isinstance(dados, list) or not dados:
        raise ValueError("Esperada uma lista não vazia de leituras.")

    # Guarda os registos validados e os identificadores já encontrados.
    resultado = []
    identificadores = set()

    # Percorre cada leitura, numerando-a para identificar possíveis erros.
    for numero, leitura in enumerate(dados, start=1):

        # Cada leitura deve ser representada por um dicionário.
        if not isinstance(leitura, dict):
            raise ValueError(f"Leitura {numero}: formato inválido.")

        # Confirma que os oito campos obrigatórios estão presentes.
        # hora é opcional, pois não existe na exportação TSV.
        if not set(CAMPOS_OBRIGATORIOS).issubset(leitura):
            raise ValueError(f"Leitura {numero}: faltam campos.")

        # Não permite valores nulos nos campos obrigatórios,
        # exceto luz_raw e luz_pct, que podem não ter medição.
        # A coluna deve existir mesmo quando o seu valor é None.
        if any(
            leitura[campo] is None
            for campo in CAMPOS_OBRIGATORIOS
            if campo not in CAMPOS_ACEITAM_NULO
        ):
            raise ValueError(f"Leitura {numero}: campo obrigatório nulo.")

        # Confirma que a leitura pertence ao nó que estamos a analisar.
        if leitura["no_id"] != no_esperado:
            raise ValueError(f"Leitura {numero}: nó inesperado.")

        # A divisão deve ser um texto válido e não pode estar vazia.
        if (
            not isinstance(leitura["divisao"], str)
            or not leitura["divisao"].strip()
        ):
            raise ValueError(f"Leitura {numero}: divisão inválida.")

        # O timestamp deve ser um número inteiro positivo.
        # A comparação exata do tipo também impede aceitar True,
        # que em Python pode comportar-se como o número 1.
        ts = leitura["ts"]
        if type(ts) is not int or ts <= 0:
            raise ValueError(f"Leitura {numero}: timestamp inválido.")

        # A presença só pode assumir dois valores:
        # 0 = ausência de presença; 1 = presença detetada.
        if (
            type(leitura["presenca"]) not in (int, bool)
            or leitura["presenca"] not in (0, 1)
        ):
            raise ValueError(f"Leitura {numero}: presença inválida.")

        # Valida as percentagens de intensidade do LED e luminosidade.
        # Apenas são aceites valores entre 0 e 100.
        for campo in ("led_pct", "luz_pct"):
            valor = leitura[campo]

            # A luminosidade percentual pode ser nula quando
            # não existe uma medição percentual disponível.
            if campo == "luz_pct" and valor is None:
                continue

            if type(valor) not in (int, float) or not 0 <= valor <= 100:
                raise ValueError(f"Leitura {numero}: {campo} inválido.")

        # Combina o nó, a divisão e o instante da leitura
        # para identificar registos repetidos.
        chave = (leitura["no_id"], leitura["divisao"], ts)

        # Um identificador repetido indica uma leitura duplicada.
        if chave in identificadores:
            raise ValueError(f"Leitura {numero}: registo duplicado.")
        identificadores.add(chave)

        # Converte o timestamp Unix para uma data em UTC.
        # A conversão permite trabalhar com instantes padronizados.
        # O campo hora recebido não é utilizado nesta conversão.
        try:
            data_utc = datetime.fromtimestamp(ts, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError) as erro:
            raise ValueError(
                f"Leitura {numero}: timestamp fora do intervalo."
            ) from erro

        # Cria um novo registo para preservar os dados originais.
        # get() devolve None quando hora não existe no TSV.
        # Se hora existir, o seu valor original é preservado.
        # Os restantes campos já foram exigidos na validação anterior.
        linha = {campo: leitura.get(campo) for campo in CAMPOS}

        # Acrescenta a data UTC calculada a partir de ts.
        linha["data_utc"] = data_utc

        resultado.append(linha)

    # Devolve as leituras ordenadas da mais antiga para a mais recente.
    return sorted(resultado, key=lambda linha: linha["ts"])


def main():
    """Lê a amostra JSON, prepara as leituras e exporta para CSV."""

    # Caminhos dos ficheiros de entrada e saída.
    # Nesta etapa, a execução direta mantém a amostra JSON.
    origem = AI_DIR / "data/raw/no3_amostra.json"
    destino = AI_DIR / "data/processed/no3_preparado.csv"

    # Lê o ficheiro JSON e transforma o conteúdo em objetos Python.
    dados = json.loads(origem.read_text(encoding="utf-8-sig"))

    # Valida e organiza os registos utilizando a função preparar().
    linhas = preparar(dados)

    # Garante que a pasta de destino existe.
    destino.parent.mkdir(parents=True, exist_ok=True)

    # Cria o CSV com as colunas definidas e a nova data em UTC.
    # O modo "w" substitui o CSV de saída em cada execução.
    # Os valores None são escritos como células vazias.
    with destino.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(
            ficheiro, fieldnames=[*CAMPOS, "data_utc"]
        )

        # Escreve os nomes das colunas e os registos preparados.
        escritor.writeheader()
        escritor.writerows(linhas)

    # Apresenta informações sobre o processamento no terminal.
    print(f"Leituras preparadas: {len(linhas)}")
    print(f"CSV guardado em: {destino}")
    print("Sem cálculo de consumo nem treino de modelos.")


# Garante que main() só é executada quando este ficheiro
# é iniciado diretamente, e não quando é importado por outro módulo.
if __name__ == "__main__":
    main()