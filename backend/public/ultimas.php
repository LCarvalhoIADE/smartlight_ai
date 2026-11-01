<?php
// Com a chave de administrador devolve todos os nós, por exemplo ultimas.php?chave=ADMIN_KEY
// Com o token de um nó devolve só esse nó, por exemplo ultimas.php?no_id=ID_DO_NO&token=TOKEN_DO_NO
// O parâmetro opcional n define o número de leituras devolvidas, 20 por omissão e 200 no máximo
// Cada leitura inclui o tipo de sensor de luz do nó em sensor_luz, que pode ser lux, analogico ou digital
require __DIR__ . '/db.php';
$n = max(1, min(200, (int)($_GET['n'] ?? 20)));
$pdo = ligar();
$no = $_GET['no_id'] ?? '';
$chave = getenv('ADMIN_KEY');
$admin = $chave && hash_equals($chave, $_GET['chave'] ?? '');
if (!$admin) {
    // Sem a chave de administrador só se aceita o token do próprio nó e só se vê esse nó
    $tok = $_GET['token'] ?? '';
    if ($no === '' || $tok === '') resp(403, ['erro' => 'sem acesso']);
    $st = $pdo->prepare('SELECT token FROM nos WHERE no_id = ?');
    $st->execute([$no]);
    $r = $st->fetch();
    if (!$r || !hash_equals($r['token'], $tok)) resp(403, ['erro' => 'sem acesso']);
}
if ($no !== '') {
    $st = $pdo->prepare("SELECT l.no_id, l.divisao, l.ts, l.luz_raw, l.luz_pct, l.presenca, l.led_pct, l.corrente_ma, l.modo, n.sensor_luz FROM leituras l JOIN nos n ON n.no_id = l.no_id WHERE l.no_id = ? ORDER BY l.id DESC LIMIT $n");
    $st->execute([$no]);
} else {
    $st = $pdo->query("SELECT l.no_id, l.divisao, l.ts, l.luz_raw, l.luz_pct, l.presenca, l.led_pct, l.corrente_ma, l.modo, n.sensor_luz FROM leituras l JOIN nos n ON n.no_id = l.no_id ORDER BY l.id DESC LIMIT $n");
}
$linhas = $st->fetchAll();
// Acrescenta a hora legível em Lisboa. O ts continua igual, em UTC.
$tz = new DateTimeZone('Europe/Lisbon');
foreach ($linhas as &$l) {
    $l['hora'] = (new DateTime('@' . $l['ts']))->setTimezone($tz)->format('Y-m-d H:i:s');
}
unset($l);
resp(200, $linhas);
