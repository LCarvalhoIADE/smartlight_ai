# Biliotecas necessárias para ler o JSON, Criar CCSV,
#trabalhar com datas e localizar ficheiros
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

#Localiza a pasta principal da componente de IA,
#Independentemente da pasta a partir da qual o programa é executado.
AI_DIR = Path(__file__).resolve().parents[1]

# Campos obrigatórios de cada leitura recebida do ESP32.
CAMPOS = (
    "no_id", "divisao", "ts", "luz_raw", "luz_pct",
    "presenca", "led_pct", "modo", "hora",
)

def preparar(dados, no_esperado="no3"):
    """Valida e ordena leituras recebidas, acrescenta a dta em UTC e organiza os registos cronologicamente sem alterar os dados originais."""

    #Confirma que os dados são uma lista e que não está vazia.
    if not isinstance(dados, list) or not dados:
        raise ValueError("Esperada uma lista não vazia de leituras.")

    # Guarda os registos validados e os identificadores já encontrados
    resultado = []
    identificadores = set()

    #Percorre cada leitura, numerando-a para identificar possíveis erros.
    for numero, leitura in enumerate(dados, start=1):

        # Cada leitura deve ser representada por um dicionário.
        if not isinstance(leitura, dict):
            raise ValueError(f"Leitura {numero}: formato inválido.")

        # Confirma que todos os campos obrigatórios estão presentes.
        if not set(CAMPOS).issubset(leitura):
            raise ValueError(f"Leitura {numero}: faltam campos.")

        # Não permite valores nulos nos camposobrigatórios.
        # A exceção é luz_pct, pois o sensor digital pode não fornecer
        # uma percentagem de luminosidade
        if any(leitura[c] is None for c in CAMPOS if c != "luz_pct"):
            raise ValueError(f"Leitura {numero}: campo obrigatório nulo.")
        
        # Confirma que a leitura pertence ao nó que estamos a analisar.
        if leitura["no_id"] != no_esperado:
            raise ValueError(f"Leitura {numero}: nó inesperado.")
        
        # A divisão deve ser um texto válido e não pode estar vazia.
        if not isinstance(leitura["divisao"], str) or not leitura["divisao"].strip():
            raise ValueError(f"Leitura {numero}: divisão inválida.")

        # O timestamp deve ser um número inteiro positivo.
        ts = leitura["ts"]
        if type(ts) is not int or ts <= 0:
            raise ValueError(f"Leitura {numero}: timestamp inválido.")

        # A presença só pode assumir dois valores:
        # 0 = ausência de presença; 1 = presença detetada.
        if type(leitura["presenca"]) not in (int, bool) or leitura["presenca"] not in (0, 1):
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
        try:
            data_utc = datetime.fromtimestamp(ts, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError) as erro:
            raise ValueError(f"Leitura {numero}: timestamp fora do intervalo.") from erro

        # Cria um novo registo para preservar os dados originais.
        # Acrescenta também o campo data_utc.
        linha = {campo: leitura[campo] for campo in CAMPOS}
        linha["data_utc"] = data_utc

        resultado.append(linha)

    # Devolve as leituras ordenadas da mais antiga para a mais recente.
    return sorted(resultado, key=lambda linha: linha["ts"])


def main():
    """
    Executa o processamento:
    lê o JSON, valida as leituras e exporta os resultados para CSV.
    """

    # Caminhos dos ficheiros de entrada e saída.
    origem = AI_DIR / "data/raw/no3_amostra.json"
    destino = AI_DIR / "data/processed/no3_preparado.csv"

    # Lê o ficheiro JSON e transforma o conteúdo em objetos Python.
    dados = json.loads(origem.read_text(encoding="utf-8-sig"))

    # Valida e organiza os registos utilizando a função preparar().
    linhas = preparar(dados)

    # Garante que a pasta de destino existe.
    destino.parent.mkdir(parents=True, exist_ok=True)

    # Cria o CSV com os campos originais e a nova data em UTC.
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