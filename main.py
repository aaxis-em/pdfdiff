#!/usr/bin/env python3
"""
PDF Diff Server - Main Entry Point
CLI and Flask application initialization
"""

import sys
import argparse
from pathlib import Path
import json
from flask import Flask
from flask_cors import CORS

from extractor import PDFExtractor
from diff import DiffEngine


class PDFDiffServer:
    """Main application class for PDF Diff Server"""
    
    def __init__(self, debug=False, port=5000, host='0.0.0.0'):
        """
        Initialize the PDF Diff Server
        
        Args:
            debug (bool): Enable Flask debug mode
            port (int): Server port
            host (str): Server host
        """
        self.debug = debug
        self.port = port
        self.host = host
        self.app = None
        self.diff_engine = DiffEngine()
        self.pdf_extractor = PDFExtractor()
    
    def create_app(self):
        """Create and configure Flask app"""
        self.app = Flask(__name__)
        CORS(self.app)
        
        # Configuration
        self.app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
        self.app.config['JSON_SORT_KEYS'] = False
        
        # Register routes
        self._register_routes()
        
        return self.app
    
    def _register_routes(self):
        """Register all API routes"""
        
        @self.app.route('/api/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            from datetime import datetime
            return {
                'status': 'ok',
                'version': '0.1.0',
                'timestamp': datetime.now().isoformat()
            }, 200
        
        @self.app.route('/api/diff-types', methods=['GET'])
        def get_diff_types():
            """Get available diff types"""
            return {
                'diff_types': [
                    "length",
                    "identical_bytes",
                    "side_by_side_text",
                    "links",
                    "links_json",
                    "html_text_dmp",
                    "html_source_dmp",
                    "html_token",
                    "html_tree",
                    "html_perma_cc",
                    "links_diff",
                    "html_text_diff",
                    "html_source_diff",
                    "html_visual_diff",
                    "html_tree_diff",
                    "html_differ",
                    "visual_bbox_diff"
                ],
                'version': '0.1.0'
            }, 200
        
        @self.app.route('/api/compare/visual', methods=['POST'])
        def compare_visual():
            """Visual PDF comparison endpoint"""
            from flask import request
            from datetime import datetime
            
            try:
                if 'pdf_a' not in request.files or 'pdf_b' not in request.files:
                    return {'error': 'Both pdf_a and pdf_b files are required'}, 400
                
                pdf_a_file = request.files['pdf_a']
                pdf_b_file = request.files['pdf_b']
                
                # Extract PDF structures
                text_a, images_a = self.pdf_extractor.extract(pdf_a_file.read())
                text_b, images_b = self.pdf_extractor.extract(pdf_b_file.read())
                
                # Run diff
                text_diff = self.diff_engine.text_diff(text_a, text_b)
                
                # Build visual diff response
                visual_diff = self.diff_engine.build_visual_diff(
                    text_a, text_b, text_diff
                )
                
                return {
                    'status': 'success',
                    'version': '0.1.0',
                    'visual_diff': visual_diff,
                    'timestamp': datetime.now().isoformat()
                }, 200
            
            except Exception as e:
                return {'error': str(e), 'status': 'error'}, 500
        
        @self.app.route('/api/compare', methods=['POST'])
        def compare_standard():
            """Standard PDF comparison endpoint"""
            from flask import request
            from datetime import datetime
            
            try:
                if 'pdf_a' not in request.files or 'pdf_b' not in request.files:
                    return {'error': 'Both pdf_a and pdf_b files are required'}, 400
                
                pdf_a_file = request.files['pdf_a']
                pdf_b_file = request.files['pdf_b']
                
                # Extract PDF structures
                text_a, images_a = self.pdf_extractor.extract(pdf_a_file.read())
                text_b, images_b = self.pdf_extractor.extract(pdf_b_file.read())
                
                # Run diff
                text_diff = self.diff_engine.text_diff(text_a, text_b)
                layout_changes = self.diff_engine.compare_layout(text_a, text_b)
                image_changes = self.diff_engine.compare_images(images_a, images_b)
                
                # Build response
                diff_result = {
                    'text_diff': [],
                    'layout_changes': layout_changes,
                    'image_changes': image_changes,
                    'statistics': {
                        'total_text_blocks_old': len(text_a),
                        'total_text_blocks_new': len(text_b),
                        'total_images_old': len(images_a),
                        'total_images_new': len(images_b),
                        'text_additions': sum(1 for d in text_diff if d['type'] == 'insert'),
                        'text_removals': sum(1 for d in text_diff if d['type'] == 'remove'),
                        'text_unchanged': sum(1 for d in text_diff if d['type'] == 'keep'),
                    }
                }
                
                # Format diff output
                for d in text_diff:
                    if d['type'] == 'keep':
                        diff_result['text_diff'].append({
                            'type': 'keep',
                            'text': d['text']
                        })
                    elif d['type'] == 'insert':
                        diff_result['text_diff'].append({
                            'type': 'insert',
                            'text': d['text'],
                            'color': '#00aa00',
                            'label': 'Added'
                        })
                    elif d['type'] == 'remove':
                        diff_result['text_diff'].append({
                            'type': 'remove',
                            'text': d['text'],
                            'color': '#ff0000',
                            'label': 'Removed'
                        })
                
                return {
                    'status': 'success',
                    'version': '0.1.0',
                    'comparison': diff_result,
                    'timestamp': datetime.now().isoformat()
                }, 200
            
            except Exception as e:
                return {'error': str(e), 'status': 'error'}, 500
        
        @self.app.errorhandler(404)
        def not_found(error):
            return {'error': 'Endpoint not found'}, 404
        
        @self.app.errorhandler(500)
        def server_error(error):
            return {'error': 'Internal server error'}, 500
    
    def run(self):
        """Start the Flask server"""
        if self.app is None:
            self.create_app()
        
        print(f"PDF Diff Server starting on http://{self.host}:{self.port}")
        print("\nAPI Documentation:")
        print(f"  GET  /api/health                 - Health check")
        print(f"  GET  /api/diff-types             - Available diff types")
        print(f"  POST /api/compare/visual         - Visual comparison")
        print(f"  POST /api/compare                - Standard comparison")
        print("\nPress Ctrl+C to stop the server\n")
        
        self.app.run(debug=self.debug, port=self.port, host=self.host)


def cli_compare(pdf_a_path, pdf_b_path, output_type='text'):
    """
    CLI function to compare two PDFs
    
    Args:
        pdf_a_path (str): Path to first PDF
        pdf_b_path (str): Path to second PDF
        output_type (str): Output format ('text', 'json', 'html')
    """
    try:
        # Read PDFs
        with open(pdf_a_path, 'rb') as f:
            pdf_a_data = f.read()
        with open(pdf_b_path, 'rb') as f:
            pdf_b_data = f.read()
        
        # Extract
        extractor = PDFExtractor()
        text_a, images_a = extractor.extract(pdf_a_data)
        text_b, images_b = extractor.extract(pdf_b_data)
        
        # Compare
        diff_engine = DiffEngine()
        text_diff = diff_engine.text_diff(text_a, text_b)
        
        # Output
        if output_type == 'text':
            print("\nTEXT DIFF:")
            for item in text_diff:
                if item['type'] == 'keep':
                    print(f"  {item['text']}")
                elif item['type'] == 'insert':
                    print(f"+ {item['text']}")
                elif item['type'] == 'remove':
                    print(f"- {item['text']}")
        
        elif output_type == 'json':
            result = {
                'status': 'success',
                'files': {
                    'file_a': pdf_a_path,
                    'file_b': pdf_b_path
                },
                'diff': text_diff,
                'statistics': {
                    'added': sum(1 for d in text_diff if d['type'] == 'insert'),
                    'removed': sum(1 for d in text_diff if d['type'] == 'remove'),
                    'unchanged': sum(1 for d in text_diff if d['type'] == 'keep'),
                }
            }
            print(json.dumps(result, indent=2))
        
        print(f"\n✅ Comparison complete")
        
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='PDF Diff Server - Compare PDF documents visually',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start web server
  python main.py server
  
  # Compare two PDFs from CLI
  python main.py compare old.pdf new.pdf
  
  # Compare and output JSON
  python main.py compare old.pdf new.pdf --format json
  
  # Start server on custom port
  python main.py server --port 8000
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start the web server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Server host')
    server_parser.add_argument('--port', type=int, default=5000, help='Server port')
    server_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two PDFs')
    compare_parser.add_argument('pdf_a', help='First PDF file')
    compare_parser.add_argument('pdf_b', help='Second PDF file')
    compare_parser.add_argument(
        '--format', 
        choices=['text', 'json', 'html'],
        default='text',
        help='Output format'
    )
    
    args = parser.parse_args()
    
    if args.command == 'server':
        server = PDFDiffServer(
            debug=args.debug,
            port=args.port,
            host=args.host
        )
        server.create_app()
        server.run()
    
    elif args.command == 'compare':
        cli_compare(args.pdf_a, args.pdf_b, args.format)
    
    else:
        # Default to server
        server = PDFDiffServer()
        server.create_app()
        server.run()


if __name__ == '__main__':
    main()
