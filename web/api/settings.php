<?php
/**
 * 설정 조회/변경 API
 * GET  /api/settings.php          - 전체 설정 조회
 * POST /api/settings.php          - 설정 변경 (key, value)
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

try {
    if ($_SERVER['REQUEST_METHOD'] === 'GET') {
        $sql = "SELECT * FROM settings ORDER BY id";
        $stmt = $pdo->query($sql);
        $data = $stmt->fetchAll();

        echo json_encode(['success' => true, 'data' => $data]);

    } elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $input = json_decode(file_get_contents('php://input'), true);

        if (empty($input['key']) || !isset($input['value'])) {
            http_response_code(400);
            echo json_encode(['success' => false, 'error' => 'key와 value가 필요합니다.']);
            exit;
        }

        $sql = "UPDATE settings SET setting_value = :value WHERE setting_key = :key";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':key' => $input['key'],
            ':value' => $input['value']
        ]);

        if ($stmt->rowCount() > 0) {
            echo json_encode(['success' => true, 'message' => '설정이 변경되었습니다.']);
        } else {
            echo json_encode(['success' => false, 'error' => '해당 설정 키를 찾을 수 없습니다.']);
        }

    } else {
        http_response_code(405);
        echo json_encode(['success' => false, 'error' => 'Method Not Allowed']);
    }
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
