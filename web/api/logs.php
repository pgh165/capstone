<?php
/**
 * 감지 이력 API
 * GET /api/logs.php?page=1&limit=20&date=2024-01-01
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

$page = max(1, intval($_GET['page'] ?? 1));
$limit = max(1, min(100, intval($_GET['limit'] ?? 20)));
$offset = ($page - 1) * $limit;

try {
    // 날짜 필터
    $where = '';
    $params = [];
    if (!empty($_GET['date'])) {
        $where = 'WHERE DATE(detected_at) = :date';
        $params[':date'] = $_GET['date'];
    }

    // 총 개수
    $countSql = "SELECT COUNT(*) as total FROM detection_logs $where";
    $stmt = $pdo->prepare($countSql);
    $stmt->execute($params);
    $total = $stmt->fetch()['total'];

    // 데이터 조회
    $dataSql = "SELECT * FROM detection_logs $where ORDER BY detected_at DESC LIMIT :limit OFFSET :offset";
    $stmt = $pdo->prepare($dataSql);
    foreach ($params as $key => $val) {
        $stmt->bindValue($key, $val);
    }
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $data = $stmt->fetchAll();

    echo json_encode([
        'success' => true,
        'data' => $data,
        'total' => $total,
        'page' => $page,
        'limit' => $limit,
        'total_pages' => ceil($total / $limit)
    ]);
} catch (Exception $e) {
    error_log('[api/logs] ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => '데이터 조회 중 오류가 발생했습니다.']);
}
?>
