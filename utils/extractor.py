#!/usr/bin/env python3
"""
PDF Extraction Module
Handles PDF parsing, text extraction, and image detection
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


@dataclass
class ImageBlock:
    """Represents an image block in a PDF"""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    hash: str
    page_num: int
    block_id: str
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'bbox': list(self.bbox) if self.bbox else None,
            'hash': self.hash,
            'page': self.page_num,
            'id': self.block_id
        }
    
    def __repr__(self):
        return f"ImageBlock(hash={self.hash[:8]}..., page={self.page_num})"


class PDFExtractor:
    """
    Extracts text and image information from PDF files
    Uses PyMuPDF for efficient PDF processing
    """
    
    def __init__(self):
        """Initialize the PDF extractor"""
        self.block_counter = 0
    
    @staticmethod
    def _hash_image(data: bytes) -> str:
        """
        Generate SHA256 hash for image data
        
        Args:
            data (bytes): Image data
            
        Returns:
            str: SHA256 hash
        """
        return hashlib.sha256(data).hexdigest()
    
    def extract(self, pdf_data: bytes) -> Tuple[List[TextBlock], List[ImageBlock]]:
        """
        Extract text blocks and image blocks from PDF
        
        Args:
            pdf_data (bytes): PDF file content
            
        Returns:
            Tuple[List[TextBlock], List[ImageBlock]]: Extracted blocks
        """
        text_blocks = []
        image_blocks = []
        self.block_counter = 0
        
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_data, filetype='pdf')
            
            # Extract from each page
            for page_num, page in enumerate(doc):
                self._extract_text_blocks(page, page_num, text_blocks)
                self._extract_image_blocks(doc, page, page_num, image_blocks)
            
            doc.close()
            
            return text_blocks, image_blocks
        
        except Exception as e:
            raise Exception(f"Error extracting PDF: {str(e)}")
    
    def _extract_text_blocks(self, page, page_num: int, text_blocks: List[TextBlock]):
        """
        Extract text blocks from a PDF page
        
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
        Process a text block and extract individual text spans
        
        Args:
            block: PyMuPDF block dictionary
            page_num (int): Page number
            text_blocks (List[TextBlock]): List to append blocks to
        """
        try:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    
                    # Skip empty text
                    if not text:
                        continue
                    
                    # Extract span information
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    font = span.get("font", "Unknown")
                    
                    # Create text block
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
    
    def _extract_image_blocks(self, doc, page, page_num: int, image_blocks: List[ImageBlock]):
        """
        Extract image blocks from a PDF page
        
        Args:
            doc: PyMuPDF document object
            page: PyMuPDF page object
            page_num (int): Page number
            image_blocks (List[ImageBlock]): List to append blocks to
        """
        try:
            for img in page.get_images(full=True):
                try:
                    xref = img[0]
                    base = doc.extract_image(xref)
                    img_bytes = base["image"]
                    
                    # Get image bounding box
                    rect = page.get_image_bbox(img)
                    
                    # Create image block
                    image_block = ImageBlock(
                        bbox=rect,
                        hash=self._hash_image(img_bytes),
                        page_num=page_num,
                        block_id=f"image_{self.block_counter}"
                    )
                    
                    image_blocks.append(image_block)
                    self.block_counter += 1
                
                except Exception as e:
                    print(f"Warning: Error extracting image from page {page_num}: {e}")
        
        except Exception as e:
            print(f"Warning: Error scanning images on page {page_num}: {e}")
    
    def get_text_content(self, text_blocks: List[TextBlock]) -> List[str]:
        """
        Extract text content from text blocks for diff
        
        Args:
            text_blocks (List[TextBlock]): List of text blocks
            
        Returns:
            List[str]: List of text lines
        """
        return [block.text for block in text_blocks]
    
    def get_block_map(self, text_blocks: List[TextBlock]) -> dict:
        """
        Create a mapping of text content to blocks
        
        Args:
            text_blocks (List[TextBlock]): List of text blocks
            
        Returns:
            dict: Mapping of text to block information
        """
        return {block.text: block for block in text_blocks}
    
    def get_statistics(self, text_blocks: List[TextBlock], image_blocks: List[ImageBlock]) -> dict:
        """
        Get statistics about extracted content
        
        Args:
            text_blocks (List[TextBlock]): List of text blocks
            image_blocks (List[ImageBlock]): List of image blocks
            
        Returns:
            dict: Statistics
        """
        # Group by page
        text_by_page = {}
        images_by_page = {}
        
        for block in text_blocks:
            page = block.page_num
            if page not in text_by_page:
                text_by_page[page] = []
            text_by_page[page].append(block)
        
        for block in image_blocks:
            page = block.page_num
            if page not in images_by_page:
                images_by_page[page] = []
            images_by_page[page].append(block)
        
        return {
            'total_text_blocks': len(text_blocks),
            'total_image_blocks': len(image_blocks),
            'total_pages': max(
                max(text_by_page.keys()) if text_by_page else 0,
                max(images_by_page.keys()) if images_by_page else 0
            ) + 1,
            'text_by_page': {
                page: len(blocks)
                for page, blocks in text_by_page.items()
            },
            'images_by_page': {
                page: len(blocks)
                for page, blocks in images_by_page.items()
            }
        }


class PDFMetadata:
    """Helper class to extract PDF metadata"""
    
    @staticmethod
    def get_pdf_info(pdf_data: bytes) -> dict:
        """
        Extract metadata from PDF
        
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
        Get SHA256 hash of PDF file
        
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
    
    # Extract and display
    pdf_path = sys.argv[1]
    
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
    
    extractor = PDFExtractor()
    text_blocks, image_blocks = extractor.extract(pdf_data)
    
    print(f"Extracted {len(text_blocks)} text blocks and {len(image_blocks)} images\n")
    
    print("Text Blocks:")
    for block in text_blocks[:5]:  # Show first 5
        print(f"  {block}")
    
    if len(text_blocks) > 5:
        print(f"  ... and {len(text_blocks) - 5} more")
    
    print(f"\nImage Blocks:")
    for block in image_blocks[:5]:  # Show first 5
        print(f"  {block}")
    
    if len(image_blocks) > 5:
        print(f"  ... and {len(image_blocks) - 5} more")
    
    # Get metadata
    metadata = PDFMetadata.get_pdf_info(pdf_data)
    print(f"\nMetadata:")
    for key, value in metadata.items():
        if key != 'error':
            print(f"  {key}: {value}")
