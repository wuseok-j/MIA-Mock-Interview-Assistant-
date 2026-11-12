"""1주차 첫 실행 확인: 면접 질문 1개를 받아오고 토큰 사용량과 예상 비용을 출력한다.

실행: python first_run.py
결과 화면을 캡처해 주간 점검 자료에 넣는다.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

api_key = os.getenv("LLM_API_KEY")
model = os.getenv("LLM_MODEL_FAST", "claude-haiku-5-5")
if not api_key or api_key.startswith("여기에"):
    sys.exit("❌ .env 파일에 LLM_API_KEY 를 먼저 입력하세요.")

client = anthropic.Anthropic(api_key=api_key)

SYSTEM = (
    "당신은 IT 기업의 신입 백엔드 개발자 채용 면접관입니다. "
    "질문은 한 문장, 존댓말로 하고 정답이나 해설은 말하지 않습니다."
)

start = time.time()
try:
    res = client.messages.create(
        model=model,
        max_tokens=200,
        system=SYSTEM,
        messages=[{"role": "user", "content": "데이터베이스 분야의 면접 질문 1개를 해 주세요."}],
    )
except anthropic.APIError as e:
    sys.exit(f"❌ API 호출 실패: {e}")
elapsed = time.time() - start

question = res.content[0].text.strip()
in_tok, out_tok = res.usage.input_tokens, res.usage.output_tokens

price_in = float(os.getenv("PRICE_FAST_INPUT_PER_M", 0))
price_out = float(os.getenv("PRICE_FAST_OUTPUT_PER_M", 0))
krw = float(os.getenv("USD_TO_KRW", 1400))
cost_usd = in_tok * price_in / 1_000_000 + out_tok * price_out / 1_000_000

print("=" * 50)
print(f"모델       : {model}")
print(f"응답 시간  : {elapsed:.2f}초")
print(f"면접 질문  : {question}")
print(f"입력 토큰  : {in_tok}")
print(f"출력 토큰  : {out_tok}")
if price_in or price_out:
    print(f"예상 비용  : ${cost_usd:.6f} (약 {cost_usd * krw:.2f}원)")
else:
    print("예상 비용  : .env 에 PRICE_* 값을 넣으면 계산됩니다")
print("=" * 50)
