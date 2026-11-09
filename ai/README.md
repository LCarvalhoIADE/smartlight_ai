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
- Meteorologia histórica da Open-Meteo obtida manualmente em JSON.
- 168 horas meteorológicas preparadas para 24–30/10/2026.
- Cruzamento local com os 142 resumos horários do no3.
- Cálculo energético horário implementado e executado para o no1.
- Processadas 5 734 leituras da sala do no1 relativas a 02/11/2026.
- Produzidos 24 resumos energéticos horários.
- Treino e avaliação dos modelos ainda pendentes.
- Aquisição meteorológica automática pela API ainda não implementada.
- 172 testes automáticos aprovados na execução de 09/11/2026.
- Aquisição do histórico SmartLight por nó e período, com autenticação
  pelo cabeçalho X-Chave e paginação.
- Validação reutilizável do histórico: estrutura, timestamps,
  duplicados, intervalos e cobertura temporal.

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
Preparar a meteorologia horária do JSON local:

```powershell
python -m ai.src.preparar_meteorologia
```

Cruzar o histórico do no3 com a meteorologia:

```powershell
python -m ai.src.cruzar_meteorologia
```

O cruzamento lê os ficheiros originais e reutiliza as funções de
preparação em memória. Não depende da execução prévia dos comandos
que exportam os CSV intermédios.

Calcular energia horária a partir da corrente medida do no1:

```powershell
python -m ai.src.calcular_energia
```

A tensão assumida e o limite entre leituras são configuráveis:

```powershell
python -m ai.src.calcular_energia --tensao 3.3 --limite-intervalo 30
```
### Adquirir um histórico do servidor

```powershell
python -m ai.src.adquirir_historico --no no1 --inicio 2026-11-01 --fim 2026-11-08
```

As datas representam dias completos em UTC, incluindo o dia final.

A chave de leitura ou administração é solicitada de forma oculta.
Opcionalmente, pode ser obtida da variável de ambiente
SMARTLIGHT_API_CHAVE. Não deve ser escrita no código ou versionada.

A autenticação utiliza o cabeçalho X-Chave, sem incluir a chave no URL.
Espaços exteriores da chave são removidos.

O script percorre as páginas, valida o conjunto e guarda o JSON
em ai/data/raw/. Preserva os metadados do nó e os valores das leituras.
Recusa substituir ficheiros existentes ou guardar em destinos
que não estejam ignorados pelo Git.

O parâmetro --destino permite escolher outro ficheiro dentro
de ai/data/raw/. O parâmetro --limite controla as leituras por página.

### Validar um histórico local

```powershell
python -m ai.src.validar_historico --origem ai/data/raw/no1_historico_2026-11-01_2026-11-08.json --no no1
```

Apresenta contagens, valores nulos, intervalos por divisão e cobertura
temporal segundo um limite provisório de 30 segundos.
O limite pode ser alterado através de --limite-intervalo.

Não modifica o ficheiro original nem cria ficheiros de saída.
A cobertura temporal não equivale à cobertura energética.

### Limitações da aquisição

A paginação utiliza OFFSET. Alterações no histórico durante a consulta
podem afetar a consistência das páginas; o cliente não garante uma
fotografia imutável da base de dados.

Se ocorrer uma falha, a aquisição é interrompida. Não existe ainda
retoma automática nem repetição automática dos pedidos.

Os módulos de aquisição e validação não consultam a Open-Meteo.
A meteorologia já preparada continua associada exclusivamente ao no3.

## Entrada e saída

Caminhos relativos à raiz do repositório:

| Entrada | Operação | Saída |
|---|---|---|
| ai/data/raw/no3_amostra.json | Preparação da amostra | ai/data/processed/no3_preparado.csv |
| ai/data/raw/no3_amostra.json | Agregação com --amostra | ai/data/processed/no3_por_hora.csv |
| ai/data/raw/leituras.tsv | Agregação do histórico do no3 | ai/data/processed/no3_historico_por_hora.csv |
| ai/data/raw/no1_historico_2026-11-02.json | Cálculo energético horário do no1 | ai/data/processed/no1_energia_2026-11-02.csv |

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
Meteorologia original:
- ai/data/raw/no3_meteo_2026-10-24_2026-10-30.json

Meteorologia horária preparada:
- ai/data/processed/no3_meteo_2026-10-24_2026-10-30_horario.csv

Histórico cruzado:
- ai/data/processed/no3_historico_com_meteorologia.csv

O cruzamento utiliza leituras.tsv e o JSON meteorológico.
Os dados diários permanecem no JSON original e ainda não são validados
nem utilizados no cruzamento.

## Limitações atuais

- A amostra é pequena e destina-se a validar o processamento.
- No histórico digital do no3, luz_pct é nulo.
- Os valores nulos são preservados, ficando vazios no CSV.
- led_pct indica a intensidade comandada ao LED, não energia medida.
- O cálculo energético atual usa corrente medida pelo INA219 do no1 e tensão assumida constante de 3,3 V.
- O resultado representa o circuito de iluminação, incluindo LED e resistência.
- A integração por trapézios assume variação linear da potência entre leituras consecutivas.
- O limite de 30 segundos é uma hipótese provisória e configurável.
- Intervalos superiores ao limite ou com corrente ausente, negativa ou não finita são excluídos e contabilizados.
- A cobertura energética corresponde aos segundos efetivamente integrados.
- Os períodos exteriores à primeira e à última leitura ficam sem estimativa.
- A média de aproximadamente 70 ms do INA219 pode produzir efeitos transitórios após alterações do PWM, segundo o responsável pelo firmware.
- As correntes medidas são preservadas, incluindo valores positivos quando led_pct é zero.
- A estimativa energética por PWM para os restantes nós está pendente de implementação.
- A integração meteorológica é local e histórica, limitada ao no3.
- A correspondência entre o JSON meteorológico e a localização do no3 é configurada manualmente; o código não verifica essa localização.
- Meteorologia histórica não representa uma previsão disponível antecipadamente. O conjunto cruzado destina-se à análise do passado.
- Os dados diários ainda não foram validados nem integrados.
- Cruzar uma hora parcial do ESP32 com meteorologia não completa as leituras em falta.
- As médias horárias não são ponderadas pelo tempo.
- Horas sem leituras não são preenchidas.
- Um resumo horário não comprova que a hora está completa.
- A proporção de leituras com presença não representa o tempo exato de ocupação.
- Os testes verificam regras do código, não a precisão dos sensores.
- Os comandos de análise e agregação processam atualmente o no3, a integração dos restantes nós está pendente.
- Intervalos superiores a 30 segundos geram alertas configuráveis, mas não confirmam perda de dados.
- A análise cobre apenas os intervalos internos dos dados disponíveis.
- O histórico do no3 abrange 24 a 30 de outubro de 2026, com dias parciais.
- luz_raw tem 2 519 valores ausentes no histórico do no3.
- hora ausente no TSV não significa ausência de timestamp.
- numero_leituras_luz_raw conta valores disponíveis, não medições fisicamente validadas.
- As regras específicas para sensores avariados, valores negativos e mudanças de unidades ainda não estão implementadas.
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

Distribuição dos 172 casos de teste:

- 27 de importação TSV.
- 16 no ficheiro de preparação, incluindo um teste de integração entre importação e preparação.
- 13 de análise de qualidade.
- 12 de agregação horária.
- 31 de preparação meteorológica.
- 15 de cruzamento meteorológico.
- 15 de cálculo energético.
- 21 de validação do histórico da API.
- 22 de aquisição do histórico.

Estas contagens incluem os casos parametrizados.

Os testes adicionais verificam seleção do nó, conversão de tipos,
NULL e células vazias, estrutura do TSV, UTF-8 com BOM,
hora opcional e contagem de luz_raw disponível.

A seleção das fontes nos comandos e a geração do CSV do histórico
foram também verificadas manualmente.
Os testes meteorológicos verificam unidades, tipos, limites,
preservação de nulos, UTC e sequência horária.

Os testes do cruzamento verificam alinhamento temporal, passagem
da meia-noite, preservação das entradas e rejeição de duplicados,
horas necessárias em falta e nós diferentes de no3.

Os testes energéticos verificam conversão de unidades, preservação
da entrada, integração por trapézios, divisão nas fronteiras horárias,
conservação da energia, configuração e fronteira do limite temporal,
exclusão de intervalos com corrente inválida, corrente zero,
leitura isolada, separação de divisões e rejeição de duplicados
e respostas com mais páginas.

## Próximas etapas

1. Ampliar o histórico energético do no1 e avaliar a cobertura por hora.
2. Validar a hipótese de integração e o limite temporal configurável.
3. Implementar e testar a estimativa por PWM dos restantes nós,
   documentando a potência de referência aplicável a cada instalação.
4. Integrar os restantes nós considerando localização, divisão,
   unidades, alterações de sensores e anomalias conhecidas.
5. Obter meteorologia para a localização e período de cada nó
   e preparar a aquisição de previsões disponíveis no instante de emissão.
6. Formalizar com o grupo a emissão às 20h locais para o dia civil seguinte,
   com resultados horários e total diário.
7. Comparar referência histórica, Regressão Linear e Random Forest
   quando existir histórico adequado, usando MAE e avaliação temporal.
8. Acordar e testar o envio, armazenamento e apresentação das previsões
   com os responsáveis pela API e pelo dashboard.