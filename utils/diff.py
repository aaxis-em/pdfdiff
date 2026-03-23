#!/usr/bin/env python3
"""
Diff Module
Implements Myers diff algorithm and PDF text comparison logic
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from .extractor import TextBlock


@dataclass
class DiffItem:
    """Represents a single diff item"""
    type: str  # 'keep', 'insert', 'remove'
    text: str

    def to_dict(self):
        return {'type': self.type, 'text': self.text}


@dataclass
class Frontier:
    """Represents a frontier in the Myers diff algorithm"""
    x: int
    history: List[DiffItem]


class Myers:
    """
    Myers Diff Algorithm Implementation
    http://www.xmailserver.org/diff2.pdf

    Finds the shortest edit script to transform one sequence into another.
    Complexity: O((N+M)D) where N, M are sequence lengths and D is edit distance
    """

    @staticmethod
    def one(idx: int) -> int:
        """Convert 1-based index to 0-based"""
        return idx - 1

    @staticmethod
    def diff(a_lines: List[str], b_lines: List[str]) -> List[DiffItem]:
        """
        Compute the shortest edit script between two sequences.

        Args:
            a_lines: First sequence (old version)
            b_lines: Second sequence (new version)

        Returns:
            List of DiffItems (keep, insert, remove)
        """
        frontier = {1: Frontier(0, [])}
        a_max = len(a_lines)
        b_max = len(b_lines)

        for d in range(0, a_max + b_max + 1):
            for k in range(-d, d + 1, 2):
                go_down = (
                    k == -d or
                    (k != d and frontier[k - 1].x < frontier[k + 1].x)
                )

                if go_down:
                    old_x, history = frontier[k + 1].x, frontier[k + 1].history
                    x = old_x
                else:
                    old_x, history = frontier[k - 1].x, frontier[k - 1].history
                    x = old_x + 1

                history = history[:]
                y = x - k

                if 1 <= y <= b_max and go_down:
                    history.append(DiffItem('insert', b_lines[Myers.one(y)]))
                elif 1 <= x <= a_max:
                    history.append(DiffItem('remove', a_lines[Myers.one(x)]))

                while (x < a_max and y < b_max and
                       a_lines[Myers.one(x + 1)] == b_lines[Myers.one(y + 1)]):
                    x += 1
                    y += 1
                    history.append(DiffItem('keep', a_lines[Myers.one(x)]))

                if x >= a_max and y >= b_max:
                    return history

                frontier[k] = Frontier(x, history)

        raise Exception('Could not find edit script')


class DiffEngine:
    """Compares two PDFs at the text, layout, and style level"""

    def __init__(self):
        self.myers = Myers()

    def text_diff(self, text_blocks_a: List[TextBlock],
                  text_blocks_b: List[TextBlock]) -> List[Dict[str, Any]]:
        """
        Compute text diff using Myers algorithm.

        Returns:
            List of dicts: [{'type': 'keep'|'insert'|'remove', 'text': str}, ...]
        """
        lines_a = [block.text for block in text_blocks_a]
        lines_b = [block.text for block in text_blocks_b]
        return [item.to_dict() for item in self.myers.diff(lines_a, lines_b)]

    def compare_layout(self, text_blocks_a: List[TextBlock],
                       text_blocks_b: List[TextBlock]) -> List[Dict[str, Any]]:
        """
        Detect position and font changes for text that exists in both PDFs.

        Returns:
            List of layout_change / style_change dicts
        """
        changes = []
        map_a = {block.text: block for block in text_blocks_a}
        map_b = {block.text: block for block in text_blocks_b}

        for text in map_a:
            if text in map_b:
                block_a, block_b = map_a[text], map_b[text]

                if block_a.bbox != block_b.bbox:
                    changes.append({
                        'type': 'layout_change',
                        'text': text,
                        'old_bbox': list(block_a.bbox),
                        'new_bbox': list(block_b.bbox),
                        'old_page': block_a.page_num,
                        'new_page': block_b.page_num,
                    })

                if block_a.font != block_b.font:
                    changes.append({
                        'type': 'style_change',
                        'text': text,
                        'old_font': block_a.font,
                        'new_font': block_b.font,
                    })

        return changes

    def build_visual_diff(self, text_blocks_a: List[TextBlock],
                          text_blocks_b: List[TextBlock],
                          diff_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Attach bounding-box info to diff items, grouped by page.

        Returns:
            {
              'pages': { 'page_0': { 'added': [...], 'removed': [...] }, ... },
              'summary': { 'added': [...], 'removed': [...] }
            }
        """
        visual_diff = {'pages': {}, 'summary': {'added': [], 'removed': []}}
        used_a, used_b = set(), set()

        for item in diff_items:
            if item['type'] == 'keep':
                for i, b in enumerate(text_blocks_a):
                    if b.text == item['text'] and i not in used_a:
                        used_a.add(i); break
                for i, b in enumerate(text_blocks_b):
                    if b.text == item['text'] and i not in used_b:
                        used_b.add(i); break

            elif item['type'] == 'insert':
                for i, block in enumerate(text_blocks_b):
                    if block.text == item['text'] and i not in used_b:
                        used_b.add(i)
                        pk = f"page_{block.page_num}"
                        visual_diff['pages'].setdefault(pk, {'added': [], 'removed': []})
                        entry = {'text': block.text, 'bbox': list(block.bbox), 'font': block.font}
                        visual_diff['pages'][pk]['added'].append(entry)
                        visual_diff['summary']['added'].append({**entry, 'page': block.page_num})
                        break

            elif item['type'] == 'remove':
                for i, block in enumerate(text_blocks_a):
                    if block.text == item['text'] and i not in used_a:
                        used_a.add(i)
                        pk = f"page_{block.page_num}"
                        visual_diff['pages'].setdefault(pk, {'added': [], 'removed': []})
                        entry = {'text': block.text, 'bbox': list(block.bbox), 'font': block.font}
                        visual_diff['pages'][pk]['removed'].append(entry)
                        visual_diff['summary']['removed'].append({**entry, 'page': block.page_num})
                        break

        return visual_diff

    def get_diff_stats(self, diff_items: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Count additions, removals, and unchanged lines.

        Returns:
            {'additions': int, 'removals': int, 'unchanged': int, 'total': int}
        """
        stats = {'additions': 0, 'removals': 0, 'unchanged': 0, 'total': len(diff_items)}
        for item in diff_items:
            if item['type'] == 'insert':
                stats['additions'] += 1
            elif item['type'] == 'remove':
                stats['removals'] += 1
            elif item['type'] == 'keep':
                stats['unchanged'] += 1
        return stats


# Example usage
if __name__ == '__main__':
    from extractor import PDFExtractor
    import sys

    if len(sys.argv) != 3:
        print("Usage: python diff.py <pdf_a> <pdf_b>")
        sys.exit(1)

    extractor = PDFExtractor()

    with open(sys.argv[1], 'rb') as f:
        text_a = extractor.extract(f.read())
    with open(sys.argv[2], 'rb') as f:
        text_b = extractor.extract(f.read())

    engine = DiffEngine()
    diff_items = engine.text_diff(text_a, text_b)
    stats = engine.get_diff_stats(diff_items)

    for item in diff_items:
        prefix = ' ' if item['type'] == 'keep' else ('+' if item['type'] == 'insert' else '-')
        print(f"{prefix} {item['text']}")

    print(f"\nAdded: {stats['additions']}  Removed: {stats['removals']}  Unchanged: {stats['unchanged']}")
