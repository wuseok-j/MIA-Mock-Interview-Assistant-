"""첫 실행 확인: 화재 시나리오 캐릭터 대사 1개를 받아오고 토큰 사용량과 예상 비용을 출력한다.

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
    "당신은 재난 대응 교육 롤플레잉 속 인물 '박지훈'입니다. 사무실 동료이고 낙천적이며 성격이 급합니다. "
    "반말로 1~2문장만 말하고, 올바른 대피 방법을 먼저 알려주지 않습니다. "
    "상황: 7층 사무실 탕비실에서 연기가 새어 나오는데 당신은 별일 아니라고 생각합니다."
)
USER = "<user_input>지훈아, 탕비실에서 연기 나는 거 같은데?</user_input>"

start = time.time()
try:
    res = client.messages.create(
        model=model,
        max_tokens=200,
        system=SYSTEM,
        messages=[{"role": "user", "content": USER}],
    )
except anthropic.APIError as e:
    sys.exit(f"❌ API 호출 실패: {e}")
elapsed = time.time() - start

reply = res.content[0].text.strip()
in_tok, out_tok = res.usage.input_tokens, res.usage.output_tokens

price_in = float(os.getenv("PRICE_FAST_INPUT_PER_M", 0))
price_out = float(os.getenv("PRICE_FAST_OUTPUT_PER_M", 0))
krw = float(os.getenv("USD_TO_KRW", 1400))
cost_usd = in_tok * price_in / 1_000_000 + out_tok * price_out / 1_000_000

print("=" * 50)
print(f"모델       : {model}")
print(f"응답 시간  : {elapsed:.2f}초")
print(f"캐릭터 대사: {reply}")
print(f"입력 토큰  : {in_tok}")
print(f"출력 토큰  : {out_tok}")
if price_in or price_out:
    print(f"예상 비용  : ${cost_usd:.6f} (약 {cost_usd * krw:.2f}원)")
else:
    print("예상 비용  : .env 에 PRICE_* 값을 넣으면 계산됩니다")
print("=" * 50)
