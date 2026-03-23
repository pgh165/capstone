-- AIoT 기반 졸음 및 집중력 저하 방지 시스템 - 데이터베이스 스키마
-- MySQL / MariaDB

CREATE DATABASE IF NOT EXISTS drowsiness_db
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE drowsiness_db;

-- 졸음 감지 이력
CREATE TABLE IF NOT EXISTS detection_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ear_value FLOAT,
    mar_value FLOAT,
    head_pitch FLOAT,
    head_yaw FLOAT,
    drowsiness_score INT,
    alert_level INT,
    co2_ppm INT,
    temperature FLOAT,
    humidity FLOAT,
    env_score INT,
    INDEX idx_detected_at (detected_at),
    INDEX idx_alert_level (alert_level)
);

-- 피로도 이력
CREATE TABLE IF NOT EXISTS fatigue_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    logged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fatigue_score INT,
    continuous_work_min INT,
    drowsy_count_30min INT,
    env_stress_score INT,
    fatigue_level VARCHAR(20),
    INDEX idx_logged_at (logged_at)
);

-- 피로 해소 기록
CREATE TABLE IF NOT EXISTS recovery_actions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    guide_type VARCHAR(50),
    fatigue_before INT,
    fatigue_after INT,
    duration_sec INT,
    effective BOOLEAN DEFAULT FALSE,
    INDEX idx_action_at (action_at)
);

-- 시스템 설정
CREATE TABLE IF NOT EXISTS settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value VARCHAR(255),
    description VARCHAR(500),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 일간 요약
CREATE TABLE IF NOT EXISTS daily_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    summary_date DATE UNIQUE NOT NULL,
    total_detections INT DEFAULT 0,
    max_alert_level INT DEFAULT 0,
    avg_drowsiness_score FLOAT DEFAULT 0,
    avg_fatigue_score FLOAT DEFAULT 0,
    total_recovery_count INT DEFAULT 0,
    effective_recovery_count INT DEFAULT 0,
    alert_count_level1 INT DEFAULT 0,
    alert_count_level2 INT DEFAULT 0,
    alert_count_level3 INT DEFAULT 0,
    peak_drowsy_time TIME,
    avg_co2 INT DEFAULT 0,
    avg_temperature FLOAT DEFAULT 0,
    INDEX idx_summary_date (summary_date)
);

-- 기본 설정값 삽입
INSERT INTO settings (setting_key, setting_value, description) VALUES
('ear_threshold', '0.2', 'EAR 임계값 (이하면 눈 감김)'),
('mar_threshold', '0.6', 'MAR 임계값 (이상이면 하품)'),
('ear_duration', '2.0', '눈 감김 지속시간 임계값 (초)'),
('yawn_count_threshold', '3', '하품 횟수 임계값 (3분 내)'),
('w1_ear', '0.35', '졸음점수 EAR 가중치'),
('w2_mar', '0.25', '졸음점수 MAR 가중치'),
('w3_head', '0.20', '졸음점수 Head Pose 가중치'),
('w4_env', '0.20', '졸음점수 환경 가중치'),
('co2_warning', '1000', 'CO2 경고 임계값 (ppm)'),
('temp_warning', '26', '온도 졸음유발 임계값 (C)')
ON DUPLICATE KEY UPDATE setting_key=setting_key;
