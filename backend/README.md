# Servidor e API

API em PHP que recebe as leituras dos nós e as disponibiliza ao dashboard e à IA.

| Ficheiro | Função |
|---|---|
| `public/leituras.php` | `POST`: recebe uma leitura de um nó (cabeçalho `X-Token`, corpo JSON), valida-a e guarda-a. Ignora leituras repetidas. |
| `public/ultimas.php` | `GET`: devolve as últimas leituras. Com a chave de administrador vê todos os nós, com o token de um nó só vê esse nó. |
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
