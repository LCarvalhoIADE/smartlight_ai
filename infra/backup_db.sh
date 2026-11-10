#!/bin/bash
# Cópia diária da base de dados, com 7 dias de histórico
set -euo pipefail

DIR=/home/ubuntu/backups
mkdir -p "$DIR"
F="$DIR/smartlight_$(date +%Y%m%d_%H%M).sql.gz"

docker exec vps-db-1 sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction smartlight' | gzip > "$F"
chmod 600 "$F"
find "$DIR" -name 'smartlight_*.sql.gz' -mtime +7 -delete
