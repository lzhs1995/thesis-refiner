import asyncio
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from types import SimpleNamespace
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nlm_sdk_adapter import BoundedHTTP, jacob_request, teng_request, parse_answer, unique_conversation, validate_answer


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def receive(self, encoding, wire, *, idle=1, total=2, delay=0):
        import httpx
        class Bytes(httpx.AsyncByteStream):
            async def __aiter__(self):
                for i in range(0, len(wire), 3):
                    if delay:
                        await asyncio.sleep(delay)
                    yield wire[i:i+3]
        calls=[]
        async def send(request):
            calls.append(request)
            self.assertEqual(request.headers['accept-encoding'], 'gzip, deflate')
            return httpx.Response(200, headers={'content-encoding':encoding},stream=Bytes())
        with tempfile.TemporaryDirectory() as d:
            net=BoundedHTTP(d,proxy=None,cookies={},idle=idle,total=total,transport=httpx.MockTransport(send))
            try:
                result=await net.post('query','https://notebooklm.google.com/query','f.req=test')
            finally:
                self.assertEqual(len(calls),1)
            self.assertTrue(net.calls[0]['decoder_eof'])
            with self.assertRaisesRegex(ValueError,'SECOND_POST'):
                await net.post('query','https://notebooklm.google.com/query','f.req=test')
            return result

    async def test_identity_gzip_deflate_no_double_decode_unicode(self):
        text='中文𠮷😀 e\u0301 | 2024 | 100 |\n'
        data=text.encode()
        for enc,wire in [('identity',data),('gzip',gzip.compress(data)),('deflate',zlib.compress(data))]:
            self.assertEqual(await self.receive(enc,wire),text)

    async def test_missing_trailer_and_unknown_encoding(self):
        with self.assertRaisesRegex(ValueError,'TRAILER'):
            await self.receive('gzip',gzip.compress(b'complete-looking answer')[:-4])
        with self.assertRaisesRegex(ValueError,'ENCODING'):
            await self.receive('br',b'payload')

    async def test_idle_and_total_are_not_retried(self):
        with self.assertRaises(TimeoutError):
            await self.receive('identity',b'answer',idle=.01,total=1,delay=.03)
        with self.assertRaises(TimeoutError):
            await self.receive('identity',b'a'*60,idle=1,total=.04,delay=.01)


class ContractTests(unittest.TestCase):
    def test_actual_sdk_builders_explicit_sources_and_conversation(self):
        from notebooklm_tools.core.client import NotebookLMClient
        client=NotebookLMClient(cookies={},csrf_token='offline',session_id='offline',rpc_transport='http')
        def prohibited(*args,**kwargs):
            raise AssertionError('UNEXPECTED_RPC_OR_AUTH')
        client._call_rpc=prohibited
        client._refresh_auth_tokens=prohibited
        try:
            for builder in [lambda:jacob_request(client,'book','中文𠮷😀',['s1','s2'],'persistent'),
                            lambda:teng_request(SimpleNamespace(csrf_token='offline',session_id='offline',email=None),'book','中文𠮷😀',['s1','s2'],'persistent')]:
                url,body,conv=builder()
                params=json.loads(json.loads(parse_qs(body)['f.req'][0])[1])
                self.assertEqual(params[0],[[['s1']],[['s2']]])
                self.assertEqual(params[1],'中文𠮷😀')
                self.assertEqual(params[4],'persistent')
                self.assertEqual(conv,'persistent')
            _,body,conv=jacob_request(client,'book','new',['s1'],None)
            self.assertIsInstance(conv,str)
            _,body,conv=teng_request(SimpleNamespace(csrf_token='offline',session_id='offline',email=None),'book','new',['s1'],None)
            self.assertIsNone(conv)
        finally:
            client.close()

    def test_actual_sdk_final_shorter_answer_and_all_reference_fields(self):
        from notebooklm_tools.core.conversation import ConversationMixin
        from notebooklm._web.rows.chat_stream import parse_streaming_chat_response
        from dataclasses import asdict
        parser=object.__new__(ConversationMixin)
        quote='云鹤𠮷😀 e\u0301'
        width=len(quote.encode('utf-16-le'))//2
        passage=[['22222222-2222-3333-4444-555555555555'],[None,None,.9,[[None,0,width]],[[[0,width,[[[0,width,[quote]]]]]]],[[['11111111-2222-3333-4444-555555555555']]]]]
        def frame(text,final):
            row=[text,None,['stream-id','turn-id',123],None,[None,None,None,[passage],1]]
            inner=[row,None,None,None,final]
            return json.dumps([['wrb.fr',None,json.dumps(inner,ensure_ascii=False)]],ensure_ascii=False)
        raw=frame('Very long earlier answer that must not win [1]',False)+'\n'+frame('终答[1]',True)
        a=parse_answer('jacob',parser,raw)
        b=parse_answer('teng',None,raw)
        self.assertEqual(a['answer'],'终答[1]')
        self.assertEqual(b['answer'],'终答[1]')
        self.assertEqual(a['references'][0]['cited_text'],quote)
        expected=asdict(parse_streaming_chat_response(raw))
        self.assertEqual(b['references'],expected['references'])
        self.assertEqual(b['answer_document'],expected['answer_document'])
        self.assertEqual(b['references'][0]['start_char'],0)
        self.assertEqual(b['references'][0]['end_char'],width)
        self.assertNotIn('conversation_id',b)

    def test_new_metadata_contracts_do_not_relax_pdf_contract(self):
        from nlm_contracts import normalized_result
        self.assertEqual(normalized_result('notebook_create',{'created_notebook_id':'new'}),{'created_notebook_id':'new'})
        with self.assertRaises(ValueError):
            normalized_result('source_text_add',{'source_id':'s','notebook_id':'foreign'},notebook_id='own')
        # The legacy upload validator still requires a source id, independently
        # of the separately named text-source operation.
        with self.assertRaises(ValueError):
            normalized_result('source_add',{'status':'READY'},notebook_id='own')

    def test_structured_cited_table_survives_adapter(self):
        from notebooklm_tools.core.conversation import ConversationMixin
        cursor=0
        rows=[]
        for cells in [['年份','次'],['2024','100'],['2025','125']]:
            start=cursor
            entries=[]
            for text in cells:
                end=cursor+len(text)
                entries.append([cursor,end,[[cursor,end,[[[cursor,end,[text]]]]]]])
                cursor=end
            rows.append([start,cursor,entries])
        segment=[0,cursor,None,None,[3,2,rows]]
        detail=[None,None,.9,[[None,0,cursor]],[[segment]],[[['11111111-2222-3333-4444-555555555555']]]]
        passage=[['22222222-2222-3333-4444-555555555555'],detail]
        row=['100→125 [1]',None,['stream','turn',123],None,[None,None,None,[passage],1]]
        raw=json.dumps([['wrb.fr',None,json.dumps([row,None,None,None,True])]])
        value=parse_answer('jacob',object.__new__(ConversationMixin),raw)
        self.assertEqual(value['references'][0]['cited_table']['rows'],[['年份','次'],['2024','100'],['2025','125']])

    def test_stream_id_is_not_persistent_id(self):
        self.assertEqual(unique_conversation([[['11111111-2222-3333-4444-555555555555']]]),'11111111-2222-3333-4444-555555555555')
        with self.assertRaises(ValueError):
            unique_conversation([])
        with self.assertRaises(ValueError):
            unique_conversation([['11111111-2222-3333-4444-555555555555'],['11111111-2222-3333-4444-555555555556']])

    def test_fields_table_and_unicode_preserved(self):
        ref={'source_id':'s','cited_text':'𠮷😀e\u0301','cited_table':{'rows':[['甲',100],['乙',125]]},
             'answer_anchor_start_char':2,'fragment_start_char':4,'extra_future_field':{'x':1}}
        value={'answer':'甲100乙125','references':[ref],'sources_used':['s'],'conversation_id':'persistent','stream_id':'stream'}
        self.assertIs(validate_answer(value,{'source_ids':['s'],'conversation_id':'persistent'}),value)
        self.assertEqual(value['references'][0],ref)
        for changed in ({'answer':''},{'conversation_id':'other'},{'references':[{'source_id':'foreign'}]}):
            with self.assertRaises(ValueError):
                validate_answer({**value,**changed},{'source_ids':['s'],'conversation_id':'persistent'})

    def test_empty_and_nonterminal_not_complete(self):
        for raw in ['',')]}\'\n[["e",2]]','[["wrb.fr",null,"[[\"thinking\"]]"]]']:
            with self.assertRaises(ValueError):
                parse_answer('teng',None,raw)

    def test_failure_retains_budget_and_blocks_other_sdk(self):
        from nlm_runtime import Budget,AdmissionError
        with tempfile.TemporaryDirectory() as d:
            b=Budget(d);b.configure('a',{'regime':'unknown','observed_at':1,'source':'test'})
            b.allocate('a','new-task',10)
            r={'task_id':'new-task','phase':'draft','notebook_id':'new','operation':'query','round_id':'jacob-q1'}
            first=b.admit('a',r);b.finish(first['id'],'UNCERTAIN',{'path':'fixture'})
            with self.assertRaisesRegex(AdmissionError,'IN_FLIGHT'):
                b.admit('a',{**r,'round_id':'teng-q1'})
            self.assertEqual(b.report('a')['query_count'],1)
            self.assertEqual(b.report('a')['requests'][0]['state'],'UNCERTAIN')
            b.db.close()


if __name__=='__main__':
    unittest.main()
