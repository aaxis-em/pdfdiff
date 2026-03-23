#!/usr/bin/env python3
"""
Flask PDF Diff Server
POST /diff/pdf — compares two PDFs and returns structured diff results
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback

from utils.extractor import PDFExtractor, PDFMetadata
from utils.diff import DiffEngine

app = Flask(__name__)
CORS(app)

extractor = PDFExtractor()
engine = DiffEngine()


def _extract_from_bytes(data: bytes) -> tuple:
    """Extract text blocks and metadata from raw PDF bytes."""
    text_blocks = extractor.extract(data)
    metadata = PDFMetadata.get_pdf_info(data)
    return text_blocks, metadata


@app.route("/diff/pdf", methods=["POST"])
def diff_pdf():
    """
    Compare two PDFs uploaded as multipart form data.

    Form fields:
        pdf_a  – first PDF file  (original)
        pdf_b  – second PDF file (modified)

    Response JSON:
    {
      "version": "0.1.0",
      "identical_bytes": bool,
      "stats": {
        "additions": int,
        "removals":  int,
        "unchanged": int,
        "total":     int
      },
      "diff": [
        {"type": "keep"|"insert"|"remove", "text": str},
        ...
      ],
      "layout_changes": [
        {"type": "layout_change"|"style_change", "text": str, ...},
        ...
      ],
      "visual_diff": {
        "pages": {
          "page_0": {
            "added":   [{"text": str, "bbox": [...], "font": str}, ...],
            "removed": [{"text": str, "bbox": [...], "font": str}, ...]
          },
          ...
        },
        "summary": {
          "added":   [{"text": str, "bbox": [...], "font": str, "page": int}, ...],
          "removed": [{"text": str, "bbox": [...], "font": str, "page": int}, ...]
        }
      },
      "metadata": {
        "pdf_a": {...},
        "pdf_b": {...}
      }
    }
    """

    # ── Validate ──────────────────────────────────────────────────────────────
    if "pdf_a" not in request.files or "pdf_b" not in request.files:
        return jsonify({"error": "Both pdf_a and pdf_b are required"}), 400

    file_a = request.files["pdf_a"]
    file_b = request.files["pdf_b"]

    if not file_a.filename or not file_b.filename:
        return jsonify({"error": "File names must not be empty"}), 400

    # ── Extract ───────────────────────────────────────────────────────────────
    try:
        bytes_a = file_a.read()
        bytes_b = file_b.read()

        text_a, meta_a = _extract_from_bytes(bytes_a)
        text_b, meta_b = _extract_from_bytes(bytes_b)
    except Exception as exc:
        return jsonify({"error": f"PDF extraction failed: {str(exc)}"}), 422

    # ── Diff ──────────────────────────────────────────────────────────────────
    try:
        diff_items     = engine.text_diff(text_a, text_b)
        stats          = engine.get_diff_stats(diff_items)
        layout_changes = engine.compare_layout(text_a, text_b)
        visual_diff    = engine.build_visual_diff(text_a, text_b, diff_items)

        return jsonify({
            "version":        "0.1.0",
            "identical_bytes": bytes_a == bytes_b,
            "stats":          stats,
            "diff":           diff_items,
            "layout_changes": layout_changes,
            "visual_diff":    visual_diff,
            "metadata":       {"pdf_a": meta_a, "pdf_b": meta_b},
        }), 200

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Diff failed: {str(exc)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "0.1.0"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
