<?php
/**
 * 피로도 이력 API
 * GET /api/fatigue.php?period=today|week|month
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

$period = $_GET['period'] ?? 'today';

try {
    switch ($period) {
        case 'week':
            $where = "WHERE logged_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)";
            break;
        case 'month':
            $where = "WHERE logged_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)";
            break;
        case 'today':
        default:
            $where = "WHERE DATE(logged_at) = CURDATE()";
            break;
    }

    $sql = "SELECT * FROM fatigue_logs $where ORDER BY logged_at DESC";
    $stmt = $pdo->query($sql);
    $data = $stmt->fetchAll();

    echo json_encode([
        'success' => true,
        'period' => $period,
        'data' => $data
    ]);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
