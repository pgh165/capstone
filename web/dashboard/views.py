import json
import os
from datetime import date, datetime, timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db.models import Avg, Count, Max, Sum, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import DetectionLog, DailySummary, FatigueLog, Setting

ALLOWED_SETTINGS = {
    'ear_threshold':        {'min': 0.1,  'max': 0.5,   'type': float},
    'mar_threshold':        {'min': 0.3,  'max': 1.0,   'type': float},
    'ear_duration':         {'min': 0.5,  'max': 10.0,  'type': float},
    'yawn_count_threshold': {'min': 1,    'max': 10,    'type': int},
    'w1_ear':               {'min': 0.0,  'max': 1.0,   'type': float},
    'w2_mar':               {'min': 0.0,  'max': 1.0,   'type': float},
    'w3_head':              {'min': 0.0,  'max': 1.0,   'type': float},
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


_STATUS_FILE   = "/app/data/realtime_status.json"
_CMD_FILE      = "/app/data/cmd.json"
_PROFILE_FILE  = "/app/data/user_profile.json"


def index(request):
    return render(request, 'dashboard/index.html')


def realtime(request):
    return render(request, 'dashboard/realtime.html')


def settings_page(request):
    return render(request, 'dashboard/settings.html')


def guides_page(request):
    import json as _j
    guides_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'guides.json')
    try:
        with open(guides_path, encoding='utf-8') as f:
            guides = _j.load(f)
    except Exception:
        guides = {}

    # 단계별 가이드 매핑 (fatigue_manager._GUIDE_MAP 기준)
    guide_map = {
        "caution": {
            "label": "주의",
            "color": "#d29922",
            "score": "51 ~ 75",
            "work":  ["eye_rest", "ventilation", "posture_correction", "hydration"],
            "drowsy":["eye_rest", "ventilation", "face_wash", "breathing"],
        },
        "warning": {
            "label": "경고",
            "color": "#f0883e",
            "score": "76 ~ 88",
            "work":  ["stretching", "eye_rest", "ventilation", "walk", "hydration", "posture_correction"],
            "drowsy":["stretching", "eye_rest", "ventilation", "face_wash", "breathing", "caffeine"],
        },
        "danger": {
            "label": "위험",
            "color": "#f85149",
            "score": "89 ~ 100",
            "work":  ["rest_break", "stretching", "eye_rest", "ventilation", "walk", "hydration"],
            "drowsy":["rest_break", "stretching", "eye_rest", "ventilation", "face_wash", "caffeine", "breathing"],
        },
    }

    return render(request, 'dashboard/guides.html', {
        'guides': guides,
        'guide_map': guide_map,
    })


def api_realtime(request):
    """main.py가 매초 기록하는 상태 파일을 읽어 반환한다."""
    try:
        with open(_STATUS_FILE) as f:
            data = json.load(f)
        age = datetime.now().timestamp() - data.get("ts", 0)
        data["stale"] = age > 5
        return JsonResponse({"success": True, "data": data})
    except FileNotFoundError:
        return JsonResponse({"success": False, "error": "main.py가 실행 중이 아닙니다."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def api_fatigue(request):
    period = request.GET.get('period', 'today')
    filter_date = request.GET.get('date')
    qs = FatigueLog.objects.all()
    if filter_date:
        qs = qs.filter(logged_at__date=filter_date)
    elif period == 'week':
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
    )
    fat = FatigueLog.objects.filter(logged_at__date=target).aggregate(
        avg_fatigue_score=Avg('fatigue_score')
    )
    data = {'summary_date': target, **det, **fat}
    return JsonResponse({'success': True, 'data': data, 'source': 'realtime'})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def api_profile(request):
    """사용자 프로필(이름)을 읽거나 저장한다."""
    if request.method == 'GET':
        try:
            with open(_PROFILE_FILE) as f:
                data = json.load(f)
            return JsonResponse({'success': True, 'data': data})
        except FileNotFoundError:
            return JsonResponse({'success': True, 'data': {'name': ''}})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    body = json.loads(request.body or '{}')
    name = body.get('name', '').strip()
    if not name:
        return JsonResponse({'success': False, 'error': '이름을 입력해주세요.'}, status=400)
    if len(name) > 20:
        return JsonResponse({'success': False, 'error': '이름은 20자 이하여야 합니다.'}, status=400)
    try:
        with open(_PROFILE_FILE, 'w') as f:
            json.dump({'name': name}, f, ensure_ascii=False)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


_ALLOWED_CMDS = {'pomo_reset', 'calib_reset'}

@csrf_exempt
@require_http_methods(['POST'])
def api_command(request):
    """대시보드 → main.py 제어 커맨드를 cmd.json에 기록한다."""
    import time as _time
    try:
        body = json.loads(request.body or '{}')
        cmd = body.get('cmd')
        if cmd not in _ALLOWED_CMDS:
            return JsonResponse({'success': False, 'error': '허용되지 않는 커맨드입니다.'}, status=400)
        with open(_CMD_FILE, 'w') as f:
            json.dump({'cmd': cmd, 'ts': _time.time()}, f)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
