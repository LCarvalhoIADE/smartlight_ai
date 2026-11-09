# Engenharia de Software — Componente de IA

## 1. Objetivo e âmbito

Preparar as leituras dos nós e desenvolver previsões de consumo
energético da iluminação, combinando histórico e meteorologia.

Responsável pela IA: Diego Silva.

Esta componente inclui preparação dos dados, modelos, avaliação
e integração das previsões. Servidor, base de dados e dashboard
permanecem sob responsabilidade dos respetivos elementos do grupo.

Os identificadores deste documento são provisórios e devem ser
alinhados com os requisitos gerais do projeto.

## 2. Requisitos funcionais

| ID | Requisito | Estado |
|---|---|---|
| RF-IA-01 | Ler leituras de JSON local ou TSV com seleção do nó | Implementado |
| RF-IA-02 | Validar campos obrigatórios e regras de valores | Implementado parcialmente |
| RF-IA-03 | Rejeitar duplicados por no_id, divisao e ts | Implementado |
| RF-IA-04 | Ordenar leituras e acrescentar data_utc | Implementado |
| RF-IA-05 | Exportar as leituras preparadas para CSV | Implementado |
| RF-IA-06 | Sinalizar possíveis interrupções e produzir resumos horários | Implementado para o no3; não comprova cobertura completa |
| RF-IA-07 | Obter meteorologia e associá-la por localização e hora | Parcial: aquisição manual e cruzamento horário local do no3 implementados; automatização e restantes nós pendentes |
| RF-IA-08 | Comparar referência do dia anterior, Regressão Linear e Random Forest | Planeado |
| RF-IA-09 | Avaliar previsões com MAE | Planeado |
| RF-IA-10 | Enviar previsões para a API do projeto | Planeado |
| RF-IA-11 | Calcular energia por hora UTC e divisão a partir de corrente medida, tensão assumida e intervalos reais, registando cobertura e períodos excluídos | Implementado e verificado com dados do no1 |

RF-IA-02 exige oito campos comuns ao JSON e ao TSV.
hora é opcional; luz_raw e luz_pct podem ser nulos.

A preparação verifica o nó esperado, a divisão, o timestamp,
a presença e os limites das percentagens.

O importador TSV verifica a estrutura e converte os tipos,
rejeitando luminosidade não numérica ou não finita.
Valores negativos são preservados na importação para análise posterior.

A validação continua parcial: as regras físicas de luz_raw,
os valores permitidos de modo e a interpretação de hora ainda
não estão completamente validados.

## 3. Requisitos não funcionais

| ID | Tema | Critério |
|---|---|---|
| RNF-IA-01 | Privacidade | Não versionar dados reais, credenciais ou ambiente virtual |
| RNF-IA-02 | Integridade | Preservar o ficheiro original e não modificar a entrada da função preparar |
| RNF-IA-03 | Reprodutibilidade | Registar dependências e comandos de execução |
| RNF-IA-04 | Manutenção | Separar código, testes, dados e resultados |
| RNF-IA-05 | Testabilidade | Verificar regras de preparação com testes automáticos e dados fictícios |
| RNF-IA-06 | Avaliação | Separar treino e teste por ordem temporal, evitando informação futura |
| RNF-IA-07 | Robustez | Tratar falhas de rede e respostas inválidas nas futuras integrações |

Os critérios de desempenho, disponibilidade e MAE aceitável
ainda precisam de ser definidos e justificados.

## 4. Arquitetura atual

Entrada local:
- ai/data/raw/no3_amostra.json

Preparação:
- ai/src/preparar_dados.py
- Valida e ordena as leituras, acrescentando data_utc.
- Produz ai/data/processed/no3_preparado.csv.
- O CSV é substituído em cada execução.

Análise de qualidade:
- ai/src/analisar_qualidade.py
- Reutiliza a função preparar.
- Apresenta totais, período em UTC, nulos e intervalos por nó e divisão.
- Sinaliza intervalos superiores a 30 segundos, com limite configurável.
- Apresenta os resultados no terminal, sem gerar outro ficheiro.

Testes:
- ai/tests/test_preparar_dados.py
- ai/tests/test_analisar_qualidade.py

Agregação horária:
- ai/src/agregar_por_hora.py
- Reutiliza a validação da função preparar.
- Agrupa por nó, divisão e hora UTC.
- Calcula contagens, proporção de presença e médias de LED e luminosidade.
- Preserva luminosidade nula quando não existem valores disponíveis.
- Por defeito, produz ai/data/processed/no3_historico_por_hora.csv.
- Com --amostra, produz ai/data/processed/no3_por_hora.csv.

Testes da agregação:
- ai/tests/test_agregar_por_hora.py

Histórico local:
- ai/data/raw/leituras.tsv
- Importado por ai/src/importar_leituras.py.
- O importador permite selecionar o nó.
- Os comandos de análise e agregação selecionam atualmente no3.
- A análise e a agregação usam TSV por defeito e JSON com --amostra.
- A agregação do histórico produz:
  ai/data/processed/no3_historico_por_hora.csv.
- A agregação com --amostra mantém:
  ai/data/processed/no3_por_hora.csv.
- numero_leituras_luz_raw indica quantos valores não nulos existem
  em cada grupo, sem garantir validade física.

Testes do importador:
- ai/tests/test_importar_leituras.py

Todos os scripts preservam os ficheiros originais.
O main de preparar_dados.py continua a exportar apenas a amostra JSON.
Preparação meteorológica:
- ai/src/preparar_meteorologia.py
- Lê o JSON local obtido manualmente da Open-Meteo.
- Verifica unidades, tipos, limites e sequência horária em UTC.
- Preserva valores nulos e os timestamps da fonte.
- Produz ai/data/processed/no3_meteo_2026-10-24_2026-10-30_horario.csv.
- A execução atual verifica o período específico de 24–30/10/2026.
- Não processa a componente diária.

Cruzamento meteorológico:
- ai/src/cruzar_meteorologia.py
- Reutiliza importação, agregação e preparação meteorológica em memória.
- Utiliza as variáveis instantâneas no início da hora do resumo.
- Utiliza precipitação e radiação do timestamp seguinte, que descrevem
  a hora anterior da fonte.
- Regista meteo_instante_utc e meteo_fim_intervalo_utc para rastreabilidade.
- Rejeita horas necessárias em falta, duplicados e nós diferentes de no3.
- Preserva resumos parciais e valores nulos.
- Produz ai/data/processed/no3_historico_com_meteorologia.csv.

Testes:
- ai/tests/test_preparar_meteorologia.py
- ai/tests/test_cruzar_meteorologia.py

Os módulos meteorológicos não fazem pedidos de rede.
A associação da localização ao no3 é manual.

Cálculo energético horário

- Módulo `ai/src/calcular_energia.py`.
- Testes em `ai/tests/test_calcular_energia.py`.
- Entrada local `ai/data/raw/no1_historico_2026-11-02.json`.
- Saída local `ai/data/processed/no1_energia_2026-11-02.csv`.
- Calcula potência em mW multiplicando corrente em mA pela tensão em V.
- Integra a potência pelo método dos trapézios.
- Divide os intervalos nas fronteiras horárias UTC, interpolando
  a potência nas extremidades de cada segmento.
- Exporta energia em mWh e Wh, segundos integrados e excluídos,
  proporção de cobertura, tensão assumida e limite utilizado.
- Preserva o ficheiro de entrada e os valores de corrente.
- Substitui o CSV de saída em cada execução.

## 5. Modelo em V e rastreabilidade

O grupo adotou o Modelo em V. Nesta etapa, as regras da componente
são relacionadas com testes unitários, um teste de integração local
e verificações manuais com dados reais.

| Requisito | Verificação | Resultado registado |
|---|---|---|
| RF-IA-01 | Testes de importação TSV e execução com JSON e histórico real do no3 | Testes e execuções aprovados |
| RF-IA-02 | Oito casos de valores inválidos, campo em falta e lista vazia | Testes aprovados |
| RF-IA-03 | Rejeição de duplicados na preparação e na análise | Testes aprovados |
| RF-IA-04 | Ordenação e conversão para UTC | Testes aprovados |
| RF-IA-05 | Execução do script e geração do CSV | Verificação manual |
| RF-IA-06 | Resumo de qualidade, intervalos, fronteira do alerta, configuração do limite, médias horárias, separação por hora/dia/divisão e tratamento de nulos | Testes aprovados; análise de qualidade e agregação horária implementadas |
| RF-IA-07 | Validação meteorológica, alinhamento temporal, passagem de dia, preservação de nulos e rejeição de horas em falta | 46 casos automáticos aprovados e execução local com dados reais |
| RF-IA-11 | 15 testes energéticos e execução com 5 734 leituras reais do no1 | Testes aprovados e CSV horário gerado |
| RNF-IA-02 | Preservação da entrada nas funções preparar e analisar | Testes aprovados |

Resultado: 129 testes automáticos aprovados.

- 27 de importação TSV.
- 16 no ficheiro de preparação.
- 13 de análise de qualidade.
- 12 de agregação horária.
- 31 de preparação meteorológica.
- 15 de cruzamento meteorológico.
- 15 de cálculo energético.

As contagens incluem os casos parametrizados.
Um dos testes de preparação verifica a integração entre importar_tsv
e preparar. Os restantes verificam comportamentos das funções.

Comando executado na raiz do repositório:

```powershell
python -m pytest ai/tests -v
```

Validação manual da análise de qualidade:
- 50 leituras do nó no3, divisão sala.
- Período: 2026-10-26T23:18:09+00:00 a 2026-10-26T23:30:31+00:00.
- Intervalos entre leituras: 15–16 segundos.
- 50 valores nulos em luz_pct, esperados com o sensor digital.
- Zero intervalos superiores a 30 segundos.

A ausência de alertas aplica-se apenas à amostra analisada.
Não demonstra que todo o histórico do servidor está completo.

Os testes não verificam ainda a integração com APIs,
a precisão física dos sensores ou a qualidade das previsões.

Existe um teste de integração local entre importação e preparação.
Os testes das interfaces externas, de sistema e de aceitação
serão definidos quando os contratos e critérios forem acordados.

Validação manual da agregação:
- 50 leituras originaram um resumo para 2026-10-26T23:00:00+00:00.
- Intervalo entre primeira e última leitura: 742 segundos.
- Proporção de leituras com presença: 44%.
- Intensidade LED média: 44%.
- Luminosidade percentual média: sem dados.

Estes resultados descrevem a amostra de 50 leituras do no3,
não uma hora completa. Nesta validação histórica do no3,
não foi calculado consumo energético.

O cálculo energético posterior do no1 está documentado
na verificação de 08/11/2026.

### Validação manual do histórico do no3 em 01/11/2026:

- 33 190 leituras importadas e preparadas.
- Início UTC: 2026-10-24T14:48:44+00:00.
- Fim UTC: 2026-10-30T11:10:17+00:00.
- 2 519 valores nulos em luz_raw.
- 33 190 valores nulos em luz_pct.
- hora nula nas 33 190 leituras porque não existe no TSV.
- Quatro intervalos superiores a 30 segundos:
  226, 31, 93 e 47 segundos, por ordem cronológica.
- 142 resumos horários produzidos.
- 30 671 leituras com luz_raw disponível.
- CSV do histórico confirmado como ignorado pelo Git.
- Análise da amostra JSON também executada com sucesso.

Os 142 resumos representam horas com alguma leitura.
Não representam 142 horas completas nem cobertura contínua.
Validação manual da meteorologia e do cruzamento em 01/11/2026:

- JSON meteorológico em GMT, com desvio UTC de zero segundos.
- 168 horas entre 2026-10-24T00:00:00+00:00
  e 2026-10-30T23:00:00+00:00.
- Dez variáveis horárias, sem valores nulos nesta resposta.
- 142 resumos do ESP32 originaram 142 linhas cruzadas.
- Primeira hora cruzada: 2026-10-24T14:00:00+00:00.
- Última hora cruzada: 2026-10-30T11:00:00+00:00.
- CSV meteorológico e CSV cruzado confirmados como ignorados pelo Git.
- Suite completa: 114 testes aprovados.

Esta execução não valida a precisão física da meteorologia,
a qualidade de previsões energéticas ou uma integração automática
com serviços externos.

No dia 27/10/2026, o nó `no3` apresentou intervalos de 15, 16 e 20 segundos durante a hora iniciada às 18h UTC.

Nas duas horas seguintes, foram registadas 180 leituras por hora, com intervalos internos de 20 a 21 segundos.

Por este motivo, uma contagem inferior à mediana de 238 leituras por hora, por si só, é insuficiente para classificar uma hora como incompleta.

Os resumos horários foram mantidos. A causa da alteração da frequência de recolha continua por confirmar.
### Verificação energética em 08/11/2026

Foi processado o histórico da sala do no1 de 02/11/2026.

- 5 734 leituras recebidas, com mais=false na primeira página da consulta.
- Zero duplicados por nó, divisão e timestamp.
- Zero correntes ausentes ou negativas.
- Intervalos entre leituras de 15 a 16 segundos.
- Primeira leitura em 2026-11-02T00:00:14+00:00.
- Última leitura em 2026-11-02T23:59:59+00:00.
- Tensão assumida de 3,3 V.
- Limite configurado de 30 segundos.
- 24 resumos horários.
- 86 385 segundos integrados.
- Zero segundos excluídos entre as leituras.
- 15 segundos exteriores ao período observado.
- Energia calculada de aproximadamente 12,151608 mWh,
  equivalente a 0,012151608 Wh.
- 15 testes do módulo aprovados.
- Suite completa com 129 testes aprovados.

A execução verifica o processamento do histórico disponível.
A precisão física depende do INA219, da tensão assumida e das
hipóteses da integração.

Segundo Luís, o firmware ajusta o PWM, regista led_pct e lê
a corrente no mesmo ciclo. A média de aproximadamente 70 ms
do INA219 pode introduzir efeitos transitórios após mudanças
do PWM. As medições foram preservadas no cálculo.

### Comparação preliminar com o T20

O resultado de aproximadamente 12,0 mWh referido para o T20
do Luís difere dos 12,151608 mWh calculados pelo módulo Python.
Tomando 12,0 mWh como referência, a diferença é aproximadamente
0,151608 mWh, ou 1,26%.

Esta comparação é provisória: é necessário confirmar se ambos
os resultados utilizam o mesmo período, divisão e conjunto de leituras.

O módulo Python utiliza corrente medida, tensão assumida de 3,3 V,
intervalos reais entre timestamps e integração pelo método dos
trapézios. Preserva também correntes positivas quando led_pct é zero.

As possíveis diferenças de metodologia a verificar incluem:
- Corrente medida ou estimativa baseada no PWM.
- Intervalos reais ou duração fixa por leitura.
- Método de integração.
- Tratamento das correntes com o LED comandado para zero.
- Limites temporais e arredondamentos.

Sem consultar o cálculo do T20, não é possível atribuir a diferença
a uma causa específica nem concluir qual resultado é mais preciso.

## 6. Decisões técnicas

- Usar ficheiros locais enquanto a integração definitiva não existe.
- Manter os dados reais fora do Git.
- Usar dados fictícios nos testes.
- Preservar luz_pct nulo; ausência de medição não equivale a zero.
- Acrescentar UTC para permitir cruzamento temporal entre fontes.
- Não interpretar led_pct como energia medida.
- Aguardar consumo válido antes do treino preditivo.
- Comparar modelos com uma referência simples.
- Usar apenas informação disponível no momento da previsão.
- Preservar luz_raw nulo e distinguir ausência de coluna de ausência de valor.
- Manter hora opcional e calcular data_utc a partir de ts.
- Separar os CSV da amostra e do histórico.
- Validar primeiro o no3 e depois integrar os restantes nós.
- Documentar anomalias sem assumir que as respetivas regras de tratamento já estão implementadas.
- Manter separados os timestamps originais da meteorologia e a hora
  do resumo do ESP32.
- Para o intervalo [10:00, 11:00), utilizar variáveis instantâneas
  das 10:00 e precipitação/radiação com timestamp das 11:00.
- Usar o conjunto cruzado atual para análise histórica.
- Na futura avaliação preditiva, utilizar apenas informação
  disponível no instante de emissão da previsão.
- Não interpretar radiação exterior em W/m² como luminosidade
  interior em lux nem como consumo elétrico.

## 7. Dependências e responsabilidades

| Responsável | Informação ou entrega necessária |
|---|---|
| Luís — servidor | Consulta de histórico por nó e período, autenticação e significado dos horários |
| Ricardo — base de dados | Estrutura e unidades dos dados energéticos e das previsões |
| Grupo — hardware | Medições ou estimativas calibradas de consumo e registo das mudanças de sensores |
| Francisco — dashboard | Horizonte das previsões e dados necessários para apresentação |
| Diego — IA | Preparação, modelos, avaliação, testes e formato proposto dos resultados |

O acesso da IA aos dados poderá ser feito pela API,
sem ligação direta ao MySQL.

O endpoint de envio das previsões, a autenticação e o formato
do JSON ainda serão acordados com os responsáveis.
Luís já disponibilizou uma exportação TSV com 118 492 registos.
Esta entrega permite trabalhar localmente, mas não comprova que
a BD definitiva ou a API de previsões estejam concluídas.

Continuam pendentes:
- Localizações aproximadas dos restantes nós e registo de eventuais mudanças de localização; a localização do no3 já foi usada no pedido.
- Sensor, unidade e significado de luz_raw por período.
- Fórmula de luz_pct.
- Confirmação da transição de sensor do no1.
- Explicação da luminosidade idêntica nas duas divisões do no2.
- Período exato de funcionamento incorreto do PIR do no2.
- Estrutura e unidades do futuro alvo energético.

## 8. Riscos e limitações

| Risco ou limitação | Tratamento previsto |
|---|---|
| Histórico curto e heterogéneo | Continuar a recolha e distinguir nós, sensores e períodos antes de avaliar modelos |
| Disponibilidade e precisão dos dados energéticos | Ampliar o histórico do no1, documentar a tensão assumida e validar as estimativas dos restantes nós |
| Falhas de recolha | Medir intervalos e sinalizar períodos incompletos |
| Mudanças de sensores | Registar datas e distinguir os períodos de recolha |
| Diferenças de fusos horários | Uniformizar instantes em UTC |
| Uso de informação futura no treino ou avaliação | Separação temporal e controlo das variáveis disponíveis |
| Interfaces ainda indefinidas | Acordar o contrato da API antes da integração |

Informações fornecidas pelo Luís para interpretação do histórico:

- Valores negativos de luminosidade indicam leituras inválidas.
- no1 mudou de luminosidade digital para lux em 24/10, aproximadamente
  à hora de almoço; o instante exato carece de confirmação.
- O PIR da sala do no2 mantinha a presença praticamente constante.
- no2 esteve parado entre 23 e 24/10 e deixou de recolher em 27/10.
- no1 esteve desligado em 29/10, aproximadamente entre 01:39 e 07:51.

Estas informações orientam a análise. O tratamento automático de todas
estas situações ainda não está implementado.

Ocorrência observada em 27/10/2026

Segundo o responsável pelo servidor, uma manutenção deixou a plataforma
indisponível entre as 18h33 e depois das 20h00. O fuso horário deste
relato ficou por confirmar. Os nós no1 e no3 guardaram as leituras em
memória e enviaram-nas após a reposição do serviço. O responsável
confirmou a continuidade dos registos na base de dados para ambos os nós.
O no2 estava desligado e ficou fora desta verificação.

No histórico do no3, as horas iniciadas às 19h e às 20h UTC contêm
180 leituras cada, com intervalos internos de 20 a 21 segundos.
Ambas foram mantidas na análise. A causa desta cadência ficou por confirmar.

A fila em RAM tem capacidade para 5 760 leituras, o equivalente a
24 horas à cadência de 15 segundos. Um reinício ou corte de alimentação
apaga as leituras que ainda aguardam envio.

## 9. Gestão de configuração

Repositório: https://github.com/LCarvalhoIADE/smartlight_ai
Branch de trabalho: diego.

As alterações da IA devem ficar concentradas na pasta ai/.
Alterações à configuração partilhada devem ser explicadas
e revistas antes do commit.

Dados reais, caches e credenciais não devem entrar nos commits.
Os resultados dos testes devem acompanhar as alterações de código.

## 10. Próximas etapas

1. Ampliar o histórico energético do no1 e avaliar a cobertura por hora.
2. Validar a hipótese de integração e o limite temporal configurável.
3. Implementar e testar a estimativa por PWM dos restantes nós, documentando a potência de referência aplicável a cada instalação.
4. Integrar os restantes nós considerando localização, divisão, unidades, alterações de sensores e anomalias conhecidas.
5. Obter meteorologia para a localização e período de cada nó e preparar a aquisição de previsões disponíveis no instante de emissão.
6. Formalizar com o grupo a emissão às 20h locais para o dia civil seguinte, com resultados horários e total diário.
7. Comparar referência histórica, Regressão Linear e Random Forest quando existir histórico adequado, usando MAE e avaliação temporal.
8. Acordar e testar o envio, armazenamento e apresentação das previsões com os responsáveis pela API e pelo dashboard.