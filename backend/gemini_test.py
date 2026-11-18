"""Gemini 요청 계약·오류 복구 검증. 실제 네트워크·키를 사용하지 않는다."""
import os as _os, tempfile as _tf; _os.environ.setdefault("MIA_DB_PATH", _os.path.join(_tf.mkdtemp(), "test.db"))  # 테스트는 임시 DB 사용
import json
import os
import unittest
from unittest.mock import patch
import httpx
from app import ai, gemini, harness


class GeminiTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'test-only', 'LLM_MODEL_FAST': 'gemini-2.5-flash'})
        env.start()
        self.addCleanup(env.stop)
        client = patch('app.gemini.httpx.Client')
        self.post = client.start().return_value.__enter__.return_value.post
        self.addCleanup(client.stop)
        self.scenario = harness.SCENARIOS['fire_office']
        self.stage = self.scenario['stages'][0]
        self.character = self.scenario['characters'][0]

    def response(self, text=None):
        reply = text or json.dumps({'verdict': 'correct', 'reply': '알았어!', 'reason': 'action'})
        return httpx.Response(200, json={
            'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': reply}]}}],
            'usageMetadata': {'promptTokenCount': 30, 'candidatesTokenCount': 12, 'totalTokenCount': 42},
        })

    def judge(self):
        return ai.judge_action(self.scenario, self.stage, self.character, '불이야! 119 신고할게요', [])

    def test_contract_and_key_in_header_only(self):
        self.post.return_value = self.response()
        result = self.judge()
        self.assertEqual(result['verdict'], 'correct')
        self.assertEqual(result['usage']['totalTokenCount'], 42)
        args, kwargs = self.post.call_args
        self.assertNotIn('test-only', args[0])
        self.assertEqual(kwargs['headers']['x-goog-api-key'], 'test-only')
        self.assertEqual(kwargs['json']['generationConfig']['responseMimeType'], 'application/json')

    def test_bad_json_retries_once(self):
        self.post.side_effect = [self.response('not json'), self.response()]
        self.assertEqual(self.judge()['verdict'], 'correct')
        self.assertEqual(self.post.call_count, 2)

    def test_invalid_object_falls_back(self):
        self.post.return_value = self.response('[]')
        self.assertEqual(self.judge()['reason'], 'fallback')
        self.assertEqual(self.post.call_count, 2)

    def test_auth_and_quota_do_not_retry_or_log_body(self):
        for status in [400, 401, 403, 429]:
            with self.subTest(status=status):
                self.post.reset_mock()
                self.post.return_value = httpx.Response(status, json={'error': 'test-only'})
                with self.assertLogs('mia.ai') as logs:
                    self.assertEqual(self.judge()['reason'], 'fallback')
                self.assertNotIn('test-only', str(logs.output))
                self.assertEqual(self.post.call_count, 1)

    def test_server_error_retries_once(self):
        self.post.side_effect = [httpx.Response(503), self.response()]
        self.assertEqual(self.judge()['verdict'], 'correct')

    def test_refusal_does_not_retry(self):
        self.post.return_value = httpx.Response(200, json={'promptFeedback': {'blockReason': 'SAFETY'}})
        self.assertEqual(self.judge()['reason'], 'fallback')
        self.assertEqual(self.post.call_count, 1)

    def test_no_key_is_offline(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            self.assertTrue(self.judge()['reason'].startswith('mock:'))
        self.post.assert_not_called()

    def test_current_model_does_not_send_legacy_thinking_budget(self):
        with patch.dict(os.environ, {'LLM_MODEL_FAST': 'gemini-3.1-flash-lite'}):
            self.post.return_value = self.response()
            self.assertEqual(self.judge()['verdict'], 'correct')
        config = self.post.call_args.kwargs['json']['generationConfig']
        self.assertNotIn('thinkingConfig', config)


if __name__ == '__main__':
    unittest.main()
