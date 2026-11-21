import unittest
from yandex_trials import usage_cost, reserve_cost, safe_prediction


class BudgetTests(unittest.TestCase):
    def test_missing_usage_is_not_free(self):
        self.assertIsNone(usage_cost({}))
        self.assertIsNone(usage_cost({'prompt_tokens': 100}))

    def test_negative_usage_is_rejected(self):
        self.assertIsNone(usage_cost({'prompt_tokens': -1, 'completion_tokens': 10}))

    def test_cache_does_not_underestimate_cost(self):
        usage = {'prompt_tokens': 1000, 'completion_tokens': 500,
                 'prompt_tokens_details': {'cached_tokens': 900}}
        self.assertAlmostEqual(usage_cost(usage), .2)

    def test_reservation_covers_output_and_utf8_input(self):
        messages = [{'content': 'Отзыв'}]
        upper = reserve_cost(messages)
        self.assertGreaterEqual(upper, usage_cost({'prompt_tokens': 10, 'completion_tokens': 1200}))

    def test_invalid_json_is_not_silently_fixed(self):
        self.assertIsNone(safe_prediction('```json\n{}\n```'))


class FreeOnlyTests(unittest.TestCase):
    def test_paid_account_is_never_authorized(self):
        from yandex_trials import require_free_trial
        with self.assertRaises(ValueError):
            require_free_trial({'YANDEX_BILLING_STATUS':'ACTIVE'}, 5)

    def test_unconfirmed_grant_is_not_free(self):
        from yandex_trials import require_free_trial
        with self.assertRaises(ValueError):
            require_free_trial({'YANDEX_BILLING_STATUS':'TRIAL_ACTIVE'}, 5)

    def test_grant_must_cover_reserve_and_not_expire_today(self):
        from yandex_trials import require_free_trial
        from datetime import date
        cfg={'YANDEX_BILLING_STATUS':'TRIAL_ACTIVE','YANDEX_GRANT_REMAINING_RUB':'4000',
             'YANDEX_GRANT_EXPIRES':'2026-12-01'}
        self.assertEqual(require_free_trial(cfg,50,date(2026,11,21)),4000)
        with self.assertRaises(ValueError): require_free_trial(cfg,50,date(2026,12,1))
        cfg['YANDEX_GRANT_REMAINING_RUB']='3'
        with self.assertRaises(ValueError): require_free_trial(cfg,50,date(2026,11,21))


if __name__ == '__main__': unittest.main()
