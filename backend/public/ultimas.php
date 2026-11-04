<?php
// Devolve as últimas leituras. Com a chave de administrador vê todos os nós e com o token de um nó só vê esse nó.
// Com por_divisao=1 devolve só a última leitura de cada divisão.
require __DIR__ . '/db.php';
$n = max(1, min(200, (int)($_GET['n'] ?? 20)));
$pdo = ligar();
$no = $_GET['no_id'] ?? '';
$chave = getenv('ADMIN_KEY');
$admin = $chave && hash_equals($chave, $_GET['chave'] ?? '');
if (!$admin) {
    $tok = $_GET['token'] ?? '';
    if ($no === '' || $tok === '') resp(403, ['erro' => 'sem acesso']);
    $st = $pdo->prepare('SELECT token FROM nos WHERE no_id = ?');
    $st->execute([$no]);
    $r = $st->fetch();
    if (!$r || !hash_equals($r['token'], $tok)) resp(403, ['erro' => 'sem acesso']);
}
if (($_GET['por_divisao'] ?? '') === '1') {
    $filtro = $no !== '' ? 'WHERE no_id = ?' : '';
    $st = $pdo->prepare("SELECT l.no_id, l.divisao, l.ts, l.luz_raw, l.luz_pct, l.presenca, l.led_pct, l.corrente_ma, l.modo, n.sensor_luz FROM leituras l JOIN (SELECT no_id, divisao, MAX(id) AS id FROM leituras $filtro GROUP BY no_id, divisao) u ON u.id = l.id JOIN nos n ON n.no_id = l.no_id ORDER BY l.no_id, l.divisao");
    $st->execute($no !== '' ? [$no] : []);
} elseif ($no !== '') {
    $st = $pdo->prepare("SELECT l.no_id, l.divisao, l.ts, l.luz_raw, l.luz_pct, l.presenca, l.led_pct, l.corrente_ma, l.modo, n.sensor_luz FROM leituras l JOIN nos n ON n.no_id = l.no_id WHERE l.no_id = ? ORDER BY l.id DESC LIMIT $n");
    $st->execute([$no]);
} else {
    $st = $pdo->query("SELECT l.no_id, l.divisao, l.ts, l.luz_raw, l.luz_pct, l.presenca, l.led_pct, l.corrente_ma, l.modo, n.sensor_luz FROM leituras l JOIN nos n ON n.no_id = l.no_id ORDER BY l.id DESC LIMIT $n");
}
$linhas = $st->fetchAll();
$tz = new DateTimeZone('Europe/Lisbon');
foreach ($linhas as &$l) {
    $l['hora'] = (new DateTime('@' . $l['ts']))->setTimezone($tz)->format('Y-m-d H:i:s');
}
unset($l);
resp(200, $linhas);
