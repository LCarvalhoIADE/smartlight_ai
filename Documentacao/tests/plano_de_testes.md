# Plano de Testes — SmartLight AI

**Projeto:** SmartLight AI  
**Grupo:** g04  
**Responsável pela componente de QA:** Ricardo Siqueira  
**Versão do documento:** 1.1
**Estado:** Plano proposto — em andamento

---

## 1. Introdução

Este documento define a estratégia, o âmbito, os procedimentos e os critérios de aceitação dos testes a realizar no projeto SmartLight AI.

O objetivo é verificar se as diferentes componentes do sistema cumprem os requisitos funcionais e não funcionais definidos pela equipa, identificar defeitos e garantir a integridade dos dados durante o funcionamento normal e perante situações de falha.

Os testes abrangem o firmware dos nós ESP32, a comunicação com o servidor, a API REST, a base de dados MySQL, o dashboard e a integração com a componente de Inteligência Artificial.

A execução será progressiva, acompanhando a disponibilidade das diferentes componentes do projeto.

## 1.1 Versões

### 1.1 

alinha os casos de teste com a Especificação de Requisitos, incluindo as histórias HU01–HU14, os requisitos funcionais RF01–RF51 e os requisitos não funcionais RNF01–RNF33.

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

## 3.2. Exclusões e condições

- RF49 — controlo por assistente de voz: Won't; não exige teste funcional nesta versão.

- RF50 — aplicação móvel própria: Won't; o acesso é feito pelo browser, incluindo em telemóvel.

- RF51 — faturação ao cliente: Won't; não exige teste funcional nesta versão.

- RNF05 — suporte de 50 casas: Won't; não integra os critérios de aprovação desta versão.

- Os requisitos relativos ao firmware são testados na medida em que o comportamento observável do equipamento permite validar os RF/RNF.

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

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| API-AUTH-01 | Criar conta válida | Criar conta com email e palavra-passe válidos. | Conta criada e acesso disponibilizado. | Alta | RF01 |
| API-AUTH-02 | Dados inválidos no registo | Tentar criar conta com email e/ou palavra-passe inválidos. | Registo recusado e mensagem de erro apresentada. | Alta | RF01; RNF20 |
| API-AUTH-03 | Iniciar sessão | Entrar com credenciais válidas e depois repetir com palavra-passe incorreta. | Credenciais válidas abrem sessão; inválidas não abrem sessão e apresentam erro. | Alta | RF02; RNF20 |
| API-AUTH-04 | Terminar sessão | Terminar sessão e tentar voltar à página protegida. | A página exige novo início de sessão. | Média | RF03 |
| API-AUTH-05 | Recuperar palavra-passe | Solicitar recuperação, utilizar a ligação antes e depois de 1 hora. | Ligação válida permite definir nova palavra-passe; ligação expirada é recusada. | Média | RF04 |
| API-AUTH-06 | Expiração por inatividade | Manter sessão sem interação durante 30 minutos e executar uma ação. | A ação encaminha para o início de sessão. | Média | RF05 |
| API-AUTH-07 | Bloqueio após falhas | Efetuar cinco tentativas falhadas e tentar entrar com credenciais corretas antes e depois de 15 minutos. | A sexta tentativa é bloqueada durante 15 minutos; depois, credenciais válidas permitem entrar. | Alta | RNF13 |
| API-AUTH-08 | Isolamento entre casas | Autenticado como cliente A, tentar consultar dados da casa B. | Pedido negado e nenhum dado da casa B é devolvido. | Alta | RNF10 |
| API-AUTH-09 | Desativação de conta | Desativar conta de cliente e tentar iniciar sessão. | A conta desativada não consegue iniciar sessão. | Alta | RF41 |
| API-AUTH-10 | Consentimento RGPD | Tentar criar conta sem aceitar o consentimento e depois aceitar. | Sem aceitação a conta não é criada; com aceitação, a data fica registada. | Alta | RF45 |

### 9.2. API — Validação dos pedidos

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| API-VAL-01 | Token válido | Enviar POST com token válido e dados válidos. | Pedido aceite com HTTP 200. | Alta | RNF11 |
| API-VAL-02 | Token inválido ou ausente | Enviar POST com token incorreto e repetir sem Token. | Envios recusados e mensagem de erro. | Alta | RNF11; RNF20 |
| API-VAL-03 | JSON inválido | Enviar conteúdo não JSON e pedido sem corpo. | Pedido recusado com erro; nenhum registo criado. | Alta | RNF20 |
| API-VAL-04 | Campo obrigatório ausente | Remover um campo obrigatório da leitura. | Pedido recusado e campo em falta identificado. | Alta | RNF20 |
| API-VAL-05 | Tipos e valores inválidos | Enviar texto num campo numérico e intensidade abaixo de 0% ou acima de 100%. | Leituras inválidas recusadas e não persistidas. | Alta | RNF30 |
| API-VAL-06 | Timestamp ausente | Enviar leitura sem timestamp. | Leitura recusada. | Alta | RNF30 |
| API-VAL-07 | Identificador de nó desconhecido | Enviar leitura com identificador não registado. | Pedido recusado não associado a outro nó. | Alta | RNF11 |
| API-VAL-08 | Primeira leitura e sequência | Enviar leitura inédita e outra com seq diferente. | Ambas são guardadas como registos distintos. | Alta | RF10; RNF29 |
| API-VAL-09 | Leitura duplicada | Reenviar a mesma identidade de leitura. |histórico e consumo contam só uma vez. | Alta | RNF29 |
| API-VAL-10 | Timestamp UTC | Enviar timestamp conhecido e consultar o valor persistido. | Instante de medição preservado e identificável em UTC. | Alta | RF10; RNF31 |
| API-VAL-11 | Campos opcionais ausentes | Enviar leitura sem luminosidade percentual e sem corrente, quando não aplicável. | Campos opcionais permanecem ausentes sem corromper a leitura. | Média | RF10; RF24 |
| API-VAL-12 | Autorização de consulta administrativa | Consultar endpoint administrativo com e sem credencial autorizada. | Só a credencial autorizada obtém dados administrativos. | Alta | RF37; RNF10 |

### 9.3. Firmware — Sensores e controlo local

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| ESP-SEC-01 | Deteção de presença | Gerar movimento perante o PIR | Presença identificada | Alta | RF06; RF10 |
| ESP-SEC-02 | Ausência de movimento | Não gerar movimento durante 5 minutos. | A luz permanece acesa durante os 5 minutos e Presença passa a falsa após o timeout | Alta | RF07 |
| ESP-SEC-03 | Sensor digital em ambiente claro | Colocar sensor na condição clara | Leitura raw igual a 0 | Alta | RF06; RF09 |
| ESP-SEC-04 | Sensor digital em ambiente escuro | Colocar sensor na condição escura | Leitura raw igual a 1 | Alta | RF06; RF09 |
| ESP-SEC-05 | Presença e ambiente claro | Simular presença e sensor claro | LED desligado | Alta | RF06 |
| ESP-SEC-06 | Presença e ambiente escuro | Simular presença e sensor escuro | LED com intensidade máxima | Alta | RF06 |
| ESP-SEC-07 | Ausência de presença | Aguardar o fim do timeout | LED desligado | Alta | RF08 |
| ESP-SEC-08 | Tempo de ausência configurável | Alterar o tempo para 30 segundos e sair da divisão. | Luz apaga entre 30 e 35 segundos depois da saída. | Baixa | RF19 |
| ESP-SEC-9 | Nível de luz pretendido | Configurar nível pretendido e medir a luz na divisão com sensor multinível. | Após 30 segundos, luz medida fica a menos de 10 pontos percentuais do nível pretendido. | Média | RF09; RF18 |
| ESP-SEC-10 | Modo manual | Ativar modo manual e provocar alterações de presença. | Luz deixa de reagir à presença. | Média | RF20 |
| ESP-SEC-11 | Intensidade manual | Em modo manual, escolher intensidade válida e depois valor fora de 0–100%. | Valor válido aplicado; valor inválido recusado. | Média | RF21 |
| ESP-SEC-12 | Regresso ao automático | Mudar de manual para automático e provocar presença/ausência. | Controlo volta a seguir RF06–RF08. | Média | RF22 |
| ESP-SEC-13 | Horário de funcionamento | Configurar horário e testar presença dentro e fora do horário. | Fora do horário, luz permanece apagada mesmo com presença. | Média | RF23 |
| ESP-SEC-14 | Funcionamento local | Desligar Wi-Fi e repetir os testes de iluminação | RF06–RF08 continuam a funcionar | Alta |
| ESP-15 | Registo periódico | Observar leituras da divisão durante período controlado. | Um registo a cada 15 s, tolerância de ±2 s. | Alta | RF10 |

### 9.4. Firmware — Comunicação e fila offline

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| ESP-CEF-01 | Ligação Wi-Fi | Iniciar com Wi-Fi, interromper e restabelecer a rede. | Nó continua a controlar a iluminação, após recuperação liga-se e reconecta. | Alta | RF34; RF35 |
| ESP-CEF-02 | Fila offline | Interromper a rede durante uma hora e manter o nó em funcionamento. | Registos preservados e enviados após recuperação, com hora original. | Alta | RNF28 |
| ESP-CEF-03 |  Capacidade de 24 horas offline | Interromper ligação durante 24 horas. | Os 11 520 registos previstos são preservados | Alta | RNF27 |
| ESP-CEF-04 | Servidor indisponível | Manter Wi-Fi ativo e indisponibilizar o servidor. | Leituras permanecem pendentes e são reenviadas. | Alta | RNF28 |
| ESP-CEF-05 | Reinício durante falha de rede | Acumular leituras offline e reiniciar o ESP32 antes da recuperação. | dados sobrevivem ao reinício. | Alta | RNF27; RNF28; RNF32 |
| ESP-CEF-06 | corte de energia | Cortar e repor alimentação do equipamento. | Luz e registos retomam automaticamente até 30 segundos depois. | Média | RNF32; RF35 |

### 9.5. Dashboard

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| DASH-01 | Estado da divisão | Consultar uma divisão com leituras disponíveis | Presença, LED e luminosidade apresentados corretamente | Alta | RF11 |
| DASH-02 | Atualização sem refresh | Manter página aberta e gerar novos registos. | Novo registo aparece sem ação manual. | Alta | RF12; RNF01 |
| DASH-03 | Aviso de equipamento offline | Desligar equipamento | Aviso aparece entre 60 e 90 s e desaparece após recuperação. | Alta | RF13 |
| DASH-04 | Histórico gráfico | Abrir histórico de uma divisão. | Gráfico apresenta presença, luz natural e intensidade guardadas. | Média | RF14 |
| DASH-05 | Filtros do histórico | Selecionar últimas 24 h, últimos 7 dias e intervalo de datas. | Gráfico apresenta apenas registos do período escolhido. | Média | RF15 |
| DASH-06 | Exportar histórico da divisão | Descarregar histórico de uma divisão e comparar com os registos do período. | Ficheiro contém uma linha por registo do período escolhido. | Baixa | RF16 |
| DASH-07 | Alterar nome da divisão | Alterar nome e consultar página e histórico anterior. | Novo nome aparece em toda a página e histórico anterior mantém-se. | Média | RF17 |
 DASH-08 | Alerta de luz acesa sem presença | Deixar divisão sem presença e luz acesa para além do tempo definido mais 2 minutos. | Alerta aparece na página em menos de 30 segundos. | Média | RF28 |
| DASH-09 | Estado indisponível | Interromper API e consultar a página. | Utilizador recebe indicação de indisponibilidade. | Média | RF13; RNF20; RNF21 |
| DASH-10 | Valores opcionais ausentes | Consultar divisão com campos opcionais ausentes. | Página mantém-se funcional e indica valores indisponíveis corretamente. | Média | RF11; RNF20 |
| DASH-11 | Usabilidade da consulta | Pedir a cinco pessoas que consultem o estado de uma divisão. | Pelo menos quatro concluem em menos de um minuto. | Média | RNF16 |
| DASH-12 | Alteração em três cliques | A partir da página inicial, alterar nível de luz. | Alteração concluída em três cliques ou menos. | Média | RF18; RNF17 |
| DASH-13 | Largura móvel de 360 px | Testar todas as funções de consulta/configuração em viewport de 360 px. | Sem deslocamento horizontal; funções permanecem utilizáveis. | Alta | RNF18 |
| DASH-14 | Português europeu | Inspecionar textos visíveis em todas as páginas. | Nenhum texto visível ao cliente está noutra língua. | Média | RNF19 |
| DASH-15 | Mensagens de erro | Provocar erros representativos de autenticação, validação e indisponibilidade. | Cada mensagem explica o erro e sugere o que fazer. | Média | RNF20 |
| DASH-16 | Estado não indicado apenas por cor | Inspecionar estados online/offline/erro. | Cada estado com texto identificável. | Baixa | RNF21 |
| DASH-17 | Contraste | Medir contraste do texto com o fundo em todas as páginas. | Rácio mínimo de 4,5:1. | Baixa | RNF22 |
| DASH-18 | Hora local por casa | Usar hora em Portugal e Suíça. | Portugal e Suíça apresentam a hora local. | Média | RF36; RF39; RNF23 |

### 9.6. Inteligência Artificial

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| AI-01 | Previsão para amanhã | Executar modelo e consultar previsão horária e total do dia seguinte. | São apresentados valores por hora no horário da casa e total diário produzidos pelo modelo. | Média | RF27 |
| AI-02 | Alerta de consumo acima da previsão | Criar consumo 20% superior à previsão. | Recebe Alerta de consumo. | Baixa | RF29 |
| AI-03 | Meteorologia diária | Consultar meteorologia da localidade e comparar com serviço de origem. | Dados correspondem ao serviço usado. | Média | RF30 |
| AI-04 | Previsão de horas de sol | Consultar os sete dias seguintes. | São apresentados os sete dias e as respetivas horas de sol previstas. | Baixa | RF31 |
| AI-05 | Dados nulos e incompletos | Processar leituras com luminosidade ausente e outros campos opcionais. | Pipeline trata os valores, sem inventar medições. | Média | RF24; RF27 |
| AI-6 | Limite de pedidos meteorológicos | Manter página aberta durante uma hora e contabilizar pedidos por casa. | Não são feitos mais de dois pedidos por casa na hora. | Baixa | RNF07 |

## 9.7. Administração e RGPD
| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| ADM-01 | Painéis por casa | Registar quatro casas e consultar painel administrativo. | quatro painéis, cada um apenas com as divisões da respetiva casa. | Alta | RF37 |
| ADM-02 | Agrupamento por país | Registar casas em Portugal e Suíça e aceder ao perfil admin. | Casas aparecem agrupadas por país. | Baixa | RF38 |
| ADM-03 | Equipamentos sem comunicação | Deixar equipamento sem comunicar por mais de 60 segundos. | Possibilidade de listar apenas equipamentos sem comunicação há mais de 60 s. | Média | RF40 |
| ADM-04 | Gerar credencial | Gerar credencial para equipamento e enviar leitura com ela. | Registo aceite com credencial gerada. | Alta | RF42; RNF11 |
| ADM-05 | Revogar credencial | Revogar credencial e tentar enviar novo registo com a credencial antiga. | Envio recusado e nenhum registo guardado. | Alta | RF43; RNF11 |
| ADM-06 | Exportar registos globais | Exportar um dia de registos de todas as casas. | Ficheiro contém o mesmo número de registos guardados. | Média | RF44 |
| ADM-07 | Consultar dados pessoais | Autenticado como cliente, consultar os dados associados. | São apresentados email, divisões e localidade associados à conta. | Alta | RF46 |
| ADM-08 | Eliminar conta e dados | Solicitar eliminação com conta de utilizador. | Conta e registos da casa deixam de existir no sistema. | Alta | RF47 |
| ADM-09 | Portabilidade de dados | Descarregar dados pessoais e tentar processar o ficheiro sem transcrição manual. | Ficheiro legível por máquina com os dados da conta. | Baixa | RF48 |
| ADM-10 | Localização sem morada | Inspecionar os dados guardados da casa. | Localização guardada identifica apenas a localidade, não a morada. | Média | RNF15 |
## 9.8. Segurança e infraestrutura
| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| SEC-01 | HTTPS obrigatório | Tentar aceder por HTTP e repetir por HTTPS. | Ligação sem cifra não devolve dados nem permite guardar registos. | Alta | RNF08 |
| SEC-02 | Validação do certificado TLS | Inspecionar a validação do certificado e testar certificado inválido/não confiável. | Cliente valida certificado e identidade do servidor; ligação inválida é recusada. | Alta | RNF08 |
| SEC-03 | Palavras-passe protegidas | Inspecionar armazenamento de contas de teste. | Nenhuma palavra-passe está guardada em texto legível. | Alta | RNF09 |
| SEC-04 | Credenciais dos equipamentos protegidas | Inspecionar armazenamento de credenciais e validar reconhecimento do equipamento. | Credenciais não estão em texto legível e equipamentos continuam reconhecidos. | Alta | RNF12 |
| SEC-05 | Base de dados não exposta | Tentar ligação direta à porta MySQL a partir da Internet. | Ligação recusada. | Alta | RNF14 |
| SEC-06 | Segredos no Git | Inspecionar ficheiros e histórico do repositório. | Não existem tokens nem credenciais reais publicados. | Alta | RNF09; RNF12 |
| SEC-07 | Erros sem informação sensível | Provocar erro interno e inspecionar resposta exposta ao cliente. | Não são reveladas credenciais, caminhos internos ou detalhes sensíveis. | Média | RNF08; RNF09; RNF12 |
| SEC-08 | Credenciais incorretas da BD | Configurar credenciais erradas num ambiente de teste. | Aplicação não acede à BD e não divulga credenciais. | Média | RNF14 |
| SEC-09 | Injeção SQL | Executar entradas de teste com padrões de SQL injection nos campos de entrada. | Entradas são tratadas como dados; não permitem consulta ou alteração não autorizada. | Alta | RNF10; RNF14 |
| SEC-10 | Disponibilidade mensal | Monitorizar serviço minuto a minuto durante um mês e calcular disponibilidade. | Disponibilidade mensal igual ou superior a 99%. | Média | RNF25 |
| SEC-11 | Backup e restauro | Confirmar backup diário e restaurá-lo numa máquina de teste. | Existe cópia diária e o restauro recupera os registos. | Alta | RNF33 |

## 9.9. Desempenho

| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| PERF-01 | Atualização de 20 registos | Medir 20 vezes o intervalo entre medição e apresentação na página. | Todas as 20 medições são inferiores a 30 segundos. | Alta | RNF01; RF12 |
| PERF-02 | Abertura da página | Abrir página 10 vezes e medir. | Pelo menos 9 das 10 aberturas demoram menos de 3 segundos. | Média | RNF02 |
| PERF-03 | Histórico de 24 horas | Fazer 10 pedidos de histórico de uma divisão e medir. | Pelo menos 9 dos 10 pedidos demoram menos de 2 segundos. | Média | RNF03 |
| PERF-04 | Registos sem perdas | enviar registos das 4 casas a cada 15 segundos durante uma hora. | Todos os registos esperados ficam guardados. | Alta | RNF04 |
| PERF-05 | Histórico de 120 dias | verificar histórico das quatro casas, cinco divisões no total e cerca de 3,5 milhões de registos. | RNF02 e RNF03 continuam a ser cumpridos. | Média | RNF06 |

## 9.10 Instalação e associação de equipamentos
| ID | Cenário | Procedimento | Resultado esperado | Prioridade | Requisitos |
| --- | --- | --- | --- | --- | --- |
| INST-01 | Registar divisão | Como instalador, registar uma divisão com um nome definido. | A divisão fica disponível na conta do cliente indicado. | Alta | RF32 |
| INST-02 | Associar equipamento à casa | Associar o identificador de um equipamento à casa escolhida e enviar uma leitura. | Os registos do equipamento aparecem associados às divisões da casa selecionada, sem mistura com outras casas. | Alta | RF33 |
| INST-03 | Configurar Wi-Fi sem reprogramar | Indicar o Wi-Fi do cliente e reiniciar a ligação. | O equipamento liga-se à rede indicada e envia registos sem alteração/reprogramação do código. | Média | RF34 |
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