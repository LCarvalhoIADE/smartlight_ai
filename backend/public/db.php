<?php
function ligar(): PDO {
    $dsn = getenv('DB_DSN') ?: 'mysql:host=db;dbname=smartlight;charset=utf8mb4';
    $pdo = new PDO($dsn, getenv('DB_USER') ?: null, getenv('DB_PASS') ?: null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    return $pdo;
}
function resp(int $code, array $body): never {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($body, JSON_UNESCAPED_UNICODE);
    exit;
}
