# Infraestrutura

Três contentores Docker numa máquina virtual na cloud:

- `db`: MySQL, sem porta publicada, por isso não é acessível a partir da Internet
- `web`: PHP com Apache, que serve a API
- `caddy`: proxy HTTPS, com certificado automático

## Arranque

1. Copiar `.env.example` para `.env` e preencher.
2. `sudo docker compose up -d --build`

## Manutenção

Para atualizar as imagens para as últimas versões de correções:

    sudo docker compose pull
    sudo docker compose build --pull
    sudo docker compose up -d

| Data | Intervenção |
|---|---|
| 25/10/2026 | PHP atualizado de 8.3.35 para 8.3.36, para corrigir a falha PHP2Shell (CVE-2026-109618 e CVE-2026-109619). Sistema Ubuntu atualizado e servidor reiniciado. Pasta pública verificada, sem ficheiros estranhos. |