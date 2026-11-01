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
- Amostra JSON de 50 leituras do no3 preservada.
- Exportação TSV recebida com 118 492 registos de no1, no2 e no3.
- Pipeline atual aplicado às 33 190 leituras do no3.
- Importação TSV com seleção do nó e conversão dos tipos.
- Preparação compatível com hora ausente e luminosidade nula.
- Análise de nulos, intervalos e possíveis interrupções.
- Agregação por hora UTC e divisão: 142 resumos do histórico do no3.
- 68 testes automáticos aprovados.
- Sem cálculo de consumo, treino de modelos ou integração meteorológica.

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

Executar na raiz do repositório, com ai/.venv ativo.
Os ficheiros de dados reais devem existir localmente.

Importar o histórico do no3 e mostrar as contagens:

```powershell
python -m ai.src.importar_leituras
```

Preparar a amostra JSON e gerar o CSV de leituras:

```powershell
python ai/src/preparar_dados.py
```

Analisar o histórico TSV:

```powershell
python -m ai.src.analisar_qualidade
```

Analisar a amostra JSON:

```powershell
python -m ai.src.analisar_qualidade --amostra
```

Gerar os resumos horários do histórico TSV:

```powershell
python -m ai.src.agregar_por_hora
```

Gerar os resumos horários da amostra JSON:

```powershell
python -m ai.src.agregar_por_hora --amostra
```

Acrescentar --detalhes ao comando de agregação para apresentar
cada resumo horário no terminal.

Executar todos os testes:

```powershell
python -m pytest ai/tests -q
```

## Entrada e saída

Caminhos relativos à raiz do repositório:

| Entrada | Operação | Saída |
|---|---|---|
| ai/data/raw/no3_amostra.json | Preparação da amostra | ai/data/processed/no3_preparado.csv |
| ai/data/raw/no3_amostra.json | Agregação com --amostra | ai/data/processed/no3_por_hora.csv |
| ai/data/raw/leituras.tsv | Agregação do histórico do no3 | ai/data/processed/no3_historico_por_hora.csv |

A importação e a análise de qualidade apresentam resultados no
terminal, sem criar ficheiros.

A função preparar valida algumas regras dos dados, rejeita duplicados
por (no_id, divisao, ts), ordena as leituras e acrescenta data_utc.
É reutilizada pela análise e pela agregação.

Os originais são preservados. Cada CSV é substituído quando se executa
a operação correspondente. A saída do histórico é separada da amostra.

O campo hora é opcional. Quando não existe na entrada, fica None.
O instante UTC é sempre calculado a partir de ts.

NULL e células vazias nos campos de luminosidade do TSV são convertidos
para None. No CSV, None é representado por uma célula vazia.

## Limitações atuais

- A amostra é pequena e destina-se a validar o processamento.
- luz_pct é nulo porque o sensor atual é digital.
- Os valores nulos são preservados, ficando vazios no CSV.
- led_pct indica a intensidade comandada ao LED, não energia medida.
- Os dados atualmente processados não contêm medições energéticas.
- Ainda não existe integração meteorológica.
- As médias horárias não são ponderadas pelo tempo.
- Horas sem leituras não são preenchidas.
- Um resumo horário não comprova que a hora está completa.
- A proporção de leituras com presença não representa o tempo exato de ocupação.
- Os testes verificam regras do código, não a precisão dos sensores.
- Os comandos de análise e agregação processam atualmente o no3, a integração dos restantes nós está pendente.
- Intervalos superiores a 30 segundos geram alertas configuráveis,
  mas não confirmam perda de dados.
- A análise cobre apenas os intervalos internos dos dados disponíveis.
- O histórico do no3 abrange 24 a 30 de outubro de 2026, com dias parciais.
- luz_raw tem 2 519 valores ausentes no histórico do no3.
- hora ausente no TSV não significa ausência de timestamp.
- numero_leituras_luz_raw conta valores disponíveis, não medições
  fisicamente validadas.
- As regras específicas para sensores avariados, valores negativos
  e mudanças de unidades ainda não estão implementadas.
- Não se devem misturar luminosidade digital, valores analógicos e lux.

## Implementação e testes

O projeto segue o Modelo em V.

Nesta componente, os testes automáticos verificam:
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

Distribuição dos 68 casos de teste:

- 27 de importação TSV.
- 16 no ficheiro de preparação, incluindo um teste de integração
  entre importação e preparação.
- 13 de análise de qualidade.
- 12 de agregação horária.

Estas contagens incluem os casos parametrizados.

Os testes adicionais verificam seleção do nó, conversão de tipos,
NULL e células vazias, estrutura do TSV, UTF-8 com BOM,
hora opcional e contagem de luz_raw disponível.

A seleção das fontes nos comandos e a geração do CSV do histórico
foram também verificadas manualmente.

## Próximas etapas

1. Recolher e validar meteorologia para a localização e período do no3.
2. Cruzar meteorologia e resumos horários, respeitando os intervalos
   temporais representados por cada variável.
3. Confirmar localizações, unidades, mudanças de sensores e anomalias
   antes de integrar os restantes nós.
4. Continuar a recolha e definir o alvo energético e o horizonte.
5. Treinar e comparar os modelos quando existir consumo válido.
6. Integrar as previsões com a API e o dashboard.

Os endpoints, a autenticação e o formato de envio das previsões
ainda serão acordados com os responsáveis.