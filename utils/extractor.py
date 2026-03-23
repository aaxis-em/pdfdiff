#!/usr/bin/env python3
"""
PDF Extraction Module
Handles PDF parsing and text extraction
"""

import fitz  # PyMuPDF
import hashlib
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class TextBlock:
    """Represents a text block in a PDF"""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    font: str
    page_num: int
    block_id: str

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'text': self.text,
            'bbox': list(self.bbox),
            'font': self.font,
            'page': self.page_num,
            'id': self.block_id
        }

    def __repr__(self):
        return f"TextBlock(text='{self.text[:30]}...', page={self.page_num}, bbox={self.bbox})"


class PDFExtractor:
    """
    Extracts text from PDF files.
    Uses PyMuPDF for efficient PDF processing.
    """

    def __init__(self):
        """Initialize the PDF extractor"""
        self.block_counter = 0

    def extract(self, pdf_data: bytes) -> List[TextBlock]:
        """
        Extract text blocks from PDF.

        Args:
            pdf_data (bytes): PDF file content

        Returns:
            List[TextBlock]: Extracted text blocks
        """
        text_blocks = []
        self.block_counter = 0

        try:
            doc = fitz.open(stream=pdf_data, filetype='pdf')

            for page_num, page in enumerate(doc):
                self._extract_text_blocks(page, page_num, text_blocks)

            doc.close()
            return text_blocks

        except Exception as e:
            raise Exception(f"Error extracting PDF: {str(e)}")

    def _extract_text_blocks(self, page, page_num: int, text_blocks: List[TextBlock]):
        """
        Extract text blocks from a PDF page.

        Args:
            page: PyMuPDF page object
            page_num (int): Page number
            text_blocks (List[TextBlock]): List to append blocks to
        """
        try:
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] == 0:  # Text block
                    self._process_text_block(block, page_num, text_blocks)

        except Exception as e:
            print(f"Warning: Error extracting text from page {page_num}: {e}")

    def _process_text_block(self, block, page_num: int, text_blocks: List[TextBlock]):
        """
        Process a text block and extract individual text spans.

        Args:
            block: PyMuPDF block dictionary
            page_num (int): Page number
            text_blocks (List[TextBlock]): List to append blocks to
        """
        try:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()

                    if not text:
                        continue

                    bbox = span.get("bbox", (0, 0, 0, 0))
                    font = span.get("font", "Unknown")

                    text_block = TextBlock(
                        text=text,
                        bbox=bbox,
                        font=font,
                        page_num=page_num,
                        block_id=f"text_{self.block_counter}"
                    )

                    text_blocks.append(text_block)
                    self.block_counter += 1

        except Exception as e:
            print(f"Warning: Error processing text block: {e}")

    def get_text_content(self, text_blocks: List[TextBlock]) -> List[str]:
        """
        Extract text content from text blocks for diff.

        Args:
            text_blocks (List[TextBlock]): List of text blocks

        Returns:
            List[str]: List of text lines
        """
        return [block.text for block in text_blocks]

    def get_block_map(self, text_blocks: List[TextBlock]) -> dict:
        """
        Create a mapping of text content to blocks.

        Args:
            text_blocks (List[TextBlock]): List of text blocks

        Returns:
            dict: Mapping of text to block information
        """
        return {block.text: block for block in text_blocks}

    def get_statistics(self, text_blocks: List[TextBlock]) -> dict:
        """
        Get statistics about extracted text content.

        Args:
            text_blocks (List[TextBlock]): List of text blocks

        Returns:
            dict: Statistics
        """
        text_by_page = {}

        for block in text_blocks:
            page = block.page_num
            if page not in text_by_page:
                text_by_page[page] = []
            text_by_page[page].append(block)

        return {
            'total_text_blocks': len(text_blocks),
            'total_pages': (max(text_by_page.keys()) + 1) if text_by_page else 0,
            'text_by_page': {
                page: len(blocks)
                for page, blocks in text_by_page.items()
            }
        }


class PDFMetadata:
    """Helper class to extract PDF metadata"""

    @staticmethod
    def get_pdf_info(pdf_data: bytes) -> dict:
        """
        Extract metadata from PDF.

        Args:
            pdf_data (bytes): PDF file content

        Returns:
            dict: PDF metadata
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype='pdf')

            metadata = {
                'pages': doc.page_count,
                'title': doc.metadata.get('title', 'Unknown'),
                'author': doc.metadata.get('author', 'Unknown'),
                'subject': doc.metadata.get('subject', 'Unknown'),
                'creator': doc.metadata.get('creator', 'Unknown'),
                'producer': doc.metadata.get('producer', 'Unknown'),
                'creation_date': str(doc.metadata.get('creationDate', 'Unknown')),
                'modification_date': str(doc.metadata.get('modDate', 'Unknown')),
                'is_encrypted': doc.is_encrypted,
                'is_pdf': doc.is_pdf
            }

            doc.close()
            return metadata

        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def get_file_hash(pdf_data: bytes) -> str:
        """
        Get SHA256 hash of PDF file.

        Args:
            pdf_data (bytes): PDF file content

        Returns:
            str: SHA256 hash
        """
        return hashlib.sha256(pdf_data).hexdigest()


# Example usage
if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print("Usage: python extractor.py <pdf_file>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()

    extractor = PDFExtractor()
    text_blocks = extractor.extract(pdf_data)

    print(f"Extracted {len(text_blocks)} text blocks\n")

    print("Text Blocks:")
    for block in text_blocks[:5]:
        print(f"  {block}")

    if len(text_blocks) > 5:
        print(f"  ... and {len(text_blocks) - 5} more")

    metadata = PDFMetadata.get_pdf_info(pdf_data)
    print(f"\nMetadata:")
    for key, value in metadata.items():
        if key != 'error':
            print(f"  {key}: {value}")
