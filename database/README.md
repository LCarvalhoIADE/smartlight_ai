# Base de dados

Esquema MySQL (`schema.sql`), carregado automaticamente na primeira vez que o contentor da base de dados arranca.

- `nos`: um registo por nó, com o seu token e uma descrição.
- `leituras`: uma linha por divisão e por leitura. A chave única `(no_id, boot_id, seq, divisao)` impede leituras repetidas. As datas (`ts`) são em UTC, em segundos desde 1970 (formato Unix).