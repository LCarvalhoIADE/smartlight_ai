# Dashboard

Página web onde se consulta o estado da iluminação de cada casa. Funciona no computador e no telemóvel (testada a 360 píxeis de largura, sem deslocamento horizontal).

## O que mostra

- **As casas agrupadas por país**, com a bandeira e a hora local de cada país.
- **Cada casa como um desenho**, com telhado, chaminé e paredes numa cor própria. Cada divisão é uma sala do desenho, que fica amarela com a intensidade do LED: apagada a 0 %, amarelo forte a 100 %.
- **Em cada divisão:** o nome, a intensidade do LED e um ícone de pessoa quando há presença.
- **O estado da comunicação de cada casa:** «A comunicar» (círculo cheio) ou «Sem comunicação há X min» (quadrado vazio, a vermelho). O estado nunca é indicado só pela cor. Uma casa fica sem comunicação quando passa mais tempo sem enviar leituras do que o valor de `offline_s` (60 s por omissão).
- **Divisões paradas:** as divisões sem leituras há mais de 24 horas ficam escondidas. Se a casa estiver toda parada, mostra-se tudo, esbatido, para se ver que está offline.
- **O detalhe da divisão escolhida** (carregando na sala do desenho, ou com o teclado):
  - os valores da última leitura: presença, LED, luz ambiente e modo;
  - um gráfico das últimas 24 horas com a presença, o LED e a luz ambiente, com as horas na hora local da casa;
  - o consumo de hoje e a poupança.
- **A luz ambiente no formato de cada sensor:** em lux, em percentagem (sensores analógicos, 0 a 4095) ou claro/escuro (sensores digitais, em que 1 = escuro).
- A página atualiza-se sozinha a cada 15 segundos, ao mesmo ritmo a que os nós enviam leituras.

## Consumo e poupança

O consumo conta desde a meia-noite, na hora local da casa. Cada leitura conta durante o tempo até à leitura seguinte, no máximo 60 s, para que uma falha de comunicação não conte como luz acesa.

- **No nó 1:** potência = 3,3 V × corrente medida pelo INA219.
- **Nos outros nós:** potência estimada = 17,9 mW × intensidade do LED / 100.
- **Poupança (RF26):** diferença entre o consumo que a luz teria a 100 % durante o tempo em que esteve acesa e o consumo registado. O tempo com a luz apagada não entra na comparação.

## Ficheiros

| Ficheiro | Função |
|---|---|
| `index.php` | Estrutura da página: cabeçalho, zona das casas e painel de detalhe. |
| `dados.php` | Pede os dados à API do servidor e devolve-os à página em JSON (`?o=estado`, `?o=nos` ou `?o=historico`). |
| `exemplo.php` | Dados inventados de quatro casas, para testar sem servidor. |
| `assets/painel.js` | Desenha as casas, o detalhe, o gráfico e o consumo, e atualiza a página. |
| `assets/style.css` | Aspeto da página. Paleta azul, com o amarelo só onde há luz acesa. |
| `config.php.example` | Modelo da configuração. |

## De onde vêm os dados

O dashboard não acede diretamente à base de dados. O `dados.php` faz três pedidos ao servidor, enviando a chave de leitura no cabeçalho `X-Chave`:

| Pedido da página | API do servidor | Para quê |
|---|---|---|
| `dados.php?o=nos` | `nos.php` | País, fuso horário e tipo de sensor de cada casa |
| `dados.php` (estado) | `ultimas.php?por_divisao=1` | Última leitura de cada divisão |
| `dados.php?o=historico` | `historico.php` | Leituras das últimas 24 horas de uma divisão (até 10 000) |

A chave fica só no servidor do dashboard: o browser nunca a vê.

## Configuração

1. Copiar `config.php.example` para `config.php`. Este ficheiro não vai para o repositório.
2. Preencher `url_base` com o endereço do servidor (sem barra no fim) e `chave` com a chave de leitura.
3. Para testar sem servidor, pôr `exemplo` a `true`.
4. Para testar no PC: `php -S localhost:8000 -t dashboard`, a partir da pasta do repositório.

A disposição das divisões dentro de cada casa está em `PLANTAS`, no início do `painel.js`. As divisões que não estão lá são arrumadas automaticamente.

## Tecnologia

- PHP no servidor, para fazer os pedidos à API.
- HTML, CSS e JavaScript na página, sem frameworks. As casas são desenhadas em SVG.
- Chart.js para o gráfico, carregado a partir de uma CDN.
- Tipos de letra Fraunces e Atkinson Hyperlegible (Google Fonts).

## Ainda falta

- O início de sessão.
- A lista das casas sem comunicação (RF40). Por agora, cada casa mostra o seu estado.
- A escolha do período do histórico (RF15): por agora, só as últimas 24 horas.
- A meteorologia, as previsões da IA e os alertas.
- A disposição real das divisões das casas 1, 3 e 4 em `PLANTAS`.

## Estado

Em desenvolvimento. A primeira versão está prevista para o protótipo de 30 de novembro.
