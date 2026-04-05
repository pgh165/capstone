<?php
/**
 * MySQL 데이터베이스 연결 공통 모듈
 * .env 파일에서 자격증명을 로드한다.
 */

// .env 파일 로드
function loadEnv($path) {
    if (!file_exists($path)) return [];
    $vars = [];
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        if (strpos($line, '=') !== false) {
            list($key, $value) = explode('=', $line, 2);
            $vars[trim($key)] = trim($value);
        }
    }
    return $vars;
}

$env = loadEnv(__DIR__ . '/../../.env');

$db_host = $env['DB_HOST'] ?? 'localhost';
$db_user = $env['DB_USER'] ?? 'jiho';
$db_pass = $env['DB_PASSWORD'] ?? 'qwer1234';
$db_name = $env['DB_NAME'] ?? 'jihodb';
$db_port = $env['DB_PORT'] ?? '3306';

try {
    $pdo = new PDO(
        "mysql:host=$db_host;port=$db_port;dbname=$db_name;charset=utf8mb4",
        $db_user,
        $db_pass
    );
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    error_log('[db] Connection failed: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => '데이터베이스 연결에 실패했습니다.']);
    exit;
}
?>
