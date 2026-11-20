"""Offline SDK contracts built from synthetic wire rows, never saved responses."""
import ast
import copy
from importlib.util import find_spec
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from nlm_citation_tables import _selected_row, _tables, retain_teng_citation_tables
from nlm_sdk_adapter_v2 import parse_answer as parse_before_tables
from nlm_sdk_adapter_v3 import json_value, parse_answer


TENG_AVAILABLE = find_spec('notebooklm') is not None
JACOB_AVAILABLE = find_spec('notebooklm_tools') is not None
# Deliberately synthetic IDs; these fixtures have no notebook or account binding.
SOURCE_A = '11111111-1111-4111-8111-111111111111'
SOURCE_B = '22222222-2222-4222-8222-222222222222'
CHUNK_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
CHUNK_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
ADDED_FIELDS = {'cited_fragment_raw', 'cited_tables', 'cited_table'}


def utf16_width(text):
    return len(text.encode('utf-16-le')) // 2


def paragraph(text, start=0):
    end = start + utf16_width(text)
    return [start, end, [[[start, end, [text]]]]]


def table(rows, start=0):
    """Encode the SDK's documented StructuralElement table/cell positions."""
    cursor = start
    wire_rows = []
    for row in rows:
        row_start = cursor
        cells = []
        for text in row:
            content = paragraph(text, cursor)
            cells.append([cursor, content[1], [content]])
            cursor = content[1]
        wire_rows.append([row_start, cursor, cells])
    return [start, cursor, None, None,
            [len(rows), len(rows[0]) if rows else 0, wire_rows]]


def citation(elements, source=SOURCE_A, chunk=CHUNK_A):
    start = min((element[0] for element in elements), default=0)
    end = max((element[1] for element in elements), default=0)
    detail = [None, None, .75, [[None, start, end]], [elements], [[[source]]]]
    return [[chunk], detail]


def frame(answer, citations, *, final=True, marked=True):
    row = [answer, None, ['synthetic-stream', 'synthetic-turn', 123], None,
           [None, None, None, citations, 1 if marked else 0]]
    inner = [row, None, None, None, final]
    return json.dumps([['wrb.fr', None, json.dumps(inner, ensure_ascii=False)]],
                      ensure_ascii=False)


def raw_table(rows, *, answer='Synthetic answer [1]', start=0):
    return frame(answer, [citation([table(rows, start)])])


class OrdinaryEntryIdentityContract(unittest.TestCase):
    def test_request_conversation_is_not_replaced_by_wire_identity(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'nlm_sdk_entry.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        updates = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'update'):
                continue
            fields = {keyword.arg: keyword.value for keyword in node.keywords}
            if 'request_conversation_id' not in fields:
                continue
            updates.append(fields)
            for original in (None, 'synthetic-persistent-conversation'):
                environment = {'request': {'conversation_id': original},
                               'wire_id': 'synthetic-stream-id'}
                actual = {
                    key: eval(compile(ast.Expression(fields[key]), '<identity-contract>', 'eval'),
                              {'__builtins__': {}}, environment)
                    for key in ('request_conversation_id', 'wire_conversation_id')
                }
                self.assertEqual(actual, {'request_conversation_id': original,
                                          'wire_conversation_id': 'synthetic-stream-id'})
        self.assertEqual(len(updates), 1)


@unittest.skipUnless(TENG_AVAILABLE, 'optional Teng SDK: run dedicated SDK CI job')
class CitationTableContracts(unittest.TestCase):
    def setUp(self):
        # Parsers need no client, auth, transport or sockets. Fail if that changes.
        for target in ('socket.create_connection', 'socket.socket.connect',
                       'socket.socket.connect_ex'):
            blocker = patch(target, side_effect=AssertionError('OFFLINE_NETWORK_FORBIDDEN'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def parse(self, raw):
        return parse_answer('teng', None, raw)

    def test_table_enrichment_preserves_every_existing_sdk_field(self):
        raw = raw_table([['Year', 'Visits'], ['2030', '12']], start=17)
        before = json_value(parse_before_tables('teng', None, raw))
        enriched = self.parse(raw)
        restored = copy.deepcopy(enriched)
        for reference in restored['references']:
            for key in ADDED_FIELDS:
                reference.pop(key, None)
        self.assertEqual(restored, before)
        ref = enriched['references'][0]
        expected = {'num_columns': 2, 'rows': [['Year', 'Visits'], ['2030', '12']]}
        self.assertEqual(ref['cited_table'], expected)
        self.assertEqual(ref['cited_tables'], [expected])
        self.assertEqual(enriched['citations'], {'1': SOURCE_A})
        self.assertEqual(enriched['sources_used'], [SOURCE_A])
        self.assertEqual((ref['start_char'], ref['end_char']), (17, 33))
        self.assertEqual(json.loads(json.dumps(enriched, ensure_ascii=False)), enriched)

    def test_raw_fragment_is_retained_with_coordinates_and_plain_blocks(self):
        elements = [paragraph('prefix', 4), table([['A', 'B']], 10)]
        raw = frame('Synthetic [1]', [citation(elements)])
        value = self.parse(raw)
        self.assertEqual(value['references'][0]['cited_fragment_raw'], elements)
        self.assertEqual(value['references'][0]['cited_table']['rows'], [['A', 'B']])

    def test_unicode_combining_marks_and_empty_cells(self):
        rows = [['', '𠮷😀 e\u0301'], ['é', '']]
        value = self.parse(raw_table(rows, start=3))
        ref = value['references'][0]
        self.assertEqual(ref['cited_table']['rows'], rows)
        self.assertEqual(ref['end_char'], 3 + sum(utf16_width(c) for r in rows for c in r))

    def test_multiple_paragraph_runs_in_one_cell(self):
        segment = table([['AB']], start=7)
        segment[4][2][0][2][0][2] = [paragraph('A', 7), paragraph('B', 8)]
        value = self.parse(frame('Synthetic [1]', [citation([segment])]))
        self.assertEqual(value['references'][0]['cited_table']['rows'], [['AB']])

    def test_nested_table_is_preserved_separately(self):
        inner = table([['X', 'Y']])
        outer = table([['XY']])
        outer[4][2][0][2][0][2] = [inner]
        ref = self.parse(frame('Synthetic [1]', [citation([outer])]))['references'][0]
        self.assertEqual(ref['cited_tables'], [
            {'num_columns': 1, 'rows': [['XY']]},
            {'num_columns': 2, 'rows': [['X', 'Y']]},
        ])
        self.assertNotIn('cited_table', ref)
        self.assertEqual(ref['cited_fragment_raw'], [outer])

    def test_parent_table_bounds_trim_cell_text(self):
        segment = table([['AB']])
        segment[1] = 1  # The table owns only A; row and cell still claim AB.
        ref = self.parse(frame('Synthetic [1]', [citation([segment])]))['references'][0]
        self.assertEqual(ref['cited_text'], 'A')
        self.assertEqual((ref['start_char'], ref['end_char']), (0, 1))
        self.assertEqual(ref['cited_table'], {'num_columns': 1, 'rows': [['A']]})
        self.assertEqual(ref['cited_fragment_raw'], [segment])

    def test_parent_row_bounds_trim_both_ends_of_cell_text(self):
        segment = table([['ABCD']])
        segment[4][2][0][:2] = [1, 3]  # Row owns BC inside the wider table.
        ref = self.parse(frame('Synthetic [1]', [citation([segment])]))['references'][0]
        self.assertEqual(ref['cited_text'], 'BC')
        self.assertEqual((ref['start_char'], ref['end_char']), (0, 4))
        self.assertEqual(ref['cited_table'], {'num_columns': 1, 'rows': [['BC']]})

    def test_nested_table_inherits_outer_cell_effective_bounds(self):
        inner = table([['AB']])
        outer = table([['A']])
        outer[4][2][0][2][0][2] = [inner]
        ref = self.parse(frame('Synthetic [1]', [citation([outer])]))['references'][0]
        self.assertEqual(ref['cited_text'], 'A')
        self.assertEqual(ref['cited_tables'], [
            {'num_columns': 1, 'rows': [['A']]},
            {'num_columns': 1, 'rows': [['A']]},
        ])
        self.assertNotIn('cited_table', ref)
        self.assertEqual(ref['cited_fragment_raw'], [outer])

    def test_empty_parent_cell_intersection_preserves_column(self):
        segment = table([['A', 'B']])
        segment[1] = 1  # Second cell intersects the table at [1, 1].
        ref = self.parse(frame('Synthetic [1]', [citation([segment])]))['references'][0]
        self.assertEqual(ref['cited_text'], 'A')
        self.assertEqual(ref['cited_table'], {'num_columns': 2, 'rows': [['A', '']]})
        self.assertEqual(ref['cited_fragment_raw'], [segment])

    def test_parent_bounds_clip_chinese_text_in_utf16_units(self):
        segment = table([['甲𠮷乙']], start=10)
        segment[:2] = [11, 13]  # The astral CJK character occupies two units.
        ref = self.parse(frame('Synthetic [1]', [citation([segment])]))['references'][0]
        self.assertEqual(ref['cited_text'], '𠮷')
        self.assertEqual((ref['start_char'], ref['end_char']), (11, 13))
        self.assertEqual(ref['cited_table'], {'num_columns': 1, 'rows': [['𠮷']]})
        self.assertEqual(utf16_width(ref['cited_table']['rows'][0][0]), 2)
        self.assertEqual(ref['cited_fragment_raw'], [segment])

    def test_multiple_tables_do_not_advertise_a_single_table(self):
        elements = [table([['A', 'B']]), table([['Z']], start=20)]
        ref = self.parse(frame('Synthetic [1]', [citation(elements)]))['references'][0]
        self.assertEqual(ref['cited_tables'], [
            {'num_columns': 2, 'rows': [['A', 'B']]},
            {'num_columns': 1, 'rows': [['Z']]},
        ])
        self.assertNotIn('cited_table', ref)

    def test_plain_reference_has_no_invented_table_fields(self):
        raw = frame('Synthetic [1]', [citation([paragraph('plain text')])])
        self.assertEqual(self.parse(raw), json_value(parse_before_tables('teng', None, raw)))
        self.assertFalse(ADDED_FIELDS.intersection(self.parse(raw)['references'][0]))

    def test_absent_fragment_keeps_reference_without_a_table(self):
        cite = citation([paragraph('text')])
        cite[1][4] = None
        raw = frame('Synthetic [1]', [cite])
        ref = self.parse(raw)['references'][0]
        self.assertEqual(ref['source_id'], SOURCE_A)
        self.assertIsNone(ref['cited_text'])
        self.assertFalse(ADDED_FIELDS.intersection(ref))

    def test_zero_row_table_is_explicitly_retained(self):
        self.assertEqual(_tables([table([])]), [{'num_columns': 0, 'rows': []}])

    def test_shorter_final_answer_and_its_table_win_together(self):
        earlier = frame('A much longer provisional answer [1]', [citation([table([['old']])])], final=False)
        final = raw_table([['new']], answer='Final [1]')
        value = self.parse(earlier + '\n' + final)
        self.assertEqual(value['answer'], 'Final [1]')
        self.assertEqual(value['references'][0]['cited_table']['rows'], [['new']])

    def test_equal_answer_text_does_not_select_an_earlier_source_table(self):
        early = frame('Same answer [1]', [citation([table([['old']])])], final=False)
        last = frame('Same answer [1]', [citation([table([['new']])], SOURCE_B, CHUNK_B)])
        value = self.parse(early + '\n' + last)
        self.assertEqual(value['references'][0]['source_id'], SOURCE_B)
        self.assertEqual(value['references'][0]['cited_table']['rows'], [['new']])

    def test_final_without_table_does_not_backfill_from_earlier_chunk(self):
        early = frame('Provisional [1]', [citation([table([['old']])])], final=False)
        last = frame('Final [1]', [citation([paragraph('plain')])])
        value = self.parse(early + '\n' + last)
        self.assertEqual(value['answer'], 'Final [1]')
        self.assertFalse(ADDED_FIELDS.intersection(value['references'][0]))

    def test_selection_without_final_uses_longest_marked_chunk(self):
        shorter = frame('Short', [citation([table([['short']])])], final=False)
        longer = frame('Longer marked answer', [citation([table([['long']])])], final=False)
        raw = longer + '\n' + shorter
        row, chunk = _selected_row(raw)
        self.assertEqual(chunk.text, 'Longer marked answer')
        self.assertEqual(row.text, chunk.text)
        value = {'answer': chunk.text, 'references': []}
        self.assertIs(retain_teng_citation_tables(value, raw), value)

    def test_selected_chunk_must_match_the_answer_being_enriched(self):
        raw = raw_table([['A']])
        value = json_value(parse_before_tables('teng', None, raw))
        value['answer'] = 'An unrelated answer'
        with self.assertRaisesRegex(ValueError, 'ANSWER_SELECTION_MISMATCH'):
            retain_teng_citation_tables(value, raw)

    def test_no_text_bearing_chunk_is_rejected(self):
        for raw in ('', ")]}'\n", frame('', [])):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'SELECTED_CHUNK_MISSING'):
                _selected_row(raw)

    def test_raw_ordinal_hole_is_not_renumbered(self):
        raw = frame('Synthetic [2]', [[], citation([table([['B']])], SOURCE_B, CHUNK_B)])
        value = self.parse(raw)
        self.assertEqual(len(value['references']), 1)
        ref = value['references'][0]
        self.assertEqual(ref['citation_number'], 2)
        self.assertEqual(ref['source_id'], SOURCE_B)
        self.assertEqual(ref['cited_table']['rows'], [['B']])
        self.assertEqual(value['citations'], {'2': SOURCE_B})

    def test_two_sources_keep_their_own_fragments_and_ordinals(self):
        raw = frame('Synthetic [1] [2]', [citation([table([['A']])]),
                    citation([table([['B']])], SOURCE_B, CHUNK_B)])
        refs = self.parse(raw)['references']
        self.assertEqual([(r['citation_number'], r['source_id'], r['cited_table']['rows'])
                          for r in refs], [(1, SOURCE_A, [['A']]), (2, SOURCE_B, [['B']])])

    def test_source_or_source_coordinates_mismatch_is_rejected(self):
        raw = raw_table([['A']])
        baseline = json_value(parse_before_tables('teng', None, raw))
        for field, changed in [('source_id', SOURCE_B), ('start_char', 99),
                               ('end_char', 99), ('cited_text', 'unrelated')]:
            value = copy.deepcopy(baseline)
            value['references'][0][field] = changed
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'REFERENCE_MISMATCH:' + field):
                retain_teng_citation_tables(value, raw)

    def test_missing_raw_ordinal_is_rejected(self):
        raw = raw_table([['A']])
        value = json_value(parse_before_tables('teng', None, raw))
        value['references'][0]['citation_number'] = 2
        with self.assertRaisesRegex(ValueError, 'RAW_ORDINAL_MISSING'):
            retain_teng_citation_tables(value, raw)

    def test_malformed_dimensions_are_rejected(self):
        for dims in ([1], [True, 1, []], [1, False, []], [-1, 1, []],
                     [1, -1, []], [1, 1, None], [2, 1, []], 'table'):
            segment = table([['A']])
            segment[4] = dims
            with self.subTest(dims=dims), self.assertRaisesRegex(ValueError, 'TABLE_SHAPE'):
                _tables([segment])

    def test_malformed_rows_are_rejected(self):
        for row in (None, [], [0, 1, None], [0, 1, []]):
            segment = table([['A']])
            segment[4][2][0] = row
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'TABLE_ROW_SHAPE'):
                _tables([segment])

    def test_declared_column_count_cannot_hide_a_missing_cell(self):
        segment = table([['A', 'B']])
        segment[4][1] = 3
        with self.assertRaisesRegex(ValueError, 'TABLE_ROW_SHAPE'):
            _tables([segment])

    def test_malformed_cell_shape_or_bounds_is_rejected(self):
        for cell in (None, [0, 1], [0, 1, None], [-1, 1, []],
                     [2, 1, []], [False, 1, []], [0, True, []], ['0', 1, []]):
            segment = table([['A']])
            segment[4][2][0][2][0] = cell
            with self.subTest(cell=cell), self.assertRaisesRegex(ValueError, 'TABLE_CELL_SHAPE'):
                _tables([segment])

    def test_malformed_table_is_not_silently_lost_by_adapter(self):
        segment = table([['A']])
        segment[4][1] = 2
        raw = frame('Synthetic [1]', [citation([segment])])
        with self.assertRaisesRegex(ValueError, 'TABLE_ROW_SHAPE'):
            self.parse(raw)

    def test_deeply_nested_tables_fail_with_a_bounded_error(self):
        segment = table([['X']])
        for _ in range(22):
            parent = table([['X']])
            parent[4][2][0][2][0][2] = [segment]
            segment = parent
        with self.assertRaisesRegex(ValueError, 'TABLE_DEPTH'):
            _tables([segment])

    @unittest.skipUnless(JACOB_AVAILABLE, 'optional Jacob SDK: run dedicated SDK CI job')
    def test_jacob_table_and_all_existing_fields_are_unchanged(self):
        from notebooklm_tools.core.conversation import ConversationMixin
        parser = object.__new__(ConversationMixin)
        raw = raw_table([['Label', 'Value'], ['𠮷😀 e\u0301', '7']])
        before = json_value(parse_before_tables('jacob', parser, raw))
        with patch('nlm_citation_tables.retain_teng_citation_tables',
                   side_effect=AssertionError('TENG_ENRICHMENT_MUST_NOT_RUN_FOR_JACOB')):
            value = parse_answer('jacob', parser, raw)
        self.assertEqual(value, before)
        self.assertEqual(value['references'][0]['source_id'], SOURCE_A)
        self.assertEqual(value['references'][0]['cited_table']['rows'],
                         [['Label', 'Value'], ['𠮷😀 e\u0301', '7']])


if __name__ == '__main__':
    unittest.main()
