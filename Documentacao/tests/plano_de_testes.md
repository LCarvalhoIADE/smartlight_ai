# Plano de Testes — SmartLight AI

**Projeto:** SmartLight AI  
**Grupo:** g04  
**Responsável pela componente de QA:** Ricardo Siqueira  
**Versão do documento:** 1.0  
**Estado:** Plano proposto — em andamento

---

## 1. Introdução

Este documento define a estratégia, o âmbito, os procedimentos e os critérios de aceitação dos testes a realizar no projeto SmartLight AI.

O objetivo é verificar se as diferentes componentes do sistema cumprem os requisitos funcionais e não funcionais definidos pela equipa, identificar defeitos e garantir a integridade dos dados durante o funcionamento normal e perante situações de falha.

Os testes abrangem o firmware dos nós ESP32, a comunicação com o servidor, a API REST, a base de dados MySQL, o dashboard e a integração com a componente de Inteligência Artificial.

A execução será progressiva, acompanhando a disponibilidade das diferentes componentes do projeto.

## 2. Objetivos dos testes

Os testes têm os seguintes objetivos:

- Verificar se os nós ESP32 detetam corretamente a presença e a luminosidade.
- Confirmar que o controlo da iluminação funciona localmente, sem depender da ligação à Internet.
- Verificar a comunicação entre os nós e o servidor através de HTTPS.
- Confirmar que a API autentica os nós e valida os dados recebidos.
- Garantir que leituras repetidas não originam registos duplicados.
- Verificar a integridade e a consistência dos dados armazenados.
- Confirmar que as leituras recolhidas durante uma interrupção da rede são enviadas posteriormente.
- Verificar que o dashboard apresenta corretamente os dados disponibilizados pela API.
- Identificar comportamentos inesperados, erros e vulnerabilidades.
- Documentar os resultados e acompanhar a correção dos defeitos identificados.

## 3. Âmbito

### 3.1. Componentes incluídas

**Firmware ESP32**
- Leitura dos sensores de presença e luminosidade.
- Controlo automático do LED através de PWM.
- Registo periódico das leituras.
- Sincronização da hora através de NTP.
- Ligação e reconexão ao Wi-Fi.
- Armazenamento temporário de leituras em memória.
- Reenvio de leituras após recuperação da ligação.

**API e servidor**
- Receção de leituras através de pedidos HTTP POST.
- Consulta das últimas leituras através de pedidos HTTP GET.
- Autenticação através do cabeçalho X-Token.
- Validação dos campos e dos valores recebidos.
- Tratamento de pedidos inválidos.
- Prevenção de duplicados.

**Base de dados**
- Armazenamento das informações dos nós.
- Armazenamento das leituras.
- Integridade das chaves e relações.
- Prevenção de registos duplicados.

**Dashboard**
- Consulta dos dados através da API.
- Apresentação do estado dos nós e das divisões.
- Apresentação do histórico de leituras.
- Adaptação a diferentes dimensões de ecrã.
- Autenticação e controlo de acesso.

**Inteligência Artificial**
- Preparação e validação dos dados.
- Agregação temporal.
- Integração dos dados meteorológicos.
- Comparação futura dos modelos de previsão.

## 4. Estratégia de testes

Será adotada uma abordagem progressiva, organizada em diferentes níveis.

### 4.1. Testes unitários

Os testes unitários são desenvolvidos e executados pelos responsáveis de cada componente. A componente de QA acompanha os resultados e complementa-os com testes de integração e de sistema.

### 4.2. Testes de integração

Verificam a comunicação entre componentes.

### 4.3. Testes de sistema

Verificam o comportamento do sistema completo.

### 4.4. Testes funcionais

Verificam se as funcionalidades apresentam o comportamento esperado perante entradas válidas e inválidas.

### 4.5. Testes não funcionais

Verificam características como:
- Segurança.
- Fiabilidade.
- Desempenho.
- Usabilidade.
- Compatibilidade.

### 4.6. Técnicas e ferramentas

- **Postman:** execução e automatização de testes à API REST.
- **Jira:** organização de tarefas, registo de defeitos e acompanhamento da sua resolução.
- **GitHub:** armazenamento do plano, da coleção Postman e dos resultados documentados.
- **Docker:** disponibilização do ambiente de servidor e base de dados.
- **MySQL:** verificação dos registos armazenados.
- **Navegador Web:** testes funcionais e de compatibilidade do dashboard.

## 5. Ambiente de testes

Os testes deverão ser realizados num ambiente de desenvolvimento, separado do ambiente de produção.

### 5.1. Dados de teste

Serão utilizados:
- Tokens específicos para testes.
- Identificadores de nós de teste.
- Leituras fictícias para testar a API.
- Valores válidos e inválidos de luminosidade, presença e intensidade do LED.
- Timestamps controlados.
- Leituras repetidas para verificar a idempotência.

## 6. Critérios de entrada

Um conjunto de testes poderá começar quando:

- A componente a testar estiver disponível.
- Existir uma versão identificável do código.
- O ambiente de testes estiver configurado.
- Existirem dados e credenciais próprios para testes.
- Os comportamentos esperados estiverem documentados.
- Os responsáveis pela componente tiverem disponibilizado a informação necessária.

Se algum destes requisitos não estiver cumprido, o teste será marcado como bloqueado ou pendente, sem ser considerado aprovado ou reprovado.

## 7. Critérios de saída

Uma fase de testes poderá ser considerada concluída quando:

- Todos os testes planeados para essa fase tiverem sido executados ou justificados como bloqueados.
- Os resultados estiverem registados.
- Os defeitos identificados estiverem documentados.
- Os defeitos críticos e graves tiverem sido corrigidos ou formalmente aceites pela equipa.
- Os testes associados às correções tiverem sido repetidos.
- Os resultados e limitações estiverem documentados.

## 8. Priorização e gravidade

### 8.1. Prioridade de execução

- **Alta:** testes relacionados com autenticação, integridade dos dados, controlo local e comunicação.
- **Média:** testes relacionados com consulta, apresentação e funcionalidades secundárias.
- **Baixa:** testes de conveniência, aspetos visuais secundários e melhorias não essenciais.

### 8.2. Gravidade dos defeitos

- **Crítica:** compromete a segurança do sistema, permite acesso não autorizado relevante ou provoca perda generalizada de dados.
- **Alta:** impede uma funcionalidade essencial, provoca perda de leituras ou compromete a integridade dos dados.
- **Média:** afeta parcialmente uma funcionalidade, sem comprometer o funcionamento global.
- **Baixa:** problema visual, textual ou de baixo impacto funcional.

A prioridade indica a urgência de execução ou resolução. A gravidade representa o impacto do problema encontrado.

## 9. Casos de teste

### 9.1. API — Autenticação e acesso

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| API-AUTH-01 | Token válido | Enviar POST com token válido e dados válidos | Pedido aceite com HTTP 200 | Alta |
| API-AUTH-02 | Token inválido | Enviar POST com token incorreto | HTTP 401 | Alta |
| API-AUTH-03 | Token ausente | Enviar POST sem Token | Pedido rejeitado | Alta |
| API-AUTH-04 | Consulta administrativa | Consultar GET com chave administrativa válida | Leituras de todos os nós autorizados | Alta |

### 9.2. API — Validação dos pedidos

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| API-VAL-01 | JSON válido | Enviar uma leitura com estrutura válida | HTTP 200 | Alta |
| API-VAL-02 | JSON inválido | Enviar conteúdo que não seja JSON válido | HTTP 400 | Alta |
| API-VAL-03 | Corpo vazio | Enviar POST sem conteúdo | Pedido rejeitado | Alta |
| API-VAL-04 | Campo obrigatório ausente | Remover um campo obrigatório | HTTP 422 | Alta |
| API-VAL-05 | Valor fora dos limites | Enviar um valor superior ao limite permitido | HTTP 422 | Alta |
| API-VAL-06 | Tipo de dado incorreto | Enviar texto num campo numérico | Pedido rejeitado conforme validação definida | Alta |
| API-VAL-07 | Identificador desconhecido | Enviar leitura de um nó não registado | Pedido rejeitado | Alta |

### 9.3. API — Integridade e duplicação

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| API-DAT-01 | Primeira leitura | Enviar uma leitura inédita | Registo criado | Alta |
| API-DAT-02 | Leitura repetida | Reenviar exatamente a mesma leitura | HTTP 200 sem novo registo | Alta |
| API-DAT-03 | Sequência diferente | Enviar duas leituras do mesmo nó com seq diferente | Ambas armazenadas | Alta |
| API-DAT-04 | Timestamp UTC | Enviar timestamp conhecido e consultar o registo | Instante preservado em UTC | Alta |
| API-DAT-05 | Dados opcionais nulos | Enviar leitura sem informação de luminosidade percentual | Valor opcional preservado como ausente ou NULL | Média |

### 9.4. Firmware — Sensores e controlo local

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| ESP-SEC-01 | Deteção de presença | Gerar movimento perante o PIR | Presença identificada | Alta |
| ESP-SEC-02 | Ausência de movimento | Não gerar movimento durante o período definido | Presença passa a falsa após o timeout | Alta |
| ESP-SEC-03 | Sensor digital em ambiente claro | Colocar sensor na condição clara | Leitura raw igual a 0 | Alta |
| ESP-SEC-04 | Sensor digital em ambiente escuro | Colocar sensor na condição escura | Leitura raw igual a 1 | Alta |
| ESP-SEC-05 | Presença e ambiente claro | Simular presença e sensor claro | LED desligado | Alta |
| ESP-SEC-06 | Presença e ambiente escuro | Simular presença e sensor escuro | LED com intensidade máxima | Alta |
| ESP-SEC-07 | Ausência de presença | Aguardar o fim do timeout | LED desligado | Alta |
| ESP-SEC-08 | Funcionamento local | Desligar Wi-Fi e repetir os testes de iluminação | Controlo local mantém-se funcional | Alta |

### 9.5. Firmware — Comunicação e fila offline

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| ESP-CEF-01 | Ligação Wi-Fi | Iniciar o nó com rede disponível | Ligação estabelecida | Alta |
| ESP-CEF-02 | Wi-Fi indisponível | Iniciar o nó sem rede disponível | Nó continua a controlar a iluminação localmente | Alta |
| ESP-CEF-03 | Recuperação de Wi-Fi | Restabelecer a rede após interrupção | Nó tenta estabelecer novamente a ligação | Alta |
| ESP-CEF-04 | Envio HTTPS | Enviar leitura para o servidor | Pedido enviado através de HTTPS | Alta |
| ESP-CEF-05 | Recolha offline | Desligar a rede e aguardar novos ciclos | Leituras ficam temporariamente guardadas em RAM | Alta |
| ESP-CEF-06 | Recuperação da rede | Restabelecer Wi-Fi e verificar a fila | Leituras pendentes são enviadas | Alta |
| ESP-CEF-07 | Ordem de envio | Acumular várias leituras offline | Leituras enviadas pela ordem de recolha | Média |
| ESP-CEF-08 | Servidor indisponível | Manter Wi-Fi ativo e desligar temporariamente o servidor | Leituras permanecem na fila e são tentadas novamente | Alta |
| ESP-CEF-09 | Fila cheia | Simular acumulação superior à capacidade disponível | Leitura mais antiga descartada e contador de perdas incrementado | Média |
| ESP-CEF-10 | Reinício durante falha de rede | Acumular leituras offline e reiniciar o ESP32 | Leituras anteriormente guardadas perdem-se, conforme implementação atual | Média |

### 9.6. Segurança e infraestrutura

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| SEC-01 | Comunicação cifrada | Inspecionar a ligação entre ESP32 e servidor | Comunicação efetuada por HTTPS | Alta |
| SEC-02 | Certificado TLS | Verificar a validação do certificado pelo cliente | Certificado e identidade do servidor validados | Alta |
| SEC-03 | Segredos no repositório | Inspecionar os ficheiros e histórico Git | Nenhum token ou credencial real publicado | Alta |
| SEC-04 | Acesso direto à BD | Tentar ligação externa à porta MySQL | Ligação recusada | Alta |
| SEC-05 | Credenciais inválidas da BD | Configurar credenciais incorretas num ambiente de teste | Aplicação não consegue aceder à BD e não divulga credenciais | Alta |
| SEC-06 | Acesso não autorizado à API | Efetuar pedidos sem autenticação ou com token inválido | Acesso rejeitado | Alta |
| SEC-07 | Exposição de erros | Provocar erro interno controlado | Resposta não revela credenciais, caminhos internos ou detalhes sensíveis | Média |

### 9.7. Base de dados

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| DB-01 | Inserção de leitura | Enviar uma leitura válida | Registo criado na tabela leituras | Alta |
| DB-02 | Duplicação | Inserir novamente a mesma chave única | Não é criado outro registo | Alta |
| DB-03 | Integridade do nó | Enviar leitura de nó válido | Associação ao nó correto | Alta |
| DB-04 | Integridade temporal | Consultar timestamp armazenado | Valor corresponde ao instante enviado | Alta |
| DB-05 | Sensor sem INA219 | Enviar leitura sem corrente_ma | Campo permanece sem valor, quando aplicável | Média |
| DB-06 | Sensor com INA219 | Enviar leitura com corrente_ma | Valor armazenado corretamente | Média |

### 9.8. Dashboard

Os seguintes testes dependem da disponibilização da primeira versão funcional do dashboard.

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| DASH-02 | Estado da divisão | Consultar uma divisão com leituras disponíveis | Presença, LED e luminosidade apresentados corretamente | Alta |
| DASH-04 | Histórico | Consultar gráfico de leituras | Valores correspondem aos dados da API | Média |
| DASH-05 | Falha da API | Interromper temporariamente a API | Utilizador recebe indicação de indisponibilidade | Média |
| DASH-06 | Autenticação | Aceder sem credenciais válidas | Acesso restrito | Alta |
| DASH-08 | Dados incompletos | Consultar divisão com valores opcionais ausentes | Página mantém-se funcional e representa corretamente os valores indisponíveis | Média |

### 9.9. Inteligência Artificial

Os seguintes testes serão executados à medida que a componente evoluir.

| ID | Cenário | Procedimento | Resultado esperado | Prioridade |
|---|---|---|---|---|
| AI-01 | Valores nulos | Processar leituras com luminosidade ausente | Valores nulos preservados conforme regras definidas | Média |
| AI-02 | Agregação horária | Processar leituras por hora UTC | Resumos horários produzidos corretamente | Média |

## 10. Procedimento de execução

Cada teste deverá seguir os seguintes passos:

1. Identificar o teste através do respetivo ID.
2. Confirmar que os pré-requisitos estão cumpridos.
3. Preparar os dados e o ambiente necessários.
4. Executar os passos descritos no caso de teste.
5. Comparar o resultado obtido com o resultado esperado.
6. Registar o resultado como aprovado, reprovado, bloqueado ou não executado.
7. Guardar evidências quando aplicável.
8. Se existir uma falha, criar um defeito no Jira.
9. Repetir o teste depois de a correção ser disponibilizada.
10. Registar o resultado da nova execução.

## 11. Registo de resultados

Cada execução deverá incluir:

- ID do teste.
- Versão ou commit do software testado.
- Ambiente utilizado.
- Resultado esperado.
- Resultado obtido.
- Estado do teste.
- Evidências.
- Identificador do defeito.

Estados possíveis:

- **Aprovado:** resultado obtido corresponde ao esperado.
- **Reprovado:** resultado obtido não corresponde ao esperado.
- **Bloqueado:** não foi possível executar por falta de pré-requisitos ou dependências.
- **Não executado:** ainda não foi realizada a execução.

## 12. Gestão de defeitos

Todos os defeitos identificados deverão ser registados no Jira.

Cada ocorrência deverá conter:

- Título objetivo.
- Descrição do problema.
- Componente afetada.
- Passos para reprodução.
- Resultado esperado.
- Resultado obtido.
- Gravidade.
- Evidências.
- Versão em que foi identificado.
- Estado de resolução.

Após a correção, os testes relacionados deverão ser repetidos para confirmar a resolução.

## 13. Riscos e limitações

- A fila offline do firmware utiliza memória RAM e perde os dados após reinício ou perda de energia.
- A capacidade real da fila depende da memória disponível no ESP32.
- A leitura de luminosidade varia conforme o tipo de sensor instalado.
- Os valores de presença e luminosidade dependem da calibração e das condições físicas de instalação.
- A execução de testes de integração depende da disponibilidade da API, da base de dados, do dashboard e dos nós.
- Os resultados de testes com dados fictícios não substituem a validação com hardware real.

## 14. Revisão e manutenção do plano

Este plano deverá ser atualizado sempre que:

- Forem acrescentadas ou alteradas funcionalidades.
- A estrutura dos pedidos ou respostas da API mudar.
- Forem instalados novos sensores.
- Forem alterados os mecanismos de autenticação ou comunicação.
- Forem identificados novos riscos.
- Forem adicionados testes ou critérios de aceitação.

## 15. Documentação complementar

Os resultados detalhados dos testes são mantidos junto das
respetivas componentes:

- `backend/TESTES.md`: testes do servidor, API e base de dados.
- `ai/tests/`: testes automatizados da componente de IA.
- `Documentacao/testes/resultados.md`: consolidação dos resultados
  das diferentes componentes.