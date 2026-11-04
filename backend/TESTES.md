# Testes do servidor, da API e da base de dados

Registo dos testes feitos ao servidor, à API e à base de dados e dos que faltam fazer. Cada teste indica o requisito que verifica (RF-S e RNF-D, na especificação de requisitos) e o nível no Modelo em V.

Níveis: **U** unitário (um ficheiro da API isolado), **I** integração (nó, servidor e base de dados em conjunto), **S** sistema (o sistema a funcionar em condições reais).

## Testes feitos

| ID | Data | Requisito | Nível | Procedimento | Resultado esperado | Resultado obtido |
|---|---|---|---|---|---|---|
| T01 | 21/10/2026 | RF-S11 | U | Pedido a `ultimas.php` com a chave de administrador, antes de haver leituras | Resposta `[]` | `[]`. Servidor, chave e base de dados ligados |
| T02 | 21/10/2026 | RF-S02 | U | `POST` a `leituras.php` com `curl` e um JSON de teste, a partir do servidor | Resposta 200 e leitura guardada | `{"ok":true,"novas":1,"duplicadas":0}` |
| T03 | 21/10/2026 | RF-S09 | U | Pedido a `ultimas.php` depois do T02 | Devolve a leitura de teste | Devolve no1, sala, presença 1, LED 50%, modo auto |
| T04 | 21/10/2026 | RF-S02 | I | Primeiro envio de um ESP32 real (no1) por HTTPS | Resposta 200 e leituras guardadas a cada 15 s | Primeira leitura às 21:29:56. Envio contínuo a partir daí |
| T05 | 21/10/2026 | RF-S05, RF-S06 | S | Falha do servidor (anfitrião da OVH), das 21:29 às 21:43 | O nó guarda as leituras na fila e envia-as quando o servidor volta, sem buracos nem duplicados | Sem buracos no no1 (intervalo máximo de 20 s entre leituras). Sem duplicados |
| T06 | 22/10/2026 | RF-S07 | I | Nó no2 a enviar duas divisões (sala e quarto) em cada leitura | Dois registos por leitura, um por divisão | 19 017 leituras, todas com os dois registos |
| T07 | 24/10/2026 | RF-S08 | I | Registo do nó no3 com token próprio | O nó novo envia leituras com o seu token | Primeiras leituras do no3 a 24/10 |
| T08 | 25/10/2026 | RF-S02 | S | Mudança da hora de verão (Lisboa passa de UTC+1 para UTC+0) | O `ts` em UTC continua sem saltos | Sem buracos no no1 entre 00:30 e 02:30 |
| T09 | 25/10/2026 | RF-S05 | S | Reinício do servidor para atualizar o PHP (falha PHP2Shell) | Leituras entregues depois do reinício | Paragens curtas, leituras entregues pela fila dos nós |
| T10 | 27/10/2026 | RF-S05, RF-S06 | S | Manutenção da OVH, das 18:33 até depois das 20:00 | O nó guarda as leituras na fila e envia-as quando o servidor volta, sem buracos | Fila do no1 com 86 leituras às 19:10. Sem buracos no no1 nem no no3 entre 18:20 e 20:30 (intervalo máximo de 21 s) |
| T11 | 30/10/2026 | RF-S08 | I | Registo do nó no4 com token próprio | O nó novo envia leituras com o seu token | Primeira leitura do no4 a 31/10 às 22:38:15 |
| T12 | 30/10/2026 | RF-S12 | U | Pedido a `ultimas.php` só com o token do no4 | Resposta `[]`, só com as leituras do no4 | Falhou com 403 `sem acesso`, porque o `ultimas.php` do servidor era uma versão antiga sem suporte a token. Corrigido no mesmo dia (ver T13) |
| T13 | 30/10/2026 | RF-S12 | U | Pedido a `ultimas.php` com o token do no4, antes de o nó enviar | Resposta `[]`, sem leituras de outros nós | `[]` |
| T14 | 30/10/2026 | RF-S11 | U | Pedido a `ultimas.php` com a chave de administrador, depois da correção do T12 | Devolve as leituras de todos os nós | Devolve todos os nós |
| T15 | 30/10/2026 | Segurança | S | `php -v` dentro do contentor `web` | PHP 8.3.36 ou superior (correção da PHP2Shell) | PHP 8.3.36 |
| T16 | 30/10/2026 | Segurança | S | Permissões do ficheiro `.env` no servidor | Só o dono lê e escreve | `-rw-------` |
| T17 | 30/10/2026 | RF-S05 | S | Procura de leituras repetidas na exportação da base de dados (118 492 leituras) | Nenhuma leitura repetida | 0 repetidas |
| T18 | 01/11/2026 | RF-S02 | I | Nó no1 com INA219 e firmware v4 a enviar `corrente_ma` | Resposta 200 e corrente guardada | Resposta 200. Corrente 0,0 mA com o LED apagado |
| T19 | 01/11/2026 | Medição | I | LED a 100% (sensor de luz tapado) e a 70% (luz entre 50 e 150 lux), corrente lida pelo INA219 | Perto de 5,9 mA a 100% (3,3 V, LED vermelho com cerca de 2 V, resistência de 220 ohm) e perto de 3,9 mA a 70% | 5,6 mA a 100%, cerca de 18,5 mW. Entre 3,4 e 4,2 mA a 70%, em 10 leituras |
| T20 | 03/11/2026 | RF-S13, RF-S14 | S | Consumo diário do no1 estimado a partir do `led_pct` (potência de 17,9 mW a 100%, obtida da corrente média medida de 5,41 mA a 3,3 V) comparado com o consumo medido pelo INA219 (corrente × 3,3 V), excluindo leituras com `luz_raw` negativo | Diferença pequena entre o estimado e o medido | 01/11: 23,4 mWh estimados e 23,3 medidos (+0,5%). 02/11: 11,8 e 12,0 (−1,6%). Corrente média por nível: 2,45 mA a 40% (4 leituras), 3,71 mA a 70% (519) e 5,41 mA a 100% (144) |

## Testes por fazer

| ID | Requisito | Nível | Procedimento | Resultado esperado |
|---|---|---|---|---|
| T21 | RF-S01 | U | `POST` a `leituras.php` com um token errado | Resposta 401 e nada guardado |
| T22 | RF-S03 | U | `POST` sem o campo `ts` | Resposta 422 e nada guardado |
| T23 | RF-S04 | U | `POST` com `led_pct` igual a 150 | Resposta 422 e nada guardado |
| T24 | RF-S05 | U | O mesmo `POST` enviado duas vezes | Primeira resposta com `novas: 1`, segunda com `duplicadas: 1`. Um só registo |
| T25 | RF-S06 | I | Comparar `recebido_em` com `ts` nas leituras de 27/10 entre 18:33 e 20:00 | `recebido_em` posterior a `ts` nas leituras que vieram da fila |
| T26 | RNF-D02 | S | 100 envios seguidos com `curl -w "%{time_total}"` | Tempo médio abaixo de 500 ms |
| T27 | RNF-D04 | S | 10 pedidos seguidos a `ultimas.php` | Todos abaixo de 1 s |
| T28 | RF-S10, RNF-D05 | U | Pedido do histórico de um dia, depois de criado o `historico.php` | Todas as leituras desse dia, por ordem de hora, em menos de 2 s |
| T29 | RNF-D03 | S | 4 nós reais e 10 simulados a enviar durante 1 hora | Todas as leituras guardadas |
| T30 | RF-S05 | S | Teste controlado: parar o contentor `web` durante 15 min, desligar o nó da corrente a meio, voltar a ligar o nó e depois o servidor (firmware versão 3, fila na flash) | O nó recupera a fila da flash e envia-a. Só falta o intervalo em que esteve sem energia |
| T31 | Segurança | S | A partir de fora do servidor, tentar ligar à porta 3306 | Ligação recusada |
| T32 | Medição | I | LED a 40% (luz entre 150 e 300 lux), corrente lida pelo INA219 | Cerca de 2,2 mA, proporcional ao `led_pct` |

## Observações

- Os testes T05, T09 e T10 não foram provocados. Foram falhas do servidor e os resultados foram verificados nos dados guardados.
- As datas e os intervalos estão em hora de Lisboa. Na base de dados, o `ts` está em UTC.
