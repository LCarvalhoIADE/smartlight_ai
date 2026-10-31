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
| RF-IA-01 | Ler leituras de um ficheiro JSON local | Implementado |
| RF-IA-02 | Validar campos obrigatórios e regras de valores | Implementado parcialmente |
| RF-IA-03 | Rejeitar duplicados por no_id, divisao e ts | Implementado |
| RF-IA-04 | Ordenar leituras e acrescentar data_utc | Implementado |
| RF-IA-05 | Exportar as leituras preparadas para CSV | Implementado |
| RF-IA-06 | Sinalizar possíveis interrupções na recolha e produzir resumos por hora | Parcial: análise de intervalos implementada; resumos por hora pendentes |
| RF-IA-07 | Obter meteorologia e associá-la por localização e hora | Planeado |
| RF-IA-08 | Comparar referência do dia anterior, Regressão Linear e Random Forest | Planeado |
| RF-IA-09 | Avaliar previsões com MAE | Planeado |
| RF-IA-10 | Enviar previsões para a API do projeto | Planeado |

RF-IA-02 verifica a presença dos nove campos, os nulos obrigatórios,
o nó esperado, a divisão, o timestamp, a presença e os limites
das percentagens. Ainda não valida todos os tipos e significados
de luz_raw, modo e hora.

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

Ambos os scripts preservam o JSON original.
A validação permanece restrita ao nó no3.

Agregação horária:
- ai/src/agregar_por_hora.py
- Reutiliza a validação da função preparar.
- Agrupa por nó, divisão e hora UTC.
- Calcula contagens, proporção de presença e médias de LED e luminosidade.
- Preserva luminosidade nula quando não existem valores disponíveis.
- Produz ai/data/processed/no3_por_hora.csv.

Testes da agregação:
- ai/tests/test_agregar_por_hora.py

## 5. Modelo em V e rastreabilidade

O grupo adotou o Modelo em V. Nesta etapa, as regras da
componente são relacionadas com testes unitários.

| Requisito | Verificação | Resultado registado |
|---|---|---|
| RF-IA-01 | Execução com JSON real de 50 leituras | Execução bem-sucedida |
| RF-IA-02 | Oito casos de valores inválidos, campo em falta e lista vazia | Testes aprovados |
| RF-IA-03 | Rejeição de duplicados na preparação e na análise | Testes aprovados |
| RF-IA-04 | Ordenação e conversão para UTC | Testes aprovados |
| RF-IA-05 | Execução do script e geração do CSV | Verificação manual |
| RF-IA-06 | Resumo de qualidade, intervalos, fronteira do alerta, configuração do limite, médias horárias, separação por hora/dia/divisão e tratamento de nulos | Testes aprovados; análise de qualidade e agregação horária implementadas |
| RNF-IA-02 | Preservação da entrada nas funções preparar e analisar | Testes aprovados |

Resultado: 36 testes unitários aprovados.
- 13 de preparação dos dados.
- 13 de análise de qualidade.
- 10 de agregação

Estas contagens incluem os casos dos testes parametrizados.

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

Os testes de integração, sistema e aceitação serão definidos
à medida que as interfaces e os critérios forem acordados.

Validação manual da agregação:
- 50 leituras originaram um resumo para 2026-10-26T23:00:00+00:00.
- Intervalo entre primeira e última leitura: 742 segundos.
- Proporção de leituras com presença: 44%.
- Intensidade LED média: 44%.
- Luminosidade percentual média: sem dados.

Estes resultados descrevem a amostra, não uma hora completa.
Não foi calculado consumo energético.

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

## 8. Riscos e limitações

| Risco ou limitação | Tratamento previsto |
|---|---|
| Amostra de apenas 50 leituras | Obter um histórico maior antes de avaliar modelos |
| Falta de consumo energético válido | Aguardar medição ou estimativa calibrada e identificada |
| Falhas de recolha | Medir intervalos e sinalizar períodos incompletos |
| Mudanças de sensores | Registar datas e distinguir os períodos de recolha |
| Diferenças de fusos horários | Uniformizar instantes em UTC |
| Uso de informação futura no treino ou avaliação | Separação temporal e controlo das variáveis disponíveis |
| Interfaces ainda indefinidas | Acordar o contrato da API antes da integração |

## 9. Gestão de configuração

Repositório: https://github.com/LCarvalhoIADE/smartlight_ai
Branch de trabalho: diego.

As alterações da IA devem ficar concentradas na pasta ai/.
Alterações à configuração partilhada devem ser explicadas
e revistas antes do commit.

Dados reais, caches e credenciais não devem entrar nos commits.
Os resultados dos testes devem acompanhar as alterações de código.

## 10. Próximas etapas

1. Analisar a qualidade de um histórico maior.
2. Preparar resumos por hora e testes correspondentes.
3. Integrar meteorologia.
4. Definir o alvo energético e o horizonte de previsão.
5. Treinar e avaliar os modelos.
6. Integrar e testar com a API e o dashboard.