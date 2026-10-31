<?php
// POST /leituras.php  (cabeçalho X-Token do nó, corpo JSON)
require __DIR__ . '/db.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') resp(405, ['erro' => 'usar POST']);

$j = json_decode(file_get_contents('php://input'), true);
if (!is_array($j)) resp(400, ['erro' => 'JSON invalido']);

foreach (['no_id', 'boot_id', 'seq', 'ts', 'divisoes'] as $c) {
    if (!isset($j[$c])) resp(422, ['erro' => "falta o campo $c"]);
}
if (!is_string($j['no_id']) || !preg_match('/^[A-Za-z0-9_-]{1,32}$/', $j['no_id'])) resp(422, ['erro' => 'no_id invalido']);
if (!is_int($j['boot_id']) || !is_int($j['seq']) || !is_int($j['ts'])) resp(422, ['erro' => 'boot_id, seq e ts têm de ser inteiros']);
if (!is_array($j['divisoes']) || count($j['divisoes']) < 1 || count($j['divisoes']) > 8) resp(422, ['erro' => 'divisoes invalidas']);

$pdo = ligar();
$tok = $_SERVER['HTTP_X_TOKEN'] ?? '';
$st = $pdo->prepare('SELECT token FROM nos WHERE no_id = ?');
$st->execute([$j['no_id']]);
$no = $st->fetch();
if (!$no || !hash_equals($no['token'], $tok)) resp(401, ['erro' => 'token invalido']);

$amb = $j['ambiente'] ?? [];
$luz_raw = isset($amb['luz_raw']) ? (int)$amb['luz_raw'] : null;
$luz_pct = isset($amb['luz_pct']) ? (int)$amb['luz_pct'] : null;
if ($luz_pct !== null && ($luz_pct < 0 || $luz_pct > 100)) resp(422, ['erro' => 'luz_pct fora de 0..100']);

$ins = $pdo->prepare('INSERT INTO leituras (no_id, boot_id, seq, divisao, ts, luz_raw, luz_pct, presenca, led_pct, modo)
                      VALUES (?,?,?,?,?,?,?,?,?,?)');
$novas = 0; $dups = 0;
foreach ($j['divisoes'] as $d) {
    $nome = $d['id'] ?? 'sala';
    $pres = (int)(!empty($d['presenca']));
    $led  = (int)($d['led_pct'] ?? 0);
    $modo = (string)($d['modo'] ?? 'auto');
    if ($led < 0 || $led > 100 || !in_array($modo, ['auto', 'manual', 'off'], true)) resp(422, ['erro' => 'divisao invalida']);
    try {
        $ins->execute([$j['no_id'], $j['boot_id'], $j['seq'], $nome, $j['ts'], $luz_raw, $luz_pct, $pres, $led, $modo]);
        $novas++;
    } catch (PDOException $e) {
        if ($e->getCode() === '23000') $dups++; else throw $e;
    }
}
resp(200, ['ok' => true, 'novas' => $novas, 'duplicadas' => $dups]);
