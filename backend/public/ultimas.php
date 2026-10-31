<?php
// Todos os nós, com a chave de administrador: ultimas.php?chave=ADMIN_KEY
// Só um nó, com o token desse nó: ultimas.php?no_id=ID_DO_NO&token=TOKEN_DO_NO
// Opcional: &n= número de leituras devolvidas (20 por omissão, 200 no máximo)
require __DIR__ . '/db.php';
$n = max(1, min(200, (int)($_GET['n'] ?? 20)));
$pdo = ligar();
$no = $_GET['no_id'] ?? '';
$chave = getenv('ADMIN_KEY');
$admin = $chave && hash_equals($chave, $_GET['chave'] ?? '');
if (!$admin) {
    // Sem chave de administrador: só com o token do próprio nó e só vê esse nó
    $tok = $_GET['token'] ?? '';
    if ($no === '' || $tok === '') resp(403, ['erro' => 'sem acesso']);
    $st = $pdo->prepare('SELECT token FROM nos WHERE no_id = ?');
    $st->execute([$no]);
    $r = $st->fetch();
    if (!$r || !hash_equals($r['token'], $tok)) resp(403, ['erro' => 'sem acesso']);
}
if ($no !== '') {
    $st = $pdo->prepare("SELECT no_id, divisao, ts, luz_raw, luz_pct, presenca, led_pct, modo FROM leituras WHERE no_id = ? ORDER BY id DESC LIMIT $n");
    $st->execute([$no]);
} else {
    $st = $pdo->query("SELECT no_id, divisao, ts, luz_raw, luz_pct, presenca, led_pct, modo FROM leituras ORDER BY id DESC LIMIT $n");
}
$linhas = $st->fetchAll();
// Acrescenta a hora legível (Lisboa). O ts continua igual, em UTC.
$tz = new DateTimeZone('Europe/Lisbon');
foreach ($linhas as &$l) {
    $l['hora'] = (new DateTime('@' . $l['ts']))->setTimezone($tz)->format('Y-m-d H:i:s');
}
unset($l);
resp(200, $linhas);
