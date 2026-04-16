from django.db import models


class DetectionLog(models.Model):
    detected_at = models.DateTimeField()
    ear_value = models.FloatField(null=True)
    mar_value = models.FloatField(null=True)
    head_pitch = models.FloatField(null=True)
    head_yaw = models.FloatField(null=True)
    drowsiness_score = models.IntegerField(null=True)
    alert_level = models.IntegerField(null=True)
    co2_ppm = models.IntegerField(null=True)
    temperature = models.FloatField(null=True)
    humidity = models.FloatField(null=True)
    env_score = models.IntegerField(null=True)

    class Meta:
        managed = False
        db_table = 'detection_logs'


class FatigueLog(models.Model):
    logged_at = models.DateTimeField()
    fatigue_score = models.IntegerField(null=True)
    continuous_work_min = models.IntegerField(null=True)
    drowsy_count_30min = models.IntegerField(null=True)
    env_stress_score = models.IntegerField(null=True)
    fatigue_level = models.CharField(max_length=20, null=True)

    class Meta:
        managed = False
        db_table = 'fatigue_logs'


class RecoveryAction(models.Model):
    action_at = models.DateTimeField()
    guide_type = models.CharField(max_length=100, null=True)
    dominant_cause = models.CharField(max_length=20, null=True)
    fatigue_before = models.IntegerField(null=True)
    fatigue_after = models.IntegerField(null=True)
    drowsiness_before = models.IntegerField(null=True)
    drowsiness_after = models.IntegerField(null=True)
    duration_sec = models.IntegerField(null=True)
    effective = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'recovery_actions'


class Setting(models.Model):
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.CharField(max_length=255, null=True)
    description = models.CharField(max_length=500, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'settings'


class DailySummary(models.Model):
    summary_date = models.DateField(unique=True)
    total_detections = models.IntegerField(default=0)
    max_alert_level = models.IntegerField(default=0)
    avg_drowsiness_score = models.FloatField(default=0)
    avg_fatigue_score = models.FloatField(default=0)
    total_recovery_count = models.IntegerField(default=0)
    effective_recovery_count = models.IntegerField(default=0)
    alert_count_level1 = models.IntegerField(default=0)
    alert_count_level2 = models.IntegerField(default=0)
    alert_count_level3 = models.IntegerField(default=0)
    peak_drowsy_time = models.TimeField(null=True)
    avg_co2 = models.IntegerField(default=0)
    avg_temperature = models.FloatField(default=0)

    class Meta:
        managed = False
        db_table = 'daily_summary'
