<?php
/**
 * 설정 조회/변경 API
 * GET  /api/settings.php          - 전체 설정 조회
 * POST /api/settings.php          - 설정 변경 (key, value)
 */

header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/../includes/db.php';

// 허용된 설정 키와 값 범위 (화이트리스트)
$ALLOWED_SETTINGS = [
    'ear_threshold'        => ['min' => 0.1,  'max' => 0.5,   'type' => 'float'],
    'mar_threshold'        => ['min' => 0.3,  'max' => 1.0,   'type' => 'float'],
    'ear_duration'         => ['min' => 0.5,  'max' => 10.0,  'type' => 'float'],
    'yawn_count_threshold' => ['min' => 1,    'max' => 10,    'type' => 'int'],
    'w1_ear'               => ['min' => 0.0,  'max' => 1.0,   'type' => 'float'],
    'w2_mar'               => ['min' => 0.0,  'max' => 1.0,   'type' => 'float'],
    'w3_head'              => ['min' => 0.0,  'max' => 1.0,   'type' => 'float'],
    'w4_env'               => ['min' => 0.0,  'max' => 1.0,   'type' => 'float'],
    'co2_warning'          => ['min' => 400,  'max' => 5000,  'type' => 'int'],
    'temp_warning'         => ['min' => 15,   'max' => 40,    'type' => 'int'],
];

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

        $key = $input['key'];
        $value = $input['value'];

        // 화이트리스트 검증
        if (!array_key_exists($key, $ALLOWED_SETTINGS)) {
            http_response_code(400);
            echo json_encode([
                'success' => false,
                'error' => '허용되지 않는 설정 키입니��.',
                'allowed_keys' => array_keys($ALLOWED_SETTINGS)
            ]);
            exit;
        }

        // 값 타입 및 범위 검증
        $rule = $ALLOWED_SETTINGS[$key];
        if ($rule['type'] === 'float') {
            if (!is_numeric($value)) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => '숫자 값이 필요합니다.']);
                exit;
            }
            $numValue = floatval($value);
        } else {
            if (!is_numeric($value) || intval($value) != $value) {
                http_response_code(400);
                echo json_encode(['success' => false, 'error' => '정수 값이 필요합니다.']);
                exit;
            }
            $numValue = intval($value);
        }

        if ($numValue < $rule['min'] || $numValue > $rule['max']) {
            http_response_code(400);
            echo json_encode([
                'success' => false,
                'error' => "값은 {$rule['min']} ~ {$rule['max']} 범위여야 합니다."
            ]);
            exit;
        }

        $sql = "UPDATE settings SET setting_value = :value WHERE setting_key = :key";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':key' => $key,
            ':value' => strval($numValue)
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
    error_log('[api/settings] ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => '설정 처리 중 오류가 발생했습니다.']);
}
?>
