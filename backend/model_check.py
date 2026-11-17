"""키를 출력하지 않고 현재 프로젝트에서 제공하는 생성 모델을 조회한다."""
import sys
import httpx
from app import ai

if not ai._api_key():
    sys.exit('GEMINI_API_KEY 설정 필요')
try:
    with httpx.Client(timeout=10) as client:
        response = client.get('https://generativelanguage.googleapis.com/v1beta/models',
                              headers={'x-goog-api-key': ai._api_key()})
    if response.status_code != 200:
        sys.exit(f'모델 조회 HTTP {response.status_code}')
    for model in response.json().get('models', []):
        if 'generateContent' in model.get('supportedGenerationMethods', []):
            print(model['name'].removeprefix('models/'))
except httpx.RequestError:
    sys.exit('모델 조회 네트워크 오류')
