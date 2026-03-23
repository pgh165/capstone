<?php
/**
 * 피로 해소 기록 API
 * GET /api/recovery.php
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

try {
    // 해소 기록 목록
    $sql = "SELECT * FROM recovery_actions ORDER BY action_at DESC LIMIT 50";
    $stmt = $pdo->query($sql);
    $data = $stmt->fetchAll();

    // 효과 통계
    $statsSql = "SELECT
        COUNT(*) as total_count,
        SUM(CASE WHEN effective = 1 THEN 1 ELSE 0 END) as effective_count,
        AVG(fatigue_before - fatigue_after) as avg_reduction,
        guide_type
        FROM recovery_actions
        GROUP BY guide_type";
    $stmt = $pdo->query($statsSql);
    $stats = $stmt->fetchAll();

    echo json_encode([
        'success' => true,
        'data' => $data,
        'stats' => $stats
    ]);
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
