# Testes do servidor, da API e da base de dados

Registo dos testes feitos ao servidor, à API e à base de dados e dos que faltam fazer. Cada teste indica o requisito que verifica (RF-S e RNF, na especificação de requisitos) e o nível no Modelo em V.

Níveis: **U** unitário (um ficheiro da API isolado), **I** integração (nó, servidor e base de dados em conjunto), **S** sistema (o sistema a funcionar em condições reais).

## Testes feitos

| ID | Data | Requisito | Nível | Procedimento | Resultado esperado | Resultado obtido |
|---|---|---|---|---|---|---|
| T01 | 21/10/2026 | RF-S11 | U | Pedido a `ultimas.php` com a chave de administrador, antes de haver leituras | Resposta `[]` | `[]`. Servidor, chave e base de dados ligados |
| T02 | 21/10/2026 | RF-S02 | U | `POST` a `leituras.php` com `curl` e um JSON de teste, a partir do servidor | Resposta 200 e leitura guardada | `{"ok":true,"novas":1,"duplicadas":0}` |
| T03 | 21/10/2026 | RF-S09 | U | Pedido a `ultimas.php` depois do T02 | Devolve a leitura de teste | Devolve no1, sala, presença 1, LED 50%, modo auto |
| T04 | 21/10/2026 | RF-S02 | I | Primeiro envio de um ESP32 real (no1) por HTTPS | Resposta 200 e leituras guardadas a cada 15 s | Primeira leitura às 21:29:56. Envio contínuo a partir daí |
| T05 | 21/10/2026 | RF-S05, RF-S06, RNF-F01 | S | Falha do servidor (anfitrião da OVH), das 21:29 às 21:43 | O nó guarda as leituras na fila e envia-as quando o servidor volta, sem buracos nem duplicados | Sem buracos no no1 (intervalo máximo de 20 s entre leituras). Sem duplicados |
| T06 | 22/10/2026 | RF-S07 | I | Nó no2 a enviar duas divisões (sala e quarto) em cada leitura | Dois registos por leitura, um por divisão | 19 017 leituras, todas com os dois registos |
| T07 | 24/10/2026 | RF-S08 | I | Registo do nó no3 com token próprio | O nó novo envia leituras com o seu token | Primeiras leituras do no3 a 24/10 |
| T08 | 25/10/2026 | RNF-F02 | S | Mudança da hora de verão (Lisboa passa de UTC+1 para UTC+0) | O `ts` em UTC continua sem saltos | Sem buracos no no1 entre 00:30 e 02:30 |
| T09 | 25/10/2026 | RF-S05, RNF-F01 | S | Reinício do servidor para atualizar o PHP (falha PHP2Shell) | Leituras entregues depois do reinício | Paragens curtas, leituras entregues pela fila dos nós |
| T10 | 27/10/2026 | RF-S05, RF-S06, RNF-F01 | S | Manutenção da OVH, das 18:33 até depois das 20:00 | O nó guarda as leituras na fila e envia-as quando o servidor volta, sem buracos | Fila do no1 com 86 leituras às 19:10. Sem buracos no no1 nem no no3 entre 18:20 e 20:30 (intervalo máximo de 21 s) |
| T11 | 30/10/2026 | RF-S08 | I | Registo do nó no4 com token próprio | O nó novo envia leituras com o seu token | Primeira leitura do no4 a 31/10 às 22:38:15 |
| T12 | 30/10/2026 | RF-S12 | U | Pedido a `ultimas.php` só com o token do no4 | Resposta `[]`, só com as leituras do no4 | Falhou com 403 `sem acesso`, porque o `ultimas.php` do servidor era uma versão antiga sem suporte a token. Corrigido no mesmo dia (ver T13) |
| T13 | 30/10/2026 | RF-S12 | U | Pedido a `ultimas.php` com o token do no4, antes de o nó enviar | Resposta `[]`, sem leituras de outros nós | `[]` |
| T14 | 30/10/2026 | RF-S11 | U | Pedido a `ultimas.php` com a chave de administrador, depois da correção do T12 | Devolve as leituras de todos os nós | Devolve todos os nós |
| T15 | 30/10/2026 | RNF-S06 | S | `php -v` dentro do contentor `web` | PHP 8.3.36 ou superior (correção da PHP2Shell) | PHP 8.3.36 |
| T16 | 30/10/2026 | RNF-S08 | S | Permissões do ficheiro `.env` no servidor | Só o dono lê e escreve | `-rw-------` |
| T17 | 30/10/2026 | RF-S05 | S | Procura de leituras repetidas na exportação da base de dados (118 492 leituras) | Nenhuma leitura repetida | 0 repetidas |
| T18 | 01/11/2026 | RF-S02 | I | Nó no1 com INA219 e firmware v4 a enviar `corrente_ma` | Resposta 200 e corrente guardada | Resposta 200. Corrente 0,0 mA com o LED apagado |
| T19 | 01/11/2026 | Medição | I | LED a 100% (sensor de luz tapado) e a 70% (luz entre 50 e 150 lux), corrente lida pelo INA219 | Perto de 5,9 mA a 100% (3,3 V, LED vermelho com cerca de 2 V, resistência de 220 ohm) e perto de 3,9 mA a 70% | 5,6 mA a 100%, cerca de 18,5 mW. Entre 3,4 e 4,2 mA a 70%, em 10 leituras |
| T20 | 03/11/2026 | RF-S13, RF-S14 | S | Consumo diário do no1 estimado a partir do `led_pct` (potência de 17,9 mW a 100%, obtida da corrente média medida de 5,41 mA a 3,3 V) comparado com o consumo medido pelo INA219 (corrente × 3,3 V), excluindo leituras com `luz_raw` negativo | Diferença pequena entre o estimado e o medido | 01/11: 23,4 mWh estimados e 23,3 medidos (+0,7%), com 2530 leituras. 02/11: 11,8 e 12,0 (−1,6%), com 5734 leituras. Corrente média por nível: 2,45 mA a 40% (4 leituras), 3,71 mA a 69% (483, nível de 70%) e 5,41 mA a 100% (138) |
| T21 | 04/11/2026 | RF-S09, RF-S16 | S | Pedido a `ultimas.php?por_divisao=1` com a chave de administrador | Uma só linha por nó e divisão | 7 linhas, nenhuma repetida: no1 sala, no2 corredor, quarto e sala, no3 sala, no4 Cozinha e sala. As divisões sem envio recente continuam a aparecer com a hora da última leitura (no2 sala a 27/10 e no4 sala a 01/11). Cada linha traz o `sensor_luz` (lux no no1, analogico no no2 e digital no no3 e no no4) |
| T22 | 04/11/2026 | RF-S12 | S | Pedido a `ultimas.php?por_divisao=1&no_id=no4` com o token do no4 | Só linhas do no4 | 2 linhas, Cozinha e sala, ambas do no4 |
| T23 | 04/11/2026 | RF-S12 | S | Pedido a `ultimas.php?por_divisao=1&no_id=no2` com o token do no4 | Acesso recusado | `{"erro":"sem acesso"}` |
| T24 | 04/11/2026 | RF-S17 | S | Pedido a `historico.php?no_id=no1&limite=3` com a chave de administrador | Bloco do nó com localização e fuso, e 3 leituras | Latitude 41,15, longitude −8,58 e fuso Europe/Lisbon. 3 leituras com `ts` crescente de 15 s em 15 s, as mais antigas das últimas 24 h, com `mais: true` |
| T25 | 04/11/2026 | RF-S11 | S | Pedido a `historico.php?no_id=no1` sem chave nem token | Acesso recusado | `{"erro":"sem acesso"}` |
| T26 | 04/11/2026 | RF-S10, RNF-D05 | S | Pedido a `historico.php` da divisão sala do no1 nas últimas 24 h, com `limite=10000`, comparado com a contagem na base de dados | Todas as leituras guardadas, em menos de 2 s | 5718 leituras na resposta, igual à contagem na base de dados (5718), com `mais: false`. Um pedido com 681 330 bytes demorou 0,273 s |
| T27 | 04/11/2026 | RF-S03, RNF-U01 | U | `POST` a `leituras.php` com o token do no1 e sem o campo `ts` | Resposta 422 com mensagem que indica o campo | Resposta 422, `{"erro":"falta o campo ts"}` |
| T28 | 04/11/2026 | RF-S09 | U | `ultimas.php?por_divisao=1` com a chave de administrador e, logo a seguir, a consulta `SELECT no_id, divisao, ts FROM leituras WHERE id IN (SELECT MAX(id) FROM leituras GROUP BY no_id, divisao)` na base de dados | Mesmo `ts` em todas as divisões | As 7 divisões com o mesmo `ts` nos dois resultados, incluindo as 5 ativas (por exemplo no1 sala 1793805371 e no3 sala 1793805378) |
| T29 | 04/11/2026 | RNF-S03 | S | Pesquisa no repositório local, atualizado com o GitHub (95 commits, todas as ramificações), de sequências hexadecimais com 32 ou mais caracteres e de atribuições a `ADMIN_KEY`, `DB_PASS`, `DB_ROOT_PASS`, `token`, `password` e `senha` com valor, nas linhas acrescentadas em todo o histórico | Nenhuma credencial encontrada | Nenhuma correspondência |

## Testes por fazer

| ID | Requisito | Nível | Procedimento | Resultado esperado |
|---|---|---|---|---|
| T30 | RF-S01 | U | `POST` a `leituras.php` com um token errado | Resposta 401 e nada guardado |
| T31 | RF-S04 | U | `POST` com `led_pct` igual a 150 | Resposta 422 e nada guardado |
| T32 | RF-S05 | U | O mesmo `POST` enviado duas vezes | Primeira resposta com `novas: 1`, segunda com `duplicadas: 1`. Um só registo |
| T33 | RF-S06 | I | Comparar `recebido_em` com `ts` nas leituras de 27/10 entre 18:33 e 20:00 | `recebido_em` posterior a `ts` nas leituras que vieram da fila |
| T34 | RNF-D02 | S | 100 envios seguidos com `curl -w "%{time_total}"` | Tempo médio abaixo de 500 ms |
| T35 | RNF-D04 | S | 10 pedidos seguidos a `ultimas.php?por_divisao=1` | Todos abaixo de 1 s |
| T36 | RNF-D03 | S | 4 nós reais a enviar durante 1 hora | Todas as leituras guardadas, sem buracos nem duplicados |
| T37 | RF-S05 | S | Teste controlado: parar o contentor `web` durante 15 min, desligar o nó da corrente a meio, voltar a ligar o nó e depois o servidor (firmware versão 3, fila na flash) | O nó recupera a fila da flash e envia-a. Só falta o intervalo em que esteve sem energia |
| T38 | RNF-S02 | S | A partir de fora do servidor, tentar ligar à porta 3306 | Ligação recusada |
| T39 | Medição | I | LED a 40% (luz entre 150 e 300 lux), corrente lida pelo INA219 | Cerca de 2,2 mA, proporcional ao `led_pct` |
| T40 | RF-S15 | U | `POST` com `corrente_ma` igual a 1500 | Resposta 422 e nada guardado |
| T41 | RNF-S01 | S | Pedido por HTTP simples a `leituras.php` | Não devolve nem aceita leituras |
| T42 | RNF-S04 | U | `POST` com comandos SQL no campo `no_id` e numa divisão | Recusado ou guardado como texto, sem alterar a base de dados |
| T43 | RNF-S07 | S | Mudar a chave de administrador no ficheiro de configuração e recriar o contentor `web` | A chave antiga recebe 403 e a nova dá acesso |
| T44 | RNF-M01 | S | Num servidor de teste, com os ficheiros do repositório e o ficheiro de configuração, subir o `docker compose` | `ultimas.php?por_divisao=1` responde |
| T45 | RNF-D07 | S | Com 4 nós durante 120 dias (cerca de 2,8 milhões de linhas), repetir T26 e T35 | Os dois critérios continuam a cumprir-se. Só é possível com esse volume de dados, por isso fica para janeiro |

## Observações

- Os testes T05, T09 e T10 não foram provocados. Foram falhas do servidor e os resultados foram verificados nos dados guardados.
- As datas e os intervalos estão em hora de Lisboa. Na base de dados, o `ts` está em UTC.
- A 04/11/2026 foi feita uma cópia da base de dados com `mysqldump` (21 MB) e criado o índice `idx_no_div_id (no_id, divisao, id)`, usado pelo `ultimas.php?por_divisao=1`. O índice `idx_no_ts (no_id, ts)`, usado pelo `historico.php`, já existia. A cópia foi feita à mão e o restauro não foi testado, por isso o RNF-F03 continua por cumprir.
