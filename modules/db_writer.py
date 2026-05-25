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

    def get_hourly_fatigue_pattern(self):
        """시간대별 평균 피로도를 반환한다.

        Returns:
            list[dict]: [{"hour": int, "avg_fatigue": float}, ...]
                샘플이 3개 미만인 시간대는 제외. DB 실패 시 빈 리스트.
        """
        self._ensure_connection()
        if self._conn is None:
            return []

        sql = """
            SELECT HOUR(logged_at) AS hour,
                   AVG(fatigue_score) AS avg_fatigue,
                   COUNT(*) AS cnt
            FROM fatigue_logs
            GROUP BY HOUR(logged_at)
            HAVING cnt >= 3
            ORDER BY hour
        """
        try:
            with self._conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception as e:
            print(f"[db_writer] hourly_fatigue_pattern 조회 실패: {e}")
            return []

    def get_optimal_work_interval(self):
        """피로가 높아질 때의 평균 연속 작업 시간을 반환한다.

        fatigue_logs에서 warning/danger 단계 진입 시 continuous_work_min의
        평균을 계산하여 개인 최적 인터벌 도출에 사용한다.

        Returns:
            dict | None: {"avg_min": float, "cnt": int} 또는 None.
        """
        self._ensure_connection()
        if self._conn is None:
            return None

        sql = """
            SELECT AVG(continuous_work_min) AS avg_min, COUNT(*) AS cnt
            FROM fatigue_logs
            WHERE fatigue_level IN ('warning', 'danger')
              AND continuous_work_min > 0
        """
        try:
            with self._conn.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if row and row.get("cnt", 0):
                    return {"avg_min": float(row["avg_min"]), "cnt": int(row["cnt"])}
                return None
        except Exception as e:
            print(f"[db_writer] optimal_work_interval 조회 실패: {e}")
            return None

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
