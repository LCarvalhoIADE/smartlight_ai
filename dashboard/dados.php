<?php
// Intermediário entre a página e o servidor do grupo.
// A página pede:  dados.php?o=estado   (última leitura de cada divisão)
//                 dados.php?o=nos      (país e fuso de cada casa)
//                 dados.php?o=historico&no_id=no2&divisao=quarto   (últimas 24 h)
// A chave vai no cabeçalho X-Chave e nunca chega ao browser.

$cfg = require __DIR__ . '/config.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$o = $_GET['o'] ?? 'estado';

if (!empty($cfg['exemplo'])) {
    require __DIR__ . '/exemplo.php';
    echo json_encode(exemplo($o, $cfg));
    exit;
}

// Aceita o config.php antigo, que só tinha url_ultimas
$base = $cfg['url_base'] ?? dirname($cfg['url_ultimas']);

// Faz um pedido ao servidor com a chave no cabeçalho e devolve o JSON já convertido
function pedir(string $url, string $chave): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 8,
        CURLOPT_HTTPHEADER     => ['X-Chave: ' . $chave],
    ]);
    $corpo  = curl_exec($ch);
    $codigo = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $dados = ($corpo !== false && $codigo === 200) ? json_decode($corpo, true) : null;
    if (!is_array($dados)) {
        http_response_code(502);
        echo json_encode(['erro' => 'O servidor de leituras não respondeu.']);
        exit;
    }
    return $dados;
}

if ($o === 'nos') {
    echo json_encode(pedir("$base/nos.php", $cfg['chave']));
    exit;
}

if ($o === 'historico') {
    // Só se aceitam letras, números, - e _ no nó; a divisão é limitada a 32 caracteres
    $no  = preg_replace('/[^A-Za-z0-9_-]/', '', $_GET['no_id'] ?? '');
    $div = substr($_GET['divisao'] ?? '', 0, 32);
    $q = http_build_query([
        'no_id' => $no, 'divisao' => $div,
        'de' => time() - 86400, 'ate' => time(), 'limite' => 10000,
    ]);
    echo json_encode(pedir("$base/historico.php?$q", $cfg['chave']));
    exit;
}

// Por omissão: estado atual
$leituras = pedir("$base/ultimas.php?por_divisao=1", $cfg['chave']);
echo json_encode(['agora' => time(), 'offline_s' => $cfg['offline_s'], 'leituras' => $leituras]);
