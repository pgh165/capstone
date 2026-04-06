"""
MySQL 데이터 저장 모듈

졸음 감지 결과, 피로도 이력, 피로 해소 기록을
MySQL(MariaDB) 데이터베이스에 저장한다.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class DBWriter:
    """MySQL에 감지 데이터를 저장하는 클래스.

    연결 오류 시 경고를 출력하되 프로그램을 중단하지 않는다.
    """

    def __init__(self):
        self._conn = None
        self._connect()

    def _connect(self):
        """MySQL 서버에 연결한다."""
        try:
            import pymysql
            self._conn = pymysql.connect(
                host=config.DB_HOST,
                port=getattr(config, "DB_PORT", 3306),
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                charset=config.DB_CHARSET,
                autocommit=True,
                connect_timeout=2,
                cursorclass=pymysql.cursors.DictCursor,
            )
            print("[db_writer] MySQL 연결 성공")
        except ImportError:
            print("[db_writer] pymysql 라이브러리를 찾을 수 없습니다. pip install pymysql")
            self._conn = None
        except Exception as e:
            print(f"[db_writer] MySQL 연결 실패: {e}")
            self._conn = None

    def _ensure_connection(self):
        """연결이 끊어진 경우 재연결을 시도한다."""
        if self._conn is None:
            self._connect()
            return

        try:
            self._conn.ping(reconnect=True)
        except Exception:
            print("[db_writer] MySQL 연결 끊김, 재연결 시도...")
            self._connect()

    # ──────────────────────────────────────────────────────────────
    #  detection_logs 저장
    # ──────────────────────────────────────────────────────────────
    def save_detection(self, data_dict):
        """졸음 감지 결과를 detection_logs 테이블에 저장한다.

        Args:
            data_dict (dict): 저장할 데이터. 키 목록:
                - ear_value (float)
                - mar_value (float)
                - head_pitch (float)
                - head_yaw (float)
                - drowsiness_score (int)
                - alert_level (int)
                - co2_ppm (int)
                - temperature (float)
                - humidity (float)
                - env_score (int)
        """
        self._ensure_connection()
        if self._conn is None:
            print("[db_writer] DB 연결 없음 - detection 저장 건너뜀")
            return

        sql = """
            INSERT INTO detection_logs
                (detected_at, ear_value, mar_value, head_pitch, head_yaw,
                 drowsiness_score, alert_level, co2_ppm, temperature, humidity, env_score)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            params = (
                now,
                data_dict.get("ear_value", 0.0),
                data_dict.get("mar_value", 0.0),
                data_dict.get("head_pitch", 0.0),
                data_dict.get("head_yaw", 0.0),
                data_dict.get("drowsiness_score", 0),
                data_dict.get("alert_level", 0),
                data_dict.get("co2_ppm", 0),
                data_dict.get("temperature", 0.0),
                data_dict.get("humidity", 0.0),
                data_dict.get("env_score", 0),
            )
            with self._conn.cursor() as cursor:
                cursor.execute(sql, params)
        except Exception as e:
            print(f"[db_writer] detection 저장 실패: {e}")

    # ──────────────────────────────────────────────────────────────
    #  fatigue_logs 저장
    # ──────────────────────────────────────────────────────────────
    def save_fatigue(self, data_dict):
        """피로도 이력을 fatigue_logs 테이블에 저장한다.

        Args:
            data_dict (dict): 저장할 데이터. 키 목록:
                - fatigue_score (int)
                - continuous_work_min (int)
                - drowsy_count_30min (int)
                - env_stress_score (int)
                - fatigue_level (str)
        """
        self._ensure_connection()
        if self._conn is None:
            print("[db_writer] DB 연결 없음 - fatigue 저장 건너뜀")
            return

        sql = """
            INSERT INTO fatigue_logs
                (logged_at, fatigue_score, continuous_work_min,
                 drowsy_count_30min, env_stress_score, fatigue_level)
            VALUES
                (%s, %s, %s, %s, %s, %s)
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            params = (
                now,
                data_dict.get("fatigue_score", 0),
                data_dict.get("continuous_work_min", 0),
                data_dict.get("drowsy_count_30min", 0),
                data_dict.get("env_stress_score", 0),
                data_dict.get("fatigue_level", "good"),
            )
            with self._conn.cursor() as cursor:
                cursor.execute(sql, params)
        except Exception as e:
            print(f"[db_writer] fatigue 저장 실패: {e}")

    # ──────────────────────────────────────────────────────────────
    #  recovery_actions 저장
    # ──────────────────────────────────────────────────────────────
    def save_recovery_action(self, data_dict):
        """피로 해소 기록을 recovery_actions 테이블에 저장한다.

        Args:
            data_dict (dict): 저장할 데이터. 키 목록:
                - guide_type (str)
                - dominant_cause (str): "work", "drowsy", "env"
                - fatigue_before (int)
                - fatigue_after (int)
                - drowsiness_before (int)
                - drowsiness_after (int)
                - duration_sec (int)
                - effective (bool)
        """
        self._ensure_connection()
        if self._conn is None:
            print("[db_writer] DB 연결 없음 - recovery_action 저장 건너뜀")
            return

        sql = """
            INSERT INTO recovery_actions
                (action_at, guide_type, dominant_cause,
                 fatigue_before, fatigue_after,
                 drowsiness_before, drowsiness_after,
                 duration_sec, effective)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            params = (
                now,
                data_dict.get("guide_type", ""),
                data_dict.get("dominant_cause", ""),
                data_dict.get("fatigue_before", 0),
                data_dict.get("fatigue_after", 0),
                data_dict.get("drowsiness_before", 0),
                data_dict.get("drowsiness_after", 0),
                data_dict.get("duration_sec", 0),
                1 if data_dict.get("effective", False) else 0,
            )
            with self._conn.cursor() as cursor:
                cursor.execute(sql, params)
        except Exception as e:
            print(f"[db_writer] recovery_action 저장 실패: {e}")

    def get_recovery_history(self, limit=100):
        """최근 회복 이력을 조회한다.

        Args:
            limit (int): 최대 조회 건수.

        Returns:
            list[dict]: 회복 이력 리스트. DB 연결 실패 시 빈 리스트.
        """
        self._ensure_connection()
        if self._conn is None:
            return []

        sql = """
            SELECT guide_type, dominant_cause,
                   fatigue_before, fatigue_after,
                   drowsiness_before, drowsiness_after,
                   effective
            FROM recovery_actions
            ORDER BY action_at DESC
            LIMIT %s
        """
        try:
            with self._conn.cursor() as cursor:
                cursor.execute(sql, (limit,))
                return cursor.fetchall()
        except Exception as e:
            print(f"[db_writer] recovery_history 조회 실패: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    #  연결 종료
    # ──────────────────────────────────────────────────────────────
    def close(self):
        """MySQL 연결을 닫는다."""
        if self._conn is not None:
            try:
                self._conn.close()
                print("[db_writer] MySQL 연결 종료")
            except Exception:
                pass
            self._conn = None
