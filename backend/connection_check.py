"""Gemini 실제 연결 확인. 키는 출력하지 않는다."""
import logging
import os
import sys
import time
from app import ai, harness


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    if not ai._api_key():
        sys.exit('루트 .env의 GEMINI_API_KEY와 LLM_PROVIDER=gemini를 확인해 주세요.')
    scenario = harness.SCENARIOS['fire_office']
    stage = scenario['stages'][0]
    character = next(c for c in scenario['characters'] if c['id'] == stage['character_id'])
    started = time.monotonic()
    result = ai.judge_action(scenario, stage, character, '불이야! 비상벨을 누르고 119에 신고할게요.', [])
    if result.get('reason') == 'fallback':
        sys.exit('Gemini 연결 검증 실패. 로그의 HTTP 상태와 모델·할당량·키 설정을 확인하세요.')
    usage = result.get('usage', {})
    print(f"모델: {result.get('model', 'unknown')}")
    print(f"소요 시간: {time.monotonic() - started:.2f}초")
    print(f"판정: {result['verdict']}")
    print(f"대사: {result['reply']}")
    print(f"입력 토큰: {usage.get('promptTokenCount', 0)} / 출력 토큰: {usage.get('candidatesTokenCount', 0)} / 전체 토큰: {usage.get('totalTokenCount', 0)}")
    price_in = float(os.getenv('PRICE_FAST_INPUT_PER_M', 0))
    price_out = float(os.getenv('PRICE_FAST_OUTPUT_PER_M', 0))
    if price_in > 0 and price_out > 0:
        output = usage.get('candidatesTokenCount', 0) + usage.get('thoughtsTokenCount', 0)
        cost = (usage.get('promptTokenCount', 0) * price_in + output * price_out) / 1_000_000
        print(f'설정 단가 기준 예상 비용: ${cost:.6f}')
    else:
        print('비용: 가격 설정이 없어 계산하지 않았습니다.')


if __name__ == '__main__':
    main()
