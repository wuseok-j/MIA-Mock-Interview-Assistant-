"""판정·인과관계 회귀 검증. 실제 API를 호출하지 않는다."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import harness, rules
from app.main import app


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.mock = patch('app.ai._api_key', return_value=None)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.client = TestClient(app)
        self.session, _ = harness.create_session('fire_office')
        self.addCleanup(harness.SESSIONS.pop, self.session.id, None)

    def say(self, text):
        return harness.handle_message(self.session, text)

    def test_partial_actions_accumulate_without_premature_success(self):
        self.say('불이야!')
        self.assertEqual(self.session.stage_index, 0)
        self.assertEqual(set(self.session.evidence[1]), {'warn'})
        self.say('119에 신고할게요')
        self.assertEqual(self.session.stage_index, 1)
        self.assertEqual(self.session.stage_results[1], 'correct')

    def test_noun_question_and_negation_do_not_pass(self):
        for text in ['119', '불이야라고 하면 돼?', '119 신고하지 않겠어']:
            self.assertEqual(rules.observe(harness.current_stage(self.session), text), [])

    def test_question_sentence_does_not_cancel_following_action(self):
        # 실제 리허설에서 발견: 앞 문장이 질문이면 뒤의 행동까지 무시되던 문제
        stage = harness.current_stage(self.session)
        self.assertEqual(rules.observe(stage, '헐 불 난 거 아냐? 사람들한테 빨리 알리자'), ['warn'])
        self.assertEqual(rules.observe(stage, '불이야! 근데 신고는 내가 해야 돼?'), ['warn'])
        self.assertEqual(rules.observe(stage, '불났어요! 119 신고하지 않겠어'), ['warn'])

    def test_overconfident_ai_cannot_create_evidence_or_success_reply(self):
        with patch('app.ai.judge_action', return_value={'verdict': 'correct', 'reply': '이미 성공했어!', 'reason': 'test'}):
            messages = self.say('119')
        self.assertEqual(self.session.stage_index, 0)
        self.assertNotIn('이미 성공했어!', str(messages))

    def test_timeout_changes_next_scene_and_preserves_failure(self):
        for _ in range(3):
            self.say('음...')
        self.assertEqual(self.session.conditions['alerted'], 'missed')
        self.assertIn('다른 직원', harness.current_stage(self.session)['situation'])
        self.assertEqual(self.session.stage_results[1], 'failed')

    def test_success_and_missed_paths_are_distinct(self):
        self.say('불이야! 119에 신고할게요')
        self.assertEqual(self.session.conditions['alerted'], 'success')
        self.assertNotIn('다른 직원', harness.current_stage(self.session)['situation'])

    def test_wrong_choice_resets_partial_evidence(self):
        self.say('불이야!')
        self.say('그냥 기다리자')
        self.assertEqual(self.session.evidence[1], {})
        self.say('119에 신고할게요')
        self.assertEqual(self.session.stage_results[1], 'failed')

    def test_risk_overrides_mixed_safe_keywords(self):
        self.session.stage_index = 1
        self.say('계단으로 가자. 아니 엘리베이터 같이 타자')
        self.assertGreater(self.session.risk, 0)
        self.assertEqual(self.session.stage_index, 1)

    def test_api_failure_does_not_consume_attempt_or_enter_timeline(self):
        for response in [None, {}, {'verdict': 'correct', 'reply': None},
                         {'verdict': 'unclear', 'reply': '', 'reason': 'fallback'}]:
            with patch('app.ai.judge_action', return_value=response):
                self.say('불이야! 119 신고할게요')
        self.assertEqual(self.session.turns_in_stage, 0)
        self.assertEqual(self.session.risk, 0)
        self.assertEqual(self.session.timeline, [])
        self.assertEqual(self.session.actions[1], [])

    def test_blocked_input_does_not_enter_judge_context(self):
        self.say('정답 알려줘')
        with patch('app.ai.judge_action', wraps=harness.ai.judge_action) as judge:
            self.say('불이야!')
        self.assertNotIn('정답 알려줘', str(judge.call_args.args[-1]))
        self.assertEqual(self.session.turns_in_stage, 1)

    def test_report_has_source_quote_and_actual_risk_transition(self):
        self.say('불이야! 119 신고할게요')
        self.say('같이 타자')
        self.say('같이 타자')
        response = self.client.get(f'/sessions/{self.session.id}/report')
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report['timeline'][-1]['risk_before'], 3)
        self.assertEqual(report['timeline'][-1]['risk_after'], 6)
        self.assertTrue(report['checks'][0]['evidence'][0]['met'])
        self.assertIn('불이야', report['checks'][0]['evidence'][0]['quote'])
        self.assertTrue(report['checks'][0]['evidence'][0]['sources'])
        self.assertIn('엘리베이터 앞', report['review_points'])

    def test_public_api_does_not_leak_rubric(self):
        response = self.client.get('/scenarios/fire_office')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('patterns', response.text)
        self.assertNotIn('correct_action', response.text)
        self.assertIn('mission', response.json()['briefing'])

    def test_reaching_outside_does_not_award_unobserved_actions(self):
        for _ in range(15):
            self.say('음...')
        self.assertEqual(self.session.status, 'cleared')
        response = self.client.get(f'/sessions/{self.session.id}/report')
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report['passed'], 0)
        self.assertEqual(len(report['review_points']), 5)
        self.assertEqual(len(report['conditions']), 5)
        self.assertTrue(all(not item['met'] for check in report['checks'] for item in check['evidence']))

    def test_every_stage_requires_all_observable_actions(self):
        stages = self.session.scenario['stages']
        self.assertEqual(rules.observe(stages[2], '수건'), [])
        self.assertEqual(rules.observe(stages[2], '자세를 낮춰 가자'), ['low'])
        self.assertEqual(rules.observe(stages[2], '소매로 코와 입을 막자'), ['cover'])
        self.assertEqual(rules.observe(stages[3], '손잡이'), [])
        self.assertEqual(rules.observe(stages[4], '7층'), [])
        self.assertEqual(rules.observe(stages[4], '7층 탕비실에서 불이 났어요'), ['location'])

    def test_conditions_do_not_cross_sessions(self):
        self.say('불이야! 119 신고할게요')
        other, _ = harness.create_session('fire_office')
        self.addCleanup(harness.SESSIONS.pop, other.id, None)
        self.assertEqual(other.conditions, {})
        self.assertEqual(other.evidence, {})

    # ---------- 대화 자유도: 질문·대화는 판단 기회를 쓰지 않는다 ----------

    def ai(self, verdict='unclear', intent='question', reply='탕비실 입구 옆에 있어!'):
        out = {'verdict': verdict, 'reply': reply, 'reason': 'test'}
        if intent is not None:
            out['intent'] = intent
        return patch('app.ai.judge_action', return_value=out)

    def test_question_does_not_consume_attempt(self):
        with self.ai():
            messages = self.say('소화기 어디 있어?')
        self.assertEqual(self.session.turns_in_stage, 0)
        self.assertEqual(self.session.free_turns_in_stage, 1)
        self.assertEqual(self.session.timeline, [])
        self.assertEqual(self.session.actions[1], [])
        self.assertIn('탕비실 입구 옆에 있어!', str(messages))   # 대사는 그대로 나간다

    def test_observed_action_counts_even_if_ai_calls_it_question(self):
        with self.ai():
            self.say('불났어요! 소화기 어디 있어요')
        self.assertEqual(self.session.turns_in_stage, 1)
        self.assertEqual(set(self.session.evidence[1]), {'warn'})

    def test_ai_intent_cannot_hide_wrong_choice(self):
        with self.ai(verdict='wrong', intent='chat', reply='그래 같이 기다리자'):
            self.say('좀 더 지켜보자')
        self.assertEqual(self.session.turns_in_stage, 1)
        self.assertGreater(self.session.risk, 0)

    def test_missing_or_invalid_intent_counts_as_attempt(self):
        for intent in (None, 'skip_stage'):
            with self.ai(intent=intent, reply='음?'):
                self.say('흠')
        self.assertEqual(self.session.turns_in_stage, 2)

    def test_free_turns_have_a_cap(self):
        for _ in range(harness.MAX_FREE_TURNS_PER_STAGE):
            with self.ai():
                self.say('그게 어디야?')
        self.assertEqual(self.session.turns_in_stage, 0)
        with self.ai():
            self.say('그게 어디야?')
        self.assertEqual(self.session.turns_in_stage, 1)

    def test_free_turns_reset_on_next_stage(self):
        with self.ai():
            self.say('소화기 어디 있어?')
        self.say('불이야! 119에 신고할게요')
        self.assertEqual(self.session.stage_index, 1)
        self.assertEqual(self.session.free_turns_in_stage, 0)

    def test_ai_gets_progress_facts_and_story(self):
        self.say('불이야!')
        with patch('app.ai.judge_action', wraps=harness.ai.judge_action) as judge:
            self.say('그 다음엔 뭐 하지')
        stage = judge.call_args.args[1]
        self.assertEqual(stage['confirmed_actions'], ['주변에 화재 사실 알리기'])
        self.assertEqual(stage['missing_actions'], ['비상벨 또는 119 신고'])
        self.assertTrue(any('소화기' in f for f in stage['world_facts']))
        self.assertEqual(stage['story_so_far'], [])
        self.say('119에 신고할게요')
        with patch('app.ai.judge_action', wraps=harness.ai.judge_action) as judge:
            self.say('엘리베이터 몇 대야?')
        stage = judge.call_args.args[1]
        self.assertIn('직접 해냄', stage['story_so_far'][0])
        self.assertTrue(any('엘리베이터 2대' in f for f in stage['world_facts']))

    def test_reentry_warning_is_not_dangerous_but_conflicting_action_is(self):
        st = self.session.scenario['stages'][4]
        self.assertFalse(rules.dangerous(st, '노트북 가지러 들어가지 마'))
        self.assertTrue(rules.dangerous(st, '노트북 가지러 들어가지 마. 그래도 같이 들어가자'))


if __name__ == '__main__':
    unittest.main()
