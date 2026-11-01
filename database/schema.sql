CREATE TABLE IF NOT EXISTS nos (
  no_id VARCHAR(32) PRIMARY KEY,
  token VARCHAR(64) NOT NULL,
  descricao VARCHAR(100) NULL,
  sensor_luz VARCHAR(16) NULL,
  latitude DECIMAL(5,2) NULL,
  longitude DECIMAL(5,2) NULL,
  fuso VARCHAR(40) NULL
);
CREATE TABLE IF NOT EXISTS leituras (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  no_id VARCHAR(32) NOT NULL,
  boot_id BIGINT NOT NULL,
  seq BIGINT NOT NULL,
  divisao VARCHAR(32) NOT NULL,
  ts BIGINT NOT NULL,
  recebido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  luz_raw INT NULL,
  luz_pct INT NULL,
  presenca TINYINT NOT NULL,
  led_pct INT NOT NULL,
  corrente_ma DECIMAL(6,1) NULL,
  modo VARCHAR(16) NOT NULL,
  UNIQUE KEY uq_leitura (no_id, boot_id, seq, divisao),
  KEY idx_no_ts (no_id, ts),
  FOREIGN KEY (no_id) REFERENCES nos(no_id)
);
-- Sem nós por omissão. Cada nó é criado à mão, com um token próprio.
