"""Retain source citation tables from the same Teng chunk selected by its SDK.

No I/O, client construction, monkeypatching, or network. Existing text, citation
ordinals, ranges, and answer documents remain unchanged. Unknown table shape
raises rather than being advertised as a complete empty/flattened table.
"""
from __future__ import annotations
import json


def _selected_row(raw):
    from notebooklm._web.rows.chat import AnswerRow, StreamFrameRow
    from notebooklm._web.rows.chat_stream import _extract_chunk_with_parseable
    final = best_marked = best_unmarked = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith('['):
            continue
        chunk = _extract_chunk_with_parseable(line)
        if not chunk.text:
            continue
        candidate = (chunk, line)
        if chunk.is_answer:
            if chunk.is_final_response:
                final = candidate
            if best_marked is None or len(chunk.text) > len(best_marked[0].text):
                best_marked = candidate
        elif best_unmarked is None or len(chunk.text) > len(best_unmarked[0].text):
            best_unmarked = candidate
    selected = final or best_marked or best_unmarked
    if selected is None:
        raise ValueError('TENG_CITATION_SELECTED_CHUNK_MISSING')
    chunk, line = selected
    for item in json.loads(line):
        if not isinstance(item, list) or len(item) < 3:
            continue
        frame = StreamFrameRow(item)
        if frame.tag != 'wrb.fr' or not isinstance(frame.inner_json, str):
            continue
        try:
            inner = json.loads(frame.inner_json)
        except ValueError:
            continue
        if not isinstance(inner, list) or not inner or not isinstance(inner[0], list):
            continue
        row = AnswerRow(inner[0])
        # Mirrors SDK's first text-bearing envelope, including an empty string.
        if row.text is not None:
            if row.text != chunk.text:
                raise ValueError('TENG_CITATION_SELECTED_ENVELOPE_MISMATCH')
            return row, chunk
    raise ValueError('TENG_CITATION_SELECTED_ENVELOPE_MISSING')


def _tables(elements, depth=0, *, bounds=None):
    from notebooklm._web.rows.documents import _clamp, _narrow, build_blocks
    if depth > 20:
        raise ValueError('TENG_CITATION_TABLE_DEPTH')
    tables = []
    for element in elements:
        if not isinstance(element, list) or len(element) <= 4 or element[4] is None:
            continue
        table = element[4]
        if (not isinstance(table, list) or len(table) < 3
                or type(table[0]) is not int or type(table[1]) is not int
                or table[0] < 0 or table[1] < 0 or not isinstance(table[2], list)
                or len(table[2]) != table[0]
                or type(element[0]) is not int or type(element[1]) is not int
                or element[0] < 0 or element[1] < element[0]):
            raise ValueError('TENG_CITATION_TABLE_SHAPE')
        table_bounds = (element[0], element[1])
        if bounds is not None:
            table_bounds = _narrow(bounds, *table_bounds)
            if table_bounds is None:
                continue
        rows, nested = [], []
        for row in table[2]:
            if (not isinstance(row, list) or len(row) < 3
                    or not isinstance(row[2], list) or len(row[2]) != table[1]
                    or type(row[0]) is not int or type(row[1]) is not int
                    or row[0] < 0 or row[1] < row[0]):
                raise ValueError('TENG_CITATION_TABLE_ROW_SHAPE')
            row_bounds = _narrow(table_bounds, row[0], row[1])
            if row_bounds is None:
                continue
            cells = []
            for cell in row[2]:
                if (not isinstance(cell, list) or len(cell) < 3
                        or type(cell[0]) is not int or type(cell[1]) is not int
                        or cell[0] < 0 or cell[1] < cell[0]
                        or not isinstance(cell[2], list)):
                    raise ValueError('TENG_CITATION_TABLE_CELL_SHAPE')
                # Match the pinned SDK's table -> row -> cell containment.
                # Empty intersections keep their column, without decoding or
                # recursing into text outside the enclosing table or cell.
                cell_bounds = _clamp(row_bounds, cell[0], cell[1])
                if cell_bounds[0] == cell_bounds[1]:
                    cells.append('')
                    continue
                blocks = build_blocks(cell[2], bounds=cell_bounds)
                cells.append(''.join(block.text for block in blocks))
                nested.extend(_tables(cell[2], depth + 1, bounds=cell_bounds))
            rows.append(cells)
        tables.append({'num_columns': table[1], 'rows': rows})
        tables.extend(nested)
    return tables


def retain_teng_citation_tables(value, raw):
    """Add source-fragment structure without altering the SDK's existing fields."""
    from dataclasses import asdict
    from notebooklm._web.rows.chat import CitationRow
    from notebooklm._web.rows.chat_stream import parse_single_citation
    row, chunk = _selected_row(raw)
    if chunk.text != value['answer']:
        raise ValueError('TENG_CITATION_ANSWER_SELECTION_MISMATCH')
    by_number = {}
    for ordinal, wire_cite in enumerate(row.citations, 1):
        try:
            parsed = parse_single_citation(wire_cite)
        except (IndexError, TypeError, AttributeError):
            # Match the pinned SDK's malformed-row policy; never renumber a
            # surviving citation after a skipped raw ordinal.
            continue
        if parsed is not None:
            by_number[ordinal] = (parsed, CitationRow(wire_cite).detail)
    for reference in value['references']:
        match = by_number.get(reference['citation_number'])
        if match is None:
            raise ValueError('TENG_CITATION_RAW_ORDINAL_MISSING')
        parsed, detail = match
        # Match every source-side field before enriching the selected reference.
        for key, field in asdict(parsed).items():
            if key in {'citation_number', 'answer_anchor_start', 'answer_anchor_end'}:
                continue
            if reference.get(key) != field:
                raise ValueError('TENG_CITATION_RAW_REFERENCE_MISMATCH:' + key)
        elements = detail.fragment_elements
        tables = _tables(elements)
        if tables:
            # Raw fragment preserves table/cell coordinates, styles and nested
            # structure that the compact common table schema cannot represent.
            reference['cited_fragment_raw'] = elements
            reference['cited_tables'] = tables
            if len(tables) == 1:
                reference['cited_table'] = tables[0]
    return value

