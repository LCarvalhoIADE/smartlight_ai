

Página web onde se consulta o estado da iluminação de cada casa.

## O que vai mostrar:

- O estado atual de cada divisão: presença, intensidade do LED e luz ambiente.
- Que nós estão online e quais estão sem enviar leituras.
- O histórico das leituras num gráfico.
- Mais tarde, o consumo estimado, as previsões da IA e os alertas.

## De onde vêm os dados:

O dashboard não acede diretamente à base de dados. Pede as leituras à API do servidor, que devolve as últimas leituras de todos os nós.

## Tecnologia prevista:

- PHP no servidor, para o início de sessão e para fazer os pedidos à API.
- HTML, CSS e JavaScript na página, com um gráfico.
- A página tem de funcionar no computador e no telemóvel.

## Estado:

Em desenvolvimento. A primeira versão está prevista para o protótipo de 30 de novembro.