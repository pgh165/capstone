<?php
/**
 * 환경 센서 이력 API
 * GET /api/environment.php?hours=24
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

$hours = max(1, min(168, intval($_GET['hours'] ?? 24)));

try {
    $sql = "SELECT detected_at, co2_ppm, temperature, humidity, env_score
            FROM detection_logs
            WHERE detected_at >= DATE_SUB(NOW(), INTERVAL :hours HOUR)
            ORDER BY detected_at ASC";
    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':hours', $hours, PDO::PARAM_INT);
    $stmt->execute();
    $data = $stmt->fetchAll();

    echo json_encode([
        'success' => true,
        'hours' => $hours,
        'data' => $data
    ]);
} catch (Exception $e) {
    error_log('[api/environment] ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => '데이터 조회 중 오류가 발생했습니다.']);
}
?>
