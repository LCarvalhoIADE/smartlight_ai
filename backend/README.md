# Servidor e API

API em PHP que recebe as leituras dos nós e as disponibiliza ao dashboard e à IA.

| Ficheiro | Função |
|---|---|
| `public/leituras.php` | `POST`: recebe uma leitura de um nó (cabeçalho `X-Token`, corpo JSON), valida-a e guarda-a. Ignora leituras repetidas. Aceita a corrente do LED (`corrente_ma`) nos nós com INA219. |
| `public/ultimas.php` | `GET`: devolve as últimas leituras. Com a chave de administrador vê todos os nós, com o token de um nó só vê esse nó. Cada leitura inclui o tipo de sensor de luz do nó. Com `por_divisao=1` devolve só a última leitura de cada divisão. |
| `public/historico.php` | `GET`: devolve as leituras de um nó entre duas datas, com a localização, o fuso e o tipo de sensor de luz do nó. Mesmo controlo de acesso do `ultimas.php`. |
| `public/nos.php` | `GET`: devolve a lista dos nós, com a descrição, o fuso, o país e as coordenadas. Só aceita chave, não o token de um nó. |
| `public/db.php` | Ligação à base de dados e resposta em JSON. As credenciais vêm de variáveis de ambiente. |
| `Dockerfile` | Imagem `php:8.3-apache` com a extensão `pdo_mysql`. |

## Respostas do envio de leituras

| Código | Significado |
|---|---|
| 200 | Leitura aceite (nova ou repetida) |
| 400 | JSON inválido |
| 401 | Token inválido |
| 405 | Método diferente de `POST` |
| 422 | Campos em falta ou fora dos limites |

## Consulta de leituras

O `ultimas.php` e o `historico.php` aceitam uma chave (`chave`), que pode ser a de administrador ou a de leitura, ou então o token do próprio nó (`no_id` e `token`). As duas chaves dão acesso a todos os nós e só permitem consultar.

### `ultimas.php`

| Parâmetro | Significado |
|---|---|
| `no_id` | Limita a um nó. Obrigatório com o token de um nó |
| `n` | Número de leituras, 20 por omissão e 200 no máximo |
| `por_divisao` | Com o valor `1` devolve uma leitura por nó e divisão, a última guardada, e ignora `n` |

### `historico.php`

| Parâmetro | Significado |
|---|---|
| `no_id` | Nó a consultar. Obrigatório |
| `de`, `ate` | Início e fim do período, em segundos Unix (UTC). Por omissão, as últimas 24 horas |
| `divisao` | Filtra uma divisão |
| `limite` | Número de leituras, 1000 por omissão e 10000 no máximo |
| `desloca` | Leituras a saltar, para pedir as páginas seguintes. O campo `mais` indica se há mais leituras |

As leituras vêm da mais antiga para a mais recente.

A resposta tem os campos `no` (`no_id`, `descricao`, `sensor_luz`, `latitude`, `longitude` e `fuso`), `de`, `ate`, `mais` e `leituras`.

### `nos.php`

Não tem parâmetros além da chave. Devolve a lista dos nós registados, ordenada por `no_id`, no campo `nos`. Cada nó traz `no_id`, `descricao`, `sensor_luz`, `fuso`, `pais`, `latitude` e `longitude`. Só aceita a chave de administrador ou a de leitura, e não aceita o token de um nó.

## Respostas da consulta

| Código | Significado |
|---|---|
| 200 | Pedido aceite |
| 403 | Sem chave de administrador nem token válido do nó |
| 404 | Nó não encontrado (`historico.php`, com uma chave válida) |
| 422 | Parâmetro em falta ou inválido, por exemplo `de` maior que `ate` |
