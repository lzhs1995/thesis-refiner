import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nlm_sdk_adapter_v3 as adapter


class ApplicationErrorTests(unittest.TestCase):
    def setUp(self):
        self.raw = (Path(__file__).parent / 'fixtures/nlm-region-not-supported.raw').read_text()

    def test_exact_real_response_classified_before_sdk_parser(self):
        self.assertEqual(hashlib.sha256(self.raw.encode()).hexdigest(),
                         '1d8942522ecb4a6197e6a1d27091d017a91c72decf6955cdfb98fafe51ba1e40')
        with patch.object(adapter.previous, 'parse_answer') as parser:
            with self.assertRaises(adapter.ProviderApplicationError) as caught:
                adapter.parse_answer('jacob', None, self.raw)
            parser.assert_not_called()
        self.assertEqual(caught.exception.details, dict(category='provider_application_error',
            rpc_code=7, reason='REGION_NOT_SUPPORTED', region_code='CN'))

    def test_answer_text_mentioning_region_error_is_not_control_error(self):
        raw = json.dumps([['wrb.fr', None, 'REGION_NOT_SUPPORTED region_code CN', None, None,
                           [7, None, []]]])
        self.assertIsNone(adapter.application_error(raw))
        answer = {'answer': 'REGION_NOT_SUPPORTED is discussed in the source', 'references': []}
        with patch.object(adapter.previous, 'parse_answer', return_value=answer) as parser:
            self.assertEqual(adapter.parse_answer('jacob', None, raw), answer)
            parser.assert_called_once_with('jacob', None, raw)

    def test_other_error_malformed_and_unknown_layout_use_existing_parser(self):
        for raw in (self.raw.replace('REGION_NOT_SUPPORTED', 'QUOTA_EXCEEDED'),
                    self.raw.replace('[7,null', '[8,null'),
                    self.raw.replace('google.rpc.ErrorInfo', 'google.rpc.Other'), '[broken'):
            with self.subTest(raw=raw):
                self.assertIsNone(adapter.application_error(raw))

    def test_untrusted_metadata_not_copied_into_diagnostic(self):
        error = adapter.application_error(self.raw.replace('"CN"', '"quota exceeded 429 auth secret"'))
        self.assertEqual(error, dict(category='provider_application_error', rpc_code=7,
                                    reason='REGION_NOT_SUPPORTED'))
        self.assertNotIn('remote_terminal', error)
        self.assertNotIn('quota_refunded', error)


if __name__ == '__main__':
    unittest.main()
