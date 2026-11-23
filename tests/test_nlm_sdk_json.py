import json
from importlib.util import find_spec
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_sdk_adapter_v3 import json_value


@unittest.skipUnless(find_spec("notebooklm"), "optional Teng SDK: run dedicated SDK CI job")
class RealDocumentJson(unittest.TestCase):
    def test_nested_sdk_enum_keeps_field_and_value(self):
        from notebooklm._types.documents import BlockStyle
        original={'answer_document':{'blocks':[{'style':BlockStyle.UNSPECIFIED,'text':'𠮷😀'}]},'references':[{'end_char':4}]}
        serialized=json.loads(json.dumps(json_value(original),ensure_ascii=False))
        self.assertEqual(serialized['answer_document']['blocks'][0],{'style':0,'text':'𠮷😀'})
        self.assertEqual(serialized['references'],original['references'])


if __name__=='__main__':unittest.main()
