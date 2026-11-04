<?php
// Devolve as leituras de um nó entre duas datas (de e ate, em segundos Unix UTC), por omissão as últimas 24 horas.
// Aceita a chave de administrador ou o token do próprio nó. Responde com os dados do nó e a lista de leituras.
require __DIR__ . '/db.php';
$no = $_GET['no_id'] ?? '';
if ($no === '') resp(422, ['erro' => 'falta o parametro no_id']);
$pdo = ligar();
$st = $pdo->prepare('SELECT no_id, token, descricao, sensor_luz, latitude, longitude, fuso FROM nos WHERE no_id = ?');
$st->execute([$no]);
$n = $st->fetch();
$chave = getenv('ADMIN_KEY');
$admin = $chave && hash_equals($chave, $_GET['chave'] ?? '');
if (!$admin) {
    $tok = $_GET['token'] ?? '';
    if ($tok === '' || !$n || !hash_equals($n['token'], $tok)) resp(403, ['erro' => 'sem acesso']);
}
if (!$n) resp(404, ['erro' => 'no nao encontrado']);
$int = function (string $nome, int $omissao) {
    if (!isset($_GET[$nome]) || $_GET[$nome] === '') return $omissao;
    if (!preg_match('/^\d{1,12}$/', $_GET[$nome])) resp(422, ['erro' => "$nome invalido"]);
    return (int)$_GET[$nome];
};
$ate = $int('ate', time());
$de = $int('de', $ate - 86400);
if ($de > $ate) resp(422, ['erro' => 'de tem de ser menor ou igual a ate']);
$limite = max(1, min(10000, $int('limite', 1000)));
$desloca = $int('desloca', 0);
$sql = 'SELECT divisao, ts, luz_raw, luz_pct, presenca, led_pct, corrente_ma, modo FROM leituras WHERE no_id = ? AND ts BETWEEN ? AND ?';
$par = [$no, $de, $ate];
$div = $_GET['divisao'] ?? '';
if ($div !== '') {
    $sql .= ' AND divisao = ?';
    $par[] = $div;
}
// Pede mais uma linha do que o limite para saber se há mais páginas
$sql .= ' ORDER BY ts, id LIMIT ' . ($limite + 1) . ' OFFSET ' . $desloca;
$st = $pdo->prepare($sql);
$st->execute($par);
$linhas = $st->fetchAll();
$mais = count($linhas) > $limite;
if ($mais) array_pop($linhas);
resp(200, [
    'no' => [
        'no_id' => $n['no_id'],
        'descricao' => $n['descricao'],
        'sensor_luz' => $n['sensor_luz'],
        'latitude' => $n['latitude'] === null ? null : (float)$n['latitude'],
        'longitude' => $n['longitude'] === null ? null : (float)$n['longitude'],
        'fuso' => $n['fuso'],
    ],
    'de' => $de,
    'ate' => $ate,
    'mais' => $mais,
    'leituras' => $linhas,
]);
