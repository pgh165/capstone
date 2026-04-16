import json
from datetime import date, datetime, timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db.models import Avg, Count, Max, Sum, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import DetectionLog, DailySummary, FatigueLog, RecoveryAction, Setting

ALLOWED_SETTINGS = {
    'ear_threshold':        {'min': 0.1,  'max': 0.5,   'type': float},
    'mar_threshold':        {'min': 0.3,  'max': 1.0,   'type': float},
    'ear_duration':         {'min': 0.5,  'max': 10.0,  'type': float},
    'yawn_count_threshold': {'min': 1,    'max': 10,    'type': int},
    'w1_ear':               {'min': 0.0,  'max': 1.0,   'type': float},
    'w2_mar':               {'min': 0.0,  'max': 1.0,   'type': float},
    'w3_head':              {'min': 0.0,  'max': 1.0,   'type': float},
    'w4_env':               {'min': 0.0,  'max': 1.0,   'type': float},
    'co2_warning':          {'min': 400,  'max': 5000,  'type': int},
    'temp_warning':         {'min': 15,   'max': 40,    'type': int},
}


def _to_dict(obj):
    """모델 인스턴스를 직렬화 가능한 dict로 변환."""
    d = {}
    for field in obj._meta.fields:
        val = getattr(obj, field.name)
        if isinstance(val, (datetime, date)):
            d[field.name] = val.isoformat()
        else:
            d[field.name] = val
    return d


def index(request):
    return render(request, 'dashboard/index.html')


def api_fatigue(request):
    period = request.GET.get('period', 'today')
    qs = FatigueLog.objects.all()
    if period == 'week':
        qs = qs.filter(logged_at__gte=datetime.now() - timedelta(days=7))
    elif period == 'month':
        qs = qs.filter(logged_at__gte=datetime.now() - timedelta(days=30))
    else:
        qs = qs.filter(logged_at__date=date.today())
    data = [_to_dict(r) for r in qs.order_by('-logged_at')]
    return JsonResponse({'success': True, 'period': period, 'data': data})


def api_logs(request):
    page = max(1, int(request.GET.get('page', 1)))
    limit = max(1, min(100, int(request.GET.get('limit', 20))))
    filter_date = request.GET.get('date')

    qs = DetectionLog.objects.all()
    if filter_date:
        qs = qs.filter(detected_at__date=filter_date)

    total = qs.count()
    offset = (page - 1) * limit
    data = [_to_dict(r) for r in qs.order_by('-detected_at')[offset:offset + limit]]

    return JsonResponse({
        'success': True,
        'data': data,
        'total': total,
        'page': page,
        'limit': limit,
        'total_pages': -(-total // limit),  # ceil division
    })


def api_recovery(request):
    rows = [_to_dict(r) for r in RecoveryAction.objects.order_by('-action_at')[:50]]

    stats = (
        RecoveryAction.objects
        .values('guide_type')
        .annotate(
            total_count=Count('id'),
            effective_count=Count('id', filter=Q(effective=True)),
        )
    )
    stats_list = list(stats)

    return JsonResponse({'success': True, 'data': rows, 'stats': stats_list})


def api_environment(request):
    hours = max(1, min(168, int(request.GET.get('hours', 24))))
    since = datetime.now() - timedelta(hours=hours)
    qs = (
        DetectionLog.objects
        .filter(detected_at__gte=since)
        .order_by('detected_at')
        .values('detected_at', 'co2_ppm', 'temperature', 'humidity', 'env_score')
    )
    data = []
    for r in qs:
        row = dict(r)
        if isinstance(row.get('detected_at'), datetime):
            row['detected_at'] = row['detected_at'].isoformat()
        data.append(row)
    return JsonResponse({'success': True, 'hours': hours, 'data': data})


def api_daily_report(request):
    target = request.GET.get('date', date.today().isoformat())
    try:
        summary = DailySummary.objects.get(summary_date=target)
        return JsonResponse({'success': True, 'data': _to_dict(summary)})
    except DailySummary.DoesNotExist:
        pass

    # daily_summary에 없으면 실시간 집계
    det = DetectionLog.objects.filter(detected_at__date=target).aggregate(
        total_detections=Count('id'),
        max_alert_level=Max('alert_level'),
        avg_drowsiness_score=Avg('drowsiness_score'),
        alert_count_level1=Count('id', filter=Q(alert_level=1)),
        alert_count_level2=Count('id', filter=Q(alert_level=2)),
        alert_count_level3=Count('id', filter=Q(alert_level=3)),
        avg_co2=Avg('co2_ppm'),
        avg_temperature=Avg('temperature'),
    )
    fat = FatigueLog.objects.filter(logged_at__date=target).aggregate(
        avg_fatigue_score=Avg('fatigue_score')
    )
    rec = RecoveryAction.objects.filter(action_at__date=target).aggregate(
        total_recovery_count=Count('id'),
        effective_recovery_count=Count('id', filter=Q(effective=True)),
    )

    data = {'summary_date': target, **det, **fat, **rec}
    return JsonResponse({'success': True, 'data': data, 'source': 'realtime'})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def api_settings(request):
    if request.method == 'GET':
        data = list(Setting.objects.order_by('id').values())
        return JsonResponse({'success': True, 'data': data})

    body = json.loads(request.body or '{}')
    key = body.get('key')
    value = body.get('value')

    if not key or value is None:
        return JsonResponse({'success': False, 'error': 'key와 value가 필요합니다.'}, status=400)

    if key not in ALLOWED_SETTINGS:
        return JsonResponse({
            'success': False,
            'error': '허용되지 않는 설정 키입니다.',
            'allowed_keys': list(ALLOWED_SETTINGS.keys()),
        }, status=400)

    rule = ALLOWED_SETTINGS[key]
    try:
        num = rule['type'](value)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': '올바른 숫자 값이 필요합니다.'}, status=400)

    if not (rule['min'] <= num <= rule['max']):
        return JsonResponse({
            'success': False,
            'error': f"값은 {rule['min']} ~ {rule['max']} 범위여야 합니다.",
        }, status=400)

    updated = Setting.objects.filter(setting_key=key).update(setting_value=str(num))
    if updated:
        return JsonResponse({'success': True, 'message': '설정이 변경되었습니다.'})
    return JsonResponse({'success': False, 'error': '해당 설정 키를 찾을 수 없습니다.'}, status=404)
