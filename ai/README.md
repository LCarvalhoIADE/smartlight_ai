# Componente de IA — SmartLight AI

## Objetivo

Prever o consumo energético da iluminação a partir do histórico
dos nós e de dados meteorológicos da Open-Meteo.

Está prevista a comparação de:
- Referência simples: consumo da mesma hora do dia anterior.
- Regressão Linear.
- Random Forest.

A avaliação será feita com MAE (Erro Médio Absoluto),
respeitando a ordem temporal dos dados de treino e teste.

## Estado atual

- Ambiente Python e dependências configurados.
- Amostra local de 50 leituras reais do nó no3.
- Validação e preparação dos dados implementadas.
- CSV gerado com as leituras ordenadas cronologicamente.
- Análise de nulos, intervalos e possíveis interrupções implementada.
- 36 testes automáticos aprovados: 13 de preparação, 13 de qualidade e 10 de agregação.
- Agregação por hora UTC e divisão implementada.
- Sem cálculo de consumo ou treino de modelos nesta etapa.
## Organização

- data/raw/: dados originais, apenas locais.
- data/processed/: dados preparados, apenas locais.
- src/: scripts Python.
- tests/: testes automáticos com dados fictícios.
- outputs/: futuros resultados, métricas e gráficos.
- requirements.txt: dependências do ambiente.

Os dados reais, credenciais e o ambiente virtual não devem
ser publicados no Git.

## Executar

Executar os comandos na raiz do repositório,
com o ambiente virtual ai/.venv ativo.

Preparar a amostra e gerar o CSV:

```powershell
python ai/src/preparar_dados.py
```

Executar todos os testes da IA:

```powershell
python -m pytest ai/tests/test_preparar_dados.py -v
```

Gerar os resumos por hora:

```powershell
python -m ai.src.agregar_por_hora
```

## Entrada e saída

Entrada local:
data/raw/no3_amostra.json

Saída da preparação:
ai/data/processed/no3_preparado.csv

O script de preparação preserva o JSON original, valida os campos
obrigatórios e algumas regras de valores, rejeita duplicados pelo
conjunto (no_id, divisao, ts), ordena as leituras e acrescenta data_utc.

O CSV de saída é substituído em cada execução.

A análise de qualidade lê o JSON original e apresenta
o resumo no terminal, sem criar outro ficheiro.

Saída da agregação:
ai/data/processed/no3_por_hora.csv

O CSV horário é substituído em cada execução.
As médias representam apenas as leituras disponíveis.

## Limitações atuais

- A amostra é pequena e destina-se a validar o processamento.
- luz_pct é nulo porque o sensor atual é digital.
- Os valores nulos são preservados, ficando vazios no CSV.
- led_pct indica a intensidade comandada ao LED, não energia medida.
- Ainda não existem medições energéticas nesta amostra.
- Ainda não existe integração meteorológica.
- As médias horárias não são ponderadas pelo tempo.
- Horas sem leituras não são preenchidas.
- Um resumo horário não comprova que a hora está completa.
- A proporção de leituras com presença não representa o tempo exato de ocupação.
- Os testes verificam regras do código, não a precisão dos sensores.
- A validação está atualmente restrita ao nó no3.
- Intervalos superiores a 30 segundos geram alertas configuráveis,
  mas não confirmam perda de dados.
- A análise cobre apenas os intervalos internos da amostra.

## Implementação e testes

O projeto segue o Modelo em V.

Nesta componente, os testes unitários verificam:
- Preservação dos dados originais e de luz_pct nulo.
- Conversão do timestamp para UTC.
- Ordenação cronológica.
- Rejeição de duplicados.
- Rejeição de determinados valores inválidos.
- Rejeição de campos em falta e de uma lista vazia.
- Resumo de qualidade e contagem de nulos.
- Separação dos intervalos por divisão.
- Tratamento de grupos com uma única leitura.
- Fronteira dos alertas: 30 segundos sem alerta e 31 com alerta.
- Configuração do limite e rejeição de limites inválidos.
- Preservação da entrada durante a análise.

## Próximas etapas

1. Obter e analisar um histórico maior de leituras.
2. Identificar falhas de recolha e preparar resumos por hora.
3. Integrar meteorologia por localização e instante.
4. Definir e validar o consumo usado como alvo da previsão.
5. Treinar e comparar os modelos.
6. Integrar as previsões com a API e o dashboard.

Os endpoints e o formato de envio das previsões serão
combinados com os responsáveis pelo servidor, BD e dashboard.