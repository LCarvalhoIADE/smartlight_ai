<?php
// Dados inventados, no mesmo formato do servidor, para testar sem ligação.
// A casa 4 fica parada há 10 minutos, para se ver o estado «sem comunicação».

function exemplo(string $o, array $cfg): array
{
    $nos = [
        ['no_id' => 'no1', 'pais' => 'PT', 'fuso' => 'Europe/Lisbon', 'sensor_luz' => 'analogico', 'divisoes' => ['sala', 'cozinha'], 'atraso' => 0],
        ['no_id' => 'no2', 'pais' => 'CH', 'fuso' => 'Europe/Zurich', 'sensor_luz' => 'analogico', 'divisoes' => ['corredor', 'quarto'], 'atraso' => 0],
        ['no_id' => 'no3', 'pais' => 'PT', 'fuso' => 'Europe/Lisbon', 'sensor_luz' => 'digital',   'divisoes' => ['sala'], 'atraso' => 0],
        ['no_id' => 'no4', 'pais' => 'PT', 'fuso' => 'Europe/Lisbon', 'sensor_luz' => 'lux',       'divisoes' => ['cozinha', 'sala'], 'atraso' => 600],
    ];
    $agora = time();

    if ($o === 'nos') {
        return ['nos' => array_map(fn($n) => ['no_id' => $n['no_id'], 'descricao' => null, 'sensor_luz' => $n['sensor_luz'],
            'fuso' => $n['fuso'], 'pais' => $n['pais'], 'latitude' => null, 'longitude' => null], $nos)];
    }

    if ($o === 'historico') {
        $linhas = [];
        for ($ts = $agora - 86400; $ts <= $agora; $ts += 15) {
            $linhas[] = leitura_exemplo($_GET['no_id'] ?? 'no2', $_GET['divisao'] ?? 'quarto', $ts, 'analogico');
        }
        return ['leituras' => $linhas];
    }

    $linhas = [];
    foreach ($nos as $n) {
        foreach ($n['divisoes'] as $d) {
            $linhas[] = leitura_exemplo($n['no_id'], $d, $agora - $n['atraso'], $n['sensor_luz']);
        }
    }
    return ['agora' => $agora, 'offline_s' => $cfg['offline_s'], 'leituras' => $linhas];
}

function leitura_exemplo(string $no, string $div, int $ts, string $sensor): array
{
    $h = (int)gmdate('G', $ts);
    $dia = $h >= 7 && $h < 18;                       // de dia há luz natural
    $pres = (int)((intdiv($ts, 900) + crc32($div)) % 3 === 0);   // presença aos blocos de 15 min
    $led = $pres ? ($dia ? 40 : 100) : 0;
    $raw = match ($sensor) {
        'digital' => $dia ? 0 : 1,
        'lux'     => $dia ? 320 : 4,
        default   => $dia ? 3100 : 600,
    };
    return ['no_id' => $no, 'divisao' => $div, 'ts' => $ts, 'luz_raw' => $raw,
            'luz_pct' => $sensor === 'analogico' ? intdiv($raw * 100, 4095) : null,
            'presenca' => $pres, 'led_pct' => $led,
            'corrente_ma' => $no === 'no1' ? round(5.6 * $led / 100, 1) : null,
            'modo' => 'auto', 'sensor_luz' => $sensor];
}
