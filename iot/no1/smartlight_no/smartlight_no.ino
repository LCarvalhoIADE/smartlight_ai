// SmartLight, firmware do nó 1, versão 1.
// Lê a presença e a luz, controla o LED e envia as leituras por HTTPS, com fila quando não há ligação.
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include "config.h"
#if SENSOR_LUZ == 0
#include <Wire.h>
#include <BH1750.h>
BH1750 sensorLuz;
#endif

#ifndef USAR_HTTPS
#define USAR_HTTPS 0
#endif
// Pinos por omissão para o ESP32 DevKit V1. Para outra placa, definir no config.h.
#ifndef PIN_PIR
#define PIN_PIR 27
#endif
#ifndef PIN_LUZ_DIG
#define PIN_LUZ_DIG 34
#endif
#ifndef PIN_LUZ_ANA
#define PIN_LUZ_ANA 35
#endif
#ifndef PIN_LED
#define PIN_LED 5
#endif
#ifndef DIVISAO
#define DIVISAO "sala"
#endif
#ifndef PIN_SDA
#define PIN_SDA 21
#endif
#ifndef PIN_SCL
#define PIN_SCL 22
#endif
const int pirPin = PIN_PIR;
const int luzDigPin = PIN_LUZ_DIG;
const int potPin = PIN_LUZ_ANA;
const int ledPin = PIN_LED;
const unsigned long TIMEOUT_MS = 10000;
const unsigned long LEITURA_MS = 15000;
const unsigned long RECONNECT_MS = 20000;
const unsigned long REENVIO_MS = 15000;

struct Leitura {
  uint32_t ts;
  uint32_t seq;
  int16_t luzRaw;
  uint8_t presenca;
  uint8_t ledPct;
};
const int FILA_MAX = 5760;
Leitura* fila = nullptr;
int filaCap = 0, filaIni = 0, filaN = 0;
unsigned long perdidas = 0;
unsigned long rejeitadas = 0;

unsigned long ultimoMovimento = 0, ultimaLeitura = 0, ultimaTentativaWifi = 0, ultimaTentativaEnvio = 0;
unsigned long esperaEnvio = 0;
bool temPresenca = false;
bool ntpIniciado = false;
long bootId = 0;
uint32_t proximoSeq = 0;

int nivelBrilho(int luz) {
  if (luz > 3000) return 0;
  if (luz > 2000) return 102;
  if (luz > 1000) return 178;
  return 255;
}
int nivelBrilhoLux(float lux) {
  if (lux > 300) return 0;
  if (lux > 150) return 102;
  if (lux > 50) return 178;
  return 255;
}

void ligarWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(200);
  WiFi.setScanMethod(WIFI_ALL_CHANNEL_SCAN);
  WiFi.setSortMethod(WIFI_CONNECT_AP_BY_SIGNAL);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  ultimaTentativaWifi = millis();
}

void lerLuz(int &raw, int &brilho255) {
#if SENSOR_LUZ == 0
  float lux = sensorLuz.readLightLevel();
  raw = (int)lux; brilho255 = nivelBrilhoLux(lux);
#elif SENSOR_LUZ == 1
  raw = digitalRead(luzDigPin) == HIGH ? 1 : 0;
  brilho255 = raw ? 255 : 0;
#elif SENSOR_LUZ == 3
  raw = analogRead(potPin); brilho255 = nivelBrilho(raw);
#else
  raw = -1; brilho255 = 255;
#endif
}

void guardar(const Leitura &l) {
  if (filaCap == 0) return;
  if (filaN == filaCap) { filaIni = (filaIni + 1) % filaCap; filaN--; perdidas++; }
  fila[(filaIni + filaN) % filaCap] = l;
  filaN++;
}

void registar(int raw, int brilho255) {
  time_t agora = time(nullptr);
  if (agora < 1700000000) { Serial.println("Nao regista: hora por acertar (NTP)"); return; }
  if (bootId == 0) bootId = (long)agora;
  Leitura l;
  l.ts = (uint32_t)agora;
  l.seq = proximoSeq++;
  l.luzRaw = (int16_t)raw;
  l.presenca = temPresenca ? 1 : 0;
  l.ledPct = (uint8_t)map(brilho255, 0, 255, 0, 100);
  guardar(l);
}

int enviarUma(const Leitura &l) {
  char amb[64];
#if SENSOR_LUZ == 0
  snprintf(amb, sizeof amb, "{\"luz_raw\":%d,\"luz_pct\":%d}", l.luzRaw, constrain(l.luzRaw / 10, 0, 100));
#elif SENSOR_LUZ == 1
  snprintf(amb, sizeof amb, "{\"luz_raw\":%d}", l.luzRaw);
#elif SENSOR_LUZ == 3
  snprintf(amb, sizeof amb, "{\"luz_raw\":%d,\"luz_pct\":%d}", l.luzRaw, l.luzRaw * 100 / 4095);
#else
  strcpy(amb, "{}");
#endif
  char corpo[400];
  snprintf(corpo, sizeof corpo,
    "{\"no_id\":\"%s\",\"boot_id\":%ld,\"seq\":%lu,\"ts\":%lu,\"ambiente\":%s,"
    "\"divisoes\":[{\"id\":\"%s\",\"presenca\":%s,\"led_pct\":%d,\"modo\":\"auto\"}]}",
    NO_ID, bootId, (unsigned long)l.seq, (unsigned long)l.ts, amb, DIVISAO,
    l.presenca ? "true" : "false", (int)l.ledPct);
#if USAR_HTTPS
  WiFiClientSecure client;
  client.setInsecure();      // ligação cifrada, sem verificação do certificado
  HTTPClient http;
  http.begin(client, SERVER_URL);
#else
  HTTPClient http;
  http.begin(SERVER_URL);
#endif
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Token", NO_TOKEN);
  int code = http.POST((uint8_t*)corpo, strlen(corpo));
  http.end();
  return code;
}

void tratarFila() {
  if (filaN == 0 || WiFi.status() != WL_CONNECTED) return;
  if (millis() - ultimaTentativaEnvio < esperaEnvio) return;
  const Leitura &l = fila[filaIni];
  int code = enviarUma(l);
  ultimaTentativaEnvio = millis();
  Serial.printf("POST seq=%lu -> %d (fila=%d)\n", (unsigned long)l.seq, code, filaN);
  if (code == 200 || code == 400 || code == 422) {
    if (code != 200) { rejeitadas++; Serial.println("Leitura recusada pelo servidor, descartada"); }
    filaIni = (filaIni + 1) % filaCap;
    filaN--;
    esperaEnvio = 0;
  } else {
    esperaEnvio = REENVIO_MS;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(pirPin, INPUT);
  pinMode(luzDigPin, INPUT);
  ledcAttach(ledPin, 5000, 8);
#if SENSOR_LUZ == 0
  Wire.begin(PIN_SDA, PIN_SCL);
  sensorLuz.begin();
#endif
  for (filaCap = FILA_MAX; filaCap >= 100; filaCap /= 2) {
    fila = (Leitura*)malloc(sizeof(Leitura) * filaCap);
    if (fila) break;
  }
  if (!fila) filaCap = 0;
  Serial.printf("Fila offline: %d leituras (%u bytes)\n", filaCap, (unsigned)(sizeof(Leitura) * filaCap));

  WiFi.onEvent([](WiFiEvent_t e, WiFiEventInfo_t info) {
    Serial.printf("Wi-Fi caiu, motivo %d\n", info.wifi_sta_disconnected.reason);
  }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.onEvent([](WiFiEvent_t e, WiFiEventInfo_t info) {
    Serial.print("Wi-Fi ligado, IP ");
    Serial.println(WiFi.localIP());
  }, ARDUINO_EVENT_WIFI_STA_GOT_IP);
  ligarWifi();
  Serial.println("A ligar ao Wi-Fi em segundo plano...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED && millis() - ultimaTentativaWifi > RECONNECT_MS) {
    Serial.printf("Sem Wi-Fi (estado %d), a tentar de novo...\n", WiFi.status());
    ligarWifi();
  }
  if (WiFi.status() == WL_CONNECTED && !ntpIniciado) { configTime(0, 0, "pool.ntp.org"); ntpIniciado = true; }

  if (digitalRead(pirPin) == HIGH) { ultimoMovimento = millis(); temPresenca = true; }
  if (temPresenca && millis() - ultimoMovimento > TIMEOUT_MS) temPresenca = false;
  int raw, b;
  lerLuz(raw, b);
  int brilho = temPresenca ? b : 0;
  ledcWrite(ledPin, brilho);

  if (millis() - ultimaLeitura > LEITURA_MS) {
    ultimaLeitura = millis();
    registar(raw, brilho);
    Serial.printf("presenca=%d luz=%d brilho=%d | fila=%d perdidas=%lu recusadas=%lu\n",
                  temPresenca, raw, brilho, filaN, perdidas, rejeitadas);
  }

  tratarFila();
  delay(200);
}
