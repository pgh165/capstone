<?php
/**
 * 일간 리포트 API
 * GET /api/daily_report.php?date=2024-01-01
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

$date = $_GET['date'] ?? date('Y-m-d');

try {
    // daily_summary 테이블에서 조회
    $sql = "SELECT * FROM daily_summary WHERE summary_date = :date";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([':date' => $date]);
    $summary = $stmt->fetch();

    if ($summary) {
        echo json_encode(['success' => true, 'data' => $summary]);
    } else {
        // daily_summary에 없으면 실시간 집계
        $sql = "SELECT
            COUNT(*) as total_detections,
            MAX(alert_level) as max_alert_level,
            ROUND(AVG(drowsiness_score), 1) as avg_drowsiness_score,
            SUM(CASE WHEN alert_level = 1 THEN 1 ELSE 0 END) as alert_count_level1,
            SUM(CASE WHEN alert_level = 2 THEN 1 ELSE 0 END) as alert_count_level2,
            SUM(CASE WHEN alert_level = 3 THEN 1 ELSE 0 END) as alert_count_level3,
            ROUND(AVG(co2_ppm)) as avg_co2,
            ROUND(AVG(temperature), 1) as avg_temperature
            FROM detection_logs
            WHERE DATE(detected_at) = :date";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([':date' => $date]);
        $detection_stats = $stmt->fetch();

        // 피로도 평균
        $sql = "SELECT ROUND(AVG(fatigue_score), 1) as avg_fatigue_score
                FROM fatigue_logs WHERE DATE(logged_at) = :date";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([':date' => $date]);
        $fatigue_stats = $stmt->fetch();

        // 해소 기록
        $sql = "SELECT
            COUNT(*) as total_recovery_count,
            SUM(CASE WHEN effective = 1 THEN 1 ELSE 0 END) as effective_recovery_count
            FROM recovery_actions WHERE DATE(action_at) = :date";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([':date' => $date]);
        $recovery_stats = $stmt->fetch();

        $data = array_merge(
            ['summary_date' => $date],
            $detection_stats ?: [],
            $fatigue_stats ?: [],
            $recovery_stats ?: []
        );

        echo json_encode(['success' => true, 'data' => $data, 'source' => 'realtime']);
    }
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
