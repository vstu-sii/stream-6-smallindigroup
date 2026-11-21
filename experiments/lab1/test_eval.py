"""Checks that the evaluation cannot report a vacuous pass or leak golden labels."""
import copy
import unittest
from run import evaluate, messages, validate


class EvaluationTests(unittest.TestCase):
    def record(self, problems=None):
        return {'id':'test', 'input':{'text':'Товар пахнет краской.'},
                'expected':{'problems': problems or [], 'sentiment':'negative',
                            'severity':'medium','owner':'seller',
                            'suspicious':False,'has_instruction':False}}

    def prediction(self, problems=None):
        return {'problems': problems or [], 'sentiment':'negative', 'severity':'medium',
                'owner':'seller', 'suspicious':False,'has_instruction':False}

    def metric(self, rec, pred):
        return evaluate([rec],[{'id':'test','prediction':pred,'latency_seconds':0}])

    def test_empty_denominator_is_unknown(self):
        m=self.metric(self.record(),self.prediction())
        self.assertIsNone(m['problem_precision'])
        self.assertIsNone(m['literal_evidence']['ratio'])
        self.assertIsNone(m['critical_recall']['ratio'])

    def test_false_positive_is_counted(self):
        m=self.metric(self.record(),self.prediction([{'code':'smell','evidence':'пахнет краской'}]))
        self.assertEqual(m['fp'],1)
        self.assertEqual(m['problem_precision'],0)

    def test_missing_prediction_is_failure(self):
        m=self.metric(self.record([{'code':'smell'}]),None)
        self.assertEqual(m['fn'],1)
        self.assertEqual(m['schema_valid'],0)

    def test_fabricated_quote_is_rejected(self):
        m=self.metric(self.record(),self.prediction([{'code':'smell','evidence':'воняет химией'}]))
        self.assertEqual(m['literal_evidence']['ratio'],0)

    def test_gold_never_enters_prompt(self):
        rec=self.record([{'code':'secret_gold_label'}]); rec['tags']=['secret_tag']
        self.assertNotIn('secret',str(messages(rec,'fixed prompt')))

    def test_duplicate_codes_are_invalid(self):
        p={'code':'smell','evidence':'краской'}
        with self.assertRaises(AssertionError): validate(self.prediction([p,copy.copy(p)]))

    def test_alignment_is_checked(self):
        with self.assertRaises(AssertionError): evaluate([self.record()],[])


if __name__ == '__main__': unittest.main()
