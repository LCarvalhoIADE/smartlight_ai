# Base de dados

Esquema MySQL (`schema.sql`), carregado automaticamente na primeira vez que o contentor da base de dados arranca.

- `nos`: um registo por nó, com o seu token, uma descrição, o tipo de sensor de luz (`sensor_luz`, que pode ser `lux`, `analogico` ou `digital`) e a localização ao nível da cidade (`latitude`, `longitude` e `fuso`), que vai servir para cruzar as leituras com a meteorologia.
- `leituras`: uma linha por divisão e por leitura. A chave única `(no_id, boot_id, seq, divisao)` impede leituras repetidas. As datas (`ts`) são em UTC, em segundos desde 1970 (formato Unix). A coluna `corrente_ma` guarda a corrente média do LED em mA, medida pelo INA219 e fica vazia nos nós sem esse sensor.
