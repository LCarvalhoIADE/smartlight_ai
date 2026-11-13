# Nó 1

Firmware do nó 1, com sensor de luz BH1750. Lê a presença e a luz, controla o LED com a regra local e envia as leituras por HTTPS para o servidor, com fila na memória para quando não há ligação. Tem um ecrã OLED opcional com o estado do nó e os limites de luz definíveis no `config.h`.

## Ligações por omissão (ESP32 DevKit)

| Componente | Pino |
|---|---|
| LED (resistência de 220 ohm) | GPIO5 |
| Sensor PIR (OUT) | GPIO27 |
| Módulo de luz digital (DO) | GPIO34 |
| Módulo de luz analógico | GPIO35 |
| BH1750 e ecrã OLED (SDA e SCL) | GPIO21 e GPIO22 |

## Configuração

Copiar `smartlight_no/config.h.example` para `smartlight_no/config.h` e preencher o Wi-Fi, o endereço do servidor, o identificador e o token do nó. O `config.h` tem credenciais e por isso fica só no computador de quem grava a placa, excluído do repositório pelo `.gitignore`.

## Compilar

Arduino IDE com o core Arduino-ESP32 3.x. A biblioteca BH1750 só é necessária com `SENSOR_LUZ 0` e a biblioteca U8g2 com `USAR_OLED 1`. Abrir `smartlight_no/smartlight_no.ino`.
