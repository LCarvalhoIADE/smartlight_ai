<?php
// Vai buscar as últimas leituras ao servidor e entrega-as na página.
// A chave fica só aqui, no servidor: o browser nunca a vê.
// (O início da sessão entra no passo seguinte.)

$cfg = require __DIR__ . '/config.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

if (!empty($cfg['exemplo'])) {
    // Leituras inventadas: nó 1 e nó 2 online, nó 3 parado há 5 minutos
    $agora = time();
    $linhas = [];
    foreach ([['no1', 'sala', 0], ['no2', 'corredor', 0], ['no2', 'quarto', 0], ['no3', 'sala', 300]] as [$no, $div, $atraso]) {
        $pres = rand(0, 1);
        $linhas[] = ['no_id' => $no, 'divisao' => $div, 'ts' => $agora - $atraso,
                     'luz_pct' => rand(10, 80), 'presenca' => $pres, 'led_pct' => $pres ? 70 : 0, 'modo' => 'auto'];
    }
    echo json_encode(['agora' => $agora, 'offline_s' => $cfg['offline_s'], 'leituras' => $linhas]);
    exit;
}

$url = $cfg['url_ultimas'] . '?' . http_build_query(['chave' => $cfg['chave'], 'por_divisao' => 1]);
$ch = curl_init($url);
curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 6]);
$corpo = curl_exec($ch);
$codigo = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

$leituras = ($corpo !== false && $codigo === 200) ? json_decode($corpo, true) : null;
if (!is_array($leituras)) {
    http_response_code(502);
    echo json_encode(['erro' => 'O servidor de leituras não respondeu.']);
    exit;
}
echo json_encode(['agora' => time(), 'offline_s' => $cfg['offline_s'], 'leituras' => $leituras]);