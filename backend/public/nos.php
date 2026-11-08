<?php
// Lista os nós registados com descrição, fuso, país e coordenadas. Exige uma chave de acesso, no cabeçalho X-Chave ou no parâmetro chave do URL.
require __DIR__ . '/db.php';
$ok = false;
foreach (['ADMIN_KEY', 'LEITURA_KEY'] as $v) {
    $k = getenv($v);
    if ($k && hash_equals($k, chave_pedido())) $ok = true;
}
if (!$ok) resp(403, ['erro' => 'sem acesso']);
$st = ligar()->query('SELECT no_id, descricao, sensor_luz, fuso, pais, latitude, longitude FROM nos ORDER BY no_id');
resp(200, ['nos' => $st->fetchAll()]);
