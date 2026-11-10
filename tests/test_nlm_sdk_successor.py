from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_sdk_adapter_v2 import dependency_preflight, parse_answer
from nlm_runtime import validate_response


class SuccessorDelta(unittest.TestCase):
    def test_real_http2_lazy_dependencies_before_admission(self):
        value=dependency_preflight({'h2':'4.3.0','hpack':'4.1.0','hyperframe':'6.1.0'})
        self.assertEqual(value['h2']['version'],'4.3.0')
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_VERSION'):
            dependency_preflight({'h2':'missing'})

    def test_teng_actual_references_pass_existing_runtime(self):
        source='11111111-2222-3333-4444-555555555555'
        quote='云鹤𠮷😀 e\u0301';width=len(quote.encode('utf-16-le'))//2
        passage=[['22222222-2222-3333-4444-555555555555'],[None,None,.9,[[None,0,width]],[[[0,width,[[[0,width,[quote]]]]]]],[[[source]]]]]
        row=['终答 [1]',None,['stream-id','turn-id',123],None,[None,None,None,[passage],1]]
        raw=json.dumps([['wrb.fr',None,json.dumps([row,None,None,None,True])]])
        value=parse_answer('teng',None,raw)
        self.assertEqual(value['citations'],{'1':source})
        self.assertEqual(value['references'][0]['end_char'],width)
        self.assertEqual(value['references'][0]['cited_text'],quote)
        value.update(conversation_id='persistent',notebook_id='new-book')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw.json';p.write_text(json.dumps(value))
            self.assertEqual(validate_response({'operation':'query','notebook_id':'new-book','source_ids':[source],'conversation_id':'persistent'},p),'persistent')


if __name__=='__main__':unittest.main()
