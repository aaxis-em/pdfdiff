#!/usr/bin/env python3
"""
Diff Module
Implements Myers diff algorithm and PDF comparison logic
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from .extractor import TextBlock, ImageBlock


@dataclass
class DiffItem:
    """Represents a single diff item"""
    type: str  # 'keep', 'insert', 'remove'
    text: str
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'type': self.type,
            'text': self.text
        }


@dataclass
class Frontier:
    """Represents a frontier in the Myers diff algorithm"""
    x: int
    history: List[DiffItem]


class Myers:
    """
    Myers Diff Algorithm Implementation
    
    Based on:
    http://www.xmailserver.org/diff2.pdf
    
    This is an optimal diff algorithm that finds the shortest sequence
    of edits to transform one sequence into another.
    
    Complexity: O((N+M)D) where N, M are sequence lengths and D is edit distance
    """
    
    @staticmethod
    def one(idx: int) -> int:
        """
        Convert 1-indexed position to 0-indexed
        The algorithm uses 1-based indexing; Python uses 0-based
        
        Args:
            idx (int): 1-based index
            
        Returns:
            int: 0-based index
        """
        return idx - 1
    
    @staticmethod
    def diff(a_lines: List[str], b_lines: List[str]) -> List[DiffItem]:
        """
        Compute the shortest edit script between two sequences
        
        Args:
            a_lines (List[str]): First sequence (old version)
            b_lines (List[str]): Second sequence (new version)
            
        Returns:
            List[DiffItem]: List of diff items (keep, insert, remove)
        """
        # Initialize frontier with starting point
        frontier = {1: Frontier(0, [])}
        
        a_max = len(a_lines)
        b_max = len(b_lines)
        
        # Main loop: explore edit graph
        for d in range(0, a_max + b_max + 1):
            # Explore all diagonals at distance d
            for k in range(-d, d + 1, 2):
                # Determine search direction:
                # - If at left edge (k == -d), must go down
                # - If at top edge (k == d), cannot go down (must go right)
                # - Otherwise, choose direction that has made most progress
                go_down = (
                    k == -d or 
                    (k != d and frontier[k - 1].x < frontier[k + 1].x)
                )
                
                # Determine starting point
                if go_down:
                    # Coming from k+1 (moving down)
                    old_x, history = frontier[k + 1].x, frontier[k + 1].history
                    x = old_x
                else:
                    # Coming from k-1 (moving right)
                    old_x, history = frontier[k - 1].x, frontier[k - 1].history
                    x = old_x + 1
                
                # Copy history to avoid modifying other paths
                history = history[:]
                y = x - k
                
                # Add initial move to history
                if 1 <= y <= b_max and go_down:
                    history.append(DiffItem('insert', b_lines[Myers.one(y)]))
                elif 1 <= x <= a_max:
                    history.append(DiffItem('remove', a_lines[Myers.one(x)]))
                
                # Extend with diagonal moves (common lines)
                # These are "free" moves in the edit graph
                while (x < a_max and y < b_max and 
                       a_lines[Myers.one(x + 1)] == b_lines[Myers.one(y + 1)]):
                    x += 1
                    y += 1
                    history.append(DiffItem('keep', a_lines[Myers.one(x)]))
                
                # Check if we've reached the end
                if x >= a_max and y >= b_max:
                    return history
                
                # Store frontier for this diagonal
                frontier[k] = Frontier(x, history)
        
        # Should never reach here
        raise Exception('Could not find edit script')


class DiffEngine:
    """
    Main diff engine for comparing PDFs
    Combines Myers algorithm with PDF-specific comparison
    """
    
    def __init__(self):
        """Initialize the diff engine"""
        self.myers = Myers()
    
    def text_diff(self, text_blocks_a: List[TextBlock], 
                  text_blocks_b: List[TextBlock]) -> List[Dict[str, Any]]:
        """
        Compute text diff using Myers algorithm
        
        Args:
            text_blocks_a (List[TextBlock]): Text blocks from first PDF
            text_blocks_b (List[TextBlock]): Text blocks from second PDF
            
        Returns:
            List[Dict]: List of diff items with type and text
        """
        # Extract text lines
        lines_a = [block.text for block in text_blocks_a]
        lines_b = [block.text for block in text_blocks_b]
        
        # Run Myers diff
        diff_items = self.myers.diff(lines_a, lines_b)
        
        # Convert to dictionary format
        return [item.to_dict() for item in diff_items]
    
    def compare_layout(self, text_blocks_a: List[TextBlock],
                      text_blocks_b: List[TextBlock]) -> List[Dict[str, Any]]:
        """
        Detect layout and style changes (position, font)
        
        Args:
            text_blocks_a (List[TextBlock]): Text blocks from first PDF
            text_blocks_b (List[TextBlock]): Text blocks from second PDF
            
        Returns:
            List[Dict]: List of layout/style changes
        """
        changes = []
        
        # Create text-to-block mappings
        map_a = {block.text: block for block in text_blocks_a}
        map_b = {block.text: block for block in text_blocks_b}
        
        # Check matching blocks for changes
        for text in map_a:
            if text in map_b:
                block_a = map_a[text]
                block_b = map_b[text]
                
                # Check position change
                if block_a.bbox != block_b.bbox:
                    changes.append({
                        'type': 'layout_change',
                        'text': text,
                        'old_bbox': list(block_a.bbox),
                        'new_bbox': list(block_b.bbox),
                        'old_page': block_a.page_num,
                        'new_page': block_b.page_num
                    })
                
                # Check font change
                if block_a.font != block_b.font:
                    changes.append({
                        'type': 'style_change',
                        'text': text,
                        'old_font': block_a.font,
                        'new_font': block_b.font
                    })
        
        return changes
    
    def compare_images(self, image_blocks_a: List[ImageBlock],
                      image_blocks_b: List[ImageBlock]) -> List[Dict[str, Any]]:
        """
        Detect image changes using hash comparison
        
        Args:
            image_blocks_a (List[ImageBlock]): Images from first PDF
            image_blocks_b (List[ImageBlock]): Images from second PDF
            
        Returns:
            List[Dict]: List of image changes
        """
        changes = []
        
        # Create hash mappings
        hashes_a = {img.hash: img for img in image_blocks_a}
        hashes_b = {img.hash: img for img in image_blocks_b}
        
        # Find removed images
        for hash_val in set(hashes_a.keys()) - set(hashes_b.keys()):
            img = hashes_a[hash_val]
            changes.append({
                'type': 'image_removed',
                'hash': hash_val,
                'bbox': list(img.bbox) if img.bbox else None,
                'page': img.page_num
            })
        
        # Find added images
        for hash_val in set(hashes_b.keys()) - set(hashes_a.keys()):
            img = hashes_b[hash_val]
            changes.append({
                'type': 'image_added',
                'hash': hash_val,
                'bbox': list(img.bbox) if img.bbox else None,
                'page': img.page_num
            })
        
        return changes
    
    def build_visual_diff(self, text_blocks_a: List[TextBlock],
                         text_blocks_b: List[TextBlock],
                         diff_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build visual diff structure with bounding boxes
        
        Args:
            text_blocks_a (List[TextBlock]): Text blocks from first PDF
            text_blocks_b (List[TextBlock]): Text blocks from second PDF
            diff_items (List[Dict]): Raw diff items from Myers algorithm
            
        Returns:
            Dict: Structured visual diff with bounding box information
        """
        visual_diff = {
            'pages': {},
            'summary': {
                'added': [],
                'removed': [],
                'changed': []
            }
        }
        
        # Create mappings
        used_a = set()
        used_b = set()
        
        # Process diff items
        for diff_item in diff_items:
            if diff_item['type'] == 'keep':
                # Find matching blocks
                for i, block in enumerate(text_blocks_a):
                    if block.text == diff_item['text'] and i not in used_a:
                        used_a.add(i)
                        break
                for i, block in enumerate(text_blocks_b):
                    if block.text == diff_item['text'] and i not in used_b:
                        used_b.add(i)
                        break
            
            elif diff_item['type'] == 'insert':
                # Find added block
                for i, block in enumerate(text_blocks_b):
                    if block.text == diff_item['text'] and i not in used_b:
                        used_b.add(i)
                        page_key = f"page_{block.page_num}"
                        
                        if page_key not in visual_diff['pages']:
                            visual_diff['pages'][page_key] = {
                                'added': [],
                                'removed': [],
                                'changed': []
                            }
                        
                        added_item = {
                            'text': block.text,
                            'bbox': list(block.bbox),
                            'font': block.font,
                            'color': '#00aa00'
                        }
                        
                        visual_diff['pages'][page_key]['added'].append(added_item)
                        visual_diff['summary']['added'].append({
                            'text': block.text,
                            'bbox': list(block.bbox),
                            'page': block.page_num
                        })
                        break
            
            elif diff_item['type'] == 'remove':
                # Find removed block
                for i, block in enumerate(text_blocks_a):
                    if block.text == diff_item['text'] and i not in used_a:
                        used_a.add(i)
                        page_key = f"page_{block.page_num}"
                        
                        if page_key not in visual_diff['pages']:
                            visual_diff['pages'][page_key] = {
                                'added': [],
                                'removed': [],
                                'changed': []
                            }
                        
                        removed_item = {
                            'text': block.text,
                            'bbox': list(block.bbox),
                            'font': block.font,
                            'color': '#ff0000'
                        }
                        
                        visual_diff['pages'][page_key]['removed'].append(removed_item)
                        visual_diff['summary']['removed'].append({
                            'text': block.text,
                            'bbox': list(block.bbox),
                            'page': block.page_num
                        })
                        break
        
        return visual_diff
    
    def get_diff_stats(self, diff_items: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate statistics from diff results
        
        Args:
            diff_items (List[Dict]): Raw diff items
            
        Returns:
            Dict: Statistics (additions, removals, unchanged)
        """
        stats = {
            'additions': 0,
            'removals': 0,
            'unchanged': 0,
            'total': len(diff_items)
        }
        
        for item in diff_items:
            if item['type'] == 'insert':
                stats['additions'] += 1
            elif item['type'] == 'remove':
                stats['removals'] += 1
            elif item['type'] == 'keep':
                stats['unchanged'] += 1
        
        return stats


class DiffFormatter:
    """Formats diff output in various formats"""
    
    @staticmethod
    def to_unified(diff_items: List[Dict[str, Any]]) -> str:
        """
        Format diff as unified diff format (like git diff)
        
        Args:
            diff_items (List[Dict]): Diff items
            
        Returns:
            str: Unified diff format
        """
        lines = []
        
        for item in diff_items:
            if item['type'] == 'keep':
                lines.append(f" {item['text']}")
            elif item['type'] == 'insert':
                lines.append(f"+{item['text']}")
            elif item['type'] == 'remove':
                lines.append(f"-{item['text']}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def to_side_by_side(text_blocks_a: List[TextBlock],
                        text_blocks_b: List[TextBlock],
                        diff_items: List[Dict[str, Any]],
                        width: int = 80) -> str:
        """
        Format diff as side-by-side comparison
        
        Args:
            text_blocks_a (List[TextBlock]): First PDF blocks
            text_blocks_b (List[TextBlock]): Second PDF blocks
            diff_items (List[Dict]): Diff items
            width (int): Column width
            
        Returns:
            str: Side-by-side formatted diff
        """
        lines = []
        lines.append(f"{'OLD':<{width}} | {'NEW':<{width}}")
        lines.append("-" * (width * 2 + 3))
        
        left = []
        right = []
        
        for item in diff_items:
            if item['type'] == 'keep':
                text = item['text'][:width-2]
                left.append(f" {text:<{width-1}}")
                right.append(f" {text:<{width-1}}")
            elif item['type'] == 'remove':
                text = item['text'][:width-2]
                left.append(f"-{text:<{width-1}}")
                right.append(f" {'':.<{width-1}}")
            elif item['type'] == 'insert':
                text = item['text'][:width-2]
                left.append(f" {'':.<{width-1}}")
                right.append(f"+{text:<{width-1}}")
        
        for l, r in zip(left, right):
            lines.append(f"{l} | {r}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def to_html(diff_items: List[Dict[str, Any]]) -> str:
        """
        Format diff as HTML
        
        Args:
            diff_items (List[Dict]): Diff items
            
        Returns:
            str: HTML formatted diff
        """
        html = ['<pre style="background:#f5f5f5;padding:10px;">']
        
        for item in diff_items:
            text = item['text'].replace('<', '&lt;').replace('>', '&gt;')
            
            if item['type'] == 'keep':
                html.append(f"<span>{text}</span>")
            elif item['type'] == 'insert':
                html.append(f"<span style='color:green;background:#e8f5e9;'>+{text}</span>")
            elif item['type'] == 'remove':
                html.append(f"<span style='color:red;background:#ffebee;'>-{text}</span>")
        
        html.append('</pre>')
        return '\n'.join(html)


# Example usage
if __name__ == '__main__':
    from extractor import PDFExtractor
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python diff.py <pdf_a> <pdf_b>")
        sys.exit(1)
    
    # Extract PDFs
    extractor = PDFExtractor()
    
    with open(sys.argv[1], 'rb') as f:
        text_a, images_a = extractor.extract(f.read())
    
    with open(sys.argv[2], 'rb') as f:
        text_b, images_b = extractor.extract(f.read())
    
    # Diff
    engine = DiffEngine()
    diff_items = engine.text_diff(text_a, text_b)
    
    # Display
    print("DIFF OUTPUT:")
    print(DiffFormatter.to_unified(diff_items))
    
    # Stats
    stats = engine.get_diff_stats(diff_items)
    print(f"\nStatistics:")
    print(f"  Additions:  {stats['additions']}")
    print(f"  Removals:   {stats['removals']}")
    print(f"  Unchanged:  {stats['unchanged']}")
    print(f"  Total:      {stats['total']}")
