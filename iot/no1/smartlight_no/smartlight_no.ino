// SmartLight, firmware do nó 1, versão 3 com a fila guardada na flash.
// Lê a presença e a luz, controla o LED e envia as leituras por HTTPS, com fila quando não há ligação.
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include "config.h"
#include <LittleFS.h>
#ifndef USAR_OLED
#define USAR_OLED 0
#endif
#if SENSOR_LUZ == 0 || USAR_OLED
#include <Wire.h>
#endif
#if SENSOR_LUZ == 0
#include <BH1750.h>
BH1750 sensorLuz;
#endif

#ifndef USAR_HTTPS
#define USAR_HTTPS 0
#endif
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

// Limites da regra de luz. Acima de *_APAGA o LED fica apagado. Com menos luz passa por 40%, 70% e 100%.
#ifndef LUX_APAGA
#define LUX_APAGA 300
#endif
#ifndef LUX_40
#define LUX_40 150
#endif
#ifndef LUX_70
#define LUX_70 50
#endif
#ifndef ANA_APAGA
#define ANA_APAGA 3000
#endif
#ifndef ANA_40
#define ANA_40 2000
#endif
#ifndef ANA_70
#define ANA_70 1000
#endif

#ifndef OLED_SH1106
#define OLED_SH1106 0
#endif
#ifndef OLED_SO_PRESENCA
#define OLED_SO_PRESENCA 1
#endif
#if USAR_OLED
#include <U8g2lib.h>
#if OLED_SH1106
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, PIN_SCL, PIN_SDA);
#else
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, PIN_SCL, PIN_SDA);
#endif
#endif
const int pirPin = PIN_PIR;
const int luzDigPin = PIN_LUZ_DIG;
const int potPin = PIN_LUZ_ANA;
const int ledPin = PIN_LED;
const unsigned long TIMEOUT_MS = 10000;
const unsigned long LEITURA_MS = 15000;
const unsigned long RECONNECT_MS = 20000;
const unsigned long REENVIO_MS = 15000;
const unsigned long ECRA_MS = 1000;

struct Leitura {
  uint32_t ts;
  uint32_t seq;
  uint32_t boot;
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

#ifndef FILA_FLASH
#define FILA_FLASH 1
#endif
const char* FICH_FILA = "/fila.bin";
const char* FICH_TEMP = "/fila.tmp";
const uint32_t FILA_MAGIC = 0x534C4633;
const unsigned long GRAVAR_MS = 300000;
const int GRAVAR_MIN = 20;
bool flashOk = false, ficheiroExiste = false;
unsigned long ultimaGravacao = 0;
int luzAtual = 0, brilhoAtual = 0;
unsigned long ultimoEcra = 0;

int nivelBrilho(int luz) {
  if (luz > ANA_APAGA) return 0;
  if (luz > ANA_40) return 102;
  if (luz > ANA_70) return 178;
  return 255;
}
int nivelBrilhoLux(float lux) {
  if (lux > LUX_APAGA) return 0;
  if (lux > LUX_40) return 102;
  if (lux > LUX_70) return 178;
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
  l.boot = (uint32_t)bootId;
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
    NO_ID, (long)l.boot, (unsigned long)l.seq, (unsigned long)l.ts, amb, DIVISAO,
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

#if USAR_OLED
void atualizarEcra() {
  if (OLED_SO_PRESENCA && !temPresenca) { oled.setPowerSave(1); return; }
  oled.setPowerSave(0);
  char l[32];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x10_tf);
  snprintf(l, sizeof l, "SmartLight %s %s", NO_ID, DIVISAO);
  oled.drawUTF8(0, 10, l);
  oled.drawHLine(0, 13, 128);
#if SENSOR_LUZ == 0
  snprintf(l, sizeof l, "Luz: %d lux", luzAtual);
#elif SENSOR_LUZ == 1
  snprintf(l, sizeof l, "Luz: %s", luzAtual ? "escuro" : "claro");
#elif SENSOR_LUZ == 3
  snprintf(l, sizeof l, "Luz: %d", luzAtual);
#else
  snprintf(l, sizeof l, "Luz: sem sensor");
#endif
  oled.drawUTF8(0, 25, l);
  snprintf(l, sizeof l, "Presença: %s", temPresenca ? "sim" : "não");
  oled.drawUTF8(0, 36, l);
  snprintf(l, sizeof l, "LED: %d%%", (int)map(brilhoAtual, 0, 255, 0, 100));
  oled.drawUTF8(0, 47, l);
  time_t agora = time(nullptr);
  struct tm t;
  localtime_r(&agora, &t);
  if (agora > 1700000000) snprintf(l, sizeof l, "%s  Fila %d  %02d:%02d",
      WiFi.status() == WL_CONNECTED ? "Wi-Fi" : "Sem Wi-Fi", filaN, t.tm_hour, t.tm_min);
  else snprintf(l, sizeof l, "%s  Fila %d",
      WiFi.status() == WL_CONNECTED ? "Wi-Fi" : "Sem Wi-Fi", filaN);
  oled.drawUTF8(0, 60, l);
  oled.sendBuffer();
}
#endif

void tratarFila() {
  if (filaN == 0 || WiFi.status() != WL_CONNECTED) return;
  if (millis() - ultimaTentativaEnvio < esperaEnvio) return;
  const Leitura &l = fila[filaIni];
  int code = enviarUma(l);
  ultimaTentativaEnvio = millis();
  Serial.printf("POST seq=%lu -> %d (fila=%d)\n", (unsigned long)l.seq, code, filaN);
  if (code == 200 || code == 400 || code == 422) {
    // 200 aceite, nova ou duplicada. 400 e 422 leitura inválida, que sai da fila.
    if (code != 200) { rejeitadas++; Serial.println("Leitura recusada pelo servidor, descartada"); }
    filaIni = (filaIni + 1) % filaCap;
    filaN--;
    esperaEnvio = 0;
  } else {
    esperaEnvio = REENVIO_MS;
  }
}

#if FILA_FLASH
// Escreve num ficheiro temporário e só depois o renomeia, para que um corte de energia não estrague a cópia anterior.
void gravarFila() {
  File f = LittleFS.open(FICH_TEMP, "w");
  if (!f) { Serial.println("Flash: erro ao abrir o ficheiro"); return; }
  uint32_t cab[2] = { FILA_MAGIC, (uint32_t)filaN };
  f.write((const uint8_t*)cab, sizeof cab);
  int primeira = min(filaN, filaCap - filaIni);
  f.write((const uint8_t*)&fila[filaIni], sizeof(Leitura) * primeira);
  if (filaN > primeira) f.write((const uint8_t*)&fila[0], sizeof(Leitura) * (filaN - primeira));
  f.close();
  LittleFS.remove(FICH_FILA);
  LittleFS.rename(FICH_TEMP, FICH_FILA);
  ficheiroExiste = true;
  Serial.printf("Flash: fila copiada (%d leituras)\n", filaN);
}

void carregarFila() {
  if (!LittleFS.exists(FICH_FILA)) return;
  ficheiroExiste = true;
  File f = LittleFS.open(FICH_FILA, "r");
  if (!f) return;
  uint32_t cab[2] = {0, 0};
  if (f.read((uint8_t*)cab, sizeof cab) != sizeof cab || cab[0] != FILA_MAGIC) {
    f.close(); Serial.println("Flash: ficheiro da fila inválido, ignorado"); return;
  }
  int n = 0;
  Leitura l;
  while (n < (int)cab[1] && f.read((uint8_t*)&l, sizeof l) == sizeof l) { guardar(l); n++; }
  f.close();
  Serial.printf("Flash: recuperadas %d leituras do arranque anterior\n", n);
}

void tratarFlash() {
  if (!flashOk) return;
  if (filaN >= GRAVAR_MIN && millis() - ultimaGravacao > GRAVAR_MS) {
    ultimaGravacao = millis();
    gravarFila();
  } else if (filaN == 0 && ficheiroExiste) {
    LittleFS.remove(FICH_FILA);
    ficheiroExiste = false;
    Serial.println("Flash: fila enviada, ficheiro apagado");
  }
}
#endif

void setup() {
  Serial.begin(115200);
  pinMode(pirPin, INPUT);
  pinMode(luzDigPin, INPUT);
  ledcAttach(ledPin, 5000, 8);
#if SENSOR_LUZ == 0 || USAR_OLED
  Wire.begin(PIN_SDA, PIN_SCL);
#endif
#if SENSOR_LUZ == 0
  sensorLuz.begin();
#endif
#if USAR_OLED
  oled.begin();
  oled.setFont(u8g2_font_6x10_tf);
  oled.drawUTF8(0, 10, "SmartLight");
  oled.drawUTF8(0, 25, "A ligar ao Wi-Fi...");
  oled.sendBuffer();
#endif
  for (filaCap = FILA_MAX; filaCap >= 100; filaCap /= 2) {
    fila = (Leitura*)malloc(sizeof(Leitura) * filaCap);
    if (fila) break;
  }
  if (!fila) filaCap = 0;
  Serial.printf("Fila offline: %d leituras (%u bytes)\n", filaCap, (unsigned)(sizeof(Leitura) * filaCap));
#if FILA_FLASH
  flashOk = LittleFS.begin(true);
  if (flashOk) carregarFila();
  else Serial.println("Flash indisponível: fila só em RAM");
#endif

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
  if (WiFi.status() == WL_CONNECTED && !ntpIniciado) {
    configTime(0, 0, "pool.ntp.org");
    setenv("TZ", "WET0WEST,M3.5.0/1,M10.5.0", 1);
    tzset();
    ntpIniciado = true;
  }

  // Regra local da luz
  if (digitalRead(pirPin) == HIGH) { ultimoMovimento = millis(); temPresenca = true; }
  if (temPresenca && millis() - ultimoMovimento > TIMEOUT_MS) temPresenca = false;
  int raw, b;
  lerLuz(raw, b);
  int brilho = temPresenca ? b : 0;
  ledcWrite(ledPin, brilho);
  luzAtual = raw;
  brilhoAtual = brilho;

  if (millis() - ultimaLeitura > LEITURA_MS) {
    ultimaLeitura = millis();
    registar(raw, brilho);
    Serial.printf("presenca=%d luz=%d brilho=%d | fila=%d perdidas=%lu recusadas=%lu\n",
                  temPresenca, raw, brilho, filaN, perdidas, rejeitadas);
  }

  tratarFila();
#if FILA_FLASH
  tratarFlash();
#endif

#if USAR_OLED
  if (millis() - ultimoEcra > ECRA_MS) { ultimoEcra = millis(); atualizarEcra(); }
#endif
  delay(200);
}
