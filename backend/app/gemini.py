"""Gemini REST 어댑터. 키와 오류 본문은 로그에 남기지 않는다."""
import json
import logging
import os
import re
import time
import httpx
from . import prompts

log = logging.getLogger('mia.ai')
FALLBACK = {'verdict': 'unclear', 'reply': '', 'reason': 'fallback'}


def api_key():
    key = os.getenv('GEMINI_API_KEY', '').strip()
    return key if key and not key.startswith(('여기에', 'YOUR_', '발급받은')) else None


def judge(scenario, stage, character, user_text, history):
    model = os.getenv('LLM_MODEL_FAST', 'gemini-3.1-flash-lite').strip()
    if not re.fullmatch(r'gemini-[a-zA-Z0-9.\-]+', model) or not api_key():
        log.warning('[gemini] 모델 이름 또는 키 설정 확인 필요')
        return dict(FALLBACK)
    schema = {k: v for k, v in prompts.JUDGE_SCHEMA.items() if k != 'additionalProperties'}
    payload = {
        'systemInstruction': {'parts': [{'text': prompts.judge_system(scenario, stage, character)}]},
        'contents': [{'role': 'user', 'parts': [{'text': prompts.judge_user(history, user_text)}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': schema,
                             'maxOutputTokens': 1000, 'temperature': 0.3,
                             'thinkingConfig': {'thinkingBudget': 0}},
    }
    if not model.startswith('gemini-2.5-'):
        payload['generationConfig'].pop('thinkingConfig', None)
    started = time.monotonic()
    with httpx.Client(timeout=10.0) as client:
        for attempt in range(2):
            try:
                response = client.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                    headers={'x-goog-api-key': api_key()}, json=payload)
            except httpx.RequestError:
                log.warning('[gemini] 네트워크 오류 (시도 %d/2)', attempt + 1)
                if attempt == 0:
                    continue
                return dict(FALLBACK)
            if response.status_code != 200:
                log.warning('[gemini] HTTP %d', response.status_code)
                if response.status_code in (500, 502, 503, 504) and attempt == 0:
                    continue
                return dict(FALLBACK)
            try:
                body = response.json()
                candidates = body.get('candidates') or []
                if not candidates or body.get('promptFeedback', {}).get('blockReason'):
                    return dict(FALLBACK)
                candidate = candidates[0]
                if candidate.get('finishReason') != 'STOP':
                    return dict(FALLBACK)
                text = ''.join(part.get('text', '') for part in candidate.get('content', {}).get('parts', []) if not part.get('thought'))
                data = json.loads(text)
                if (not isinstance(data, dict) or data.get('verdict') not in ('correct', 'wrong', 'unclear')
                        or not isinstance(data.get('reply'), str) or not data['reply'].strip()
                        or not isinstance(data.get('reason'), str)):
                    raise ValueError('invalid response')
                usage = body.get('usageMetadata', {})
                counts = {name: usage.get(name, 0) for name in ('promptTokenCount', 'candidatesTokenCount', 'thoughtsTokenCount', 'totalTokenCount')}
                log.info('[gemini] model=%s %.2fs in=%s out=%s total=%s', model,
                         time.monotonic() - started, counts['promptTokenCount'], counts['candidatesTokenCount'], counts['totalTokenCount'])
                # intent 가 없거나 이상하면 'action'(판단 시도)으로 본다 → 기회를 아끼는 쪽으로 잘못 갈 수 없음
                intent = data.get('intent') if data.get('intent') in ('action', 'question', 'chat') else 'action'
                return {'verdict': data['verdict'], 'intent': intent, 'reply': data['reply'].strip()[:300],
                        'reason': data['reason'][:300], 'usage': counts, 'model': model,
                        'latency_ms': round((time.monotonic() - started) * 1000)}
            except (ValueError, TypeError, AttributeError, IndexError):
                log.warning('[gemini] 응답 형식 오류 (시도 %d/2)', attempt + 1)
    return dict(FALLBACK)
