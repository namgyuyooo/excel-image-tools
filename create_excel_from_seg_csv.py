#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Create an Excel file from segmentation inference CSV and images.

Inputs:
- IMAGES_BASE: Base directory that contains image files organized by class folders
- CSV_PATH: CSV file with headers: img_path, origin_class, error, pred_seg_results, seg_score

Output:
- Excel file containing rows per image with embedded thumbnails and parsed predictions
"""

import os
import sys
import csv
import glob
import uuid
from typing import Dict, List, Tuple, Optional

from openpyxl import Workbook
from openpyxl.drawing import image as openpyxl_image
from PIL import Image as PILImage
from openpyxl.utils import get_column_letter


def normalize_relative_path(path_from_csv: str) -> str:
    """Normalize a CSV-provided image path to be relative to images base.

    Examples:
    - "20250801_v0.2/1.bondfinger/0001.jpg" -> "1.bondfinger/0001.jpg"
    - "1.bondfinger/0001.jpg" -> unchanged
    - Handles backslashes and redundant separators
    """
    if not path_from_csv:
        return ""
    norm = path_from_csv.replace("\\", "/")
    # If the first segment looks like a dataset date/version, drop it
    if "/" in norm:
        first, rest = norm.split("/", 1)
        # Heuristic: drop a leading segment that contains digits and dots/underscores like a version string
        if any(ch.isdigit() for ch in first):
            return rest
    return norm


def resolve_image_path(images_base: str, csv_img_path: str) -> Optional[str]:
    """Resolve CSV image path to an absolute path under images_base.

    Strategy:
    1) Join images_base with normalized relative path
    2) If not found, search by basename anywhere under images_base
    """
    if not csv_img_path:
        return None

    if os.path.isabs(csv_img_path) and os.path.exists(csv_img_path):
        return csv_img_path

    rel = normalize_relative_path(csv_img_path)
    candidate = os.path.join(images_base, rel)
    if os.path.exists(candidate):
        return candidate

    # Try corresponding *_viz.png next to the expected location
    rel_dir = os.path.dirname(rel)
    rel_base, _ = os.path.splitext(os.path.basename(rel))
    viz_candidate = os.path.join(images_base, rel_dir, f"{rel_base}_viz.png")
    if os.path.exists(viz_candidate):
        return viz_candidate

    # Fallbacks: search by basename and by base name without extension, allowing suffixes like _viz
    basename = os.path.basename(rel)
    base_no_ext, _ = os.path.splitext(basename)
    patterns = [
        os.path.join(images_base, "**", basename),               # exact filename
        os.path.join(images_base, "**", f"{base_no_ext}.*"),     # any extension
        os.path.join(images_base, "**", f"*{base_no_ext}*.*"),   # allow suffix/prefix (e.g., _viz)
    ]
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    return None


def find_viz_image(original_image_path: str) -> Optional[str]:
    """Try to find a corresponding visualization image near the original image.

    Looks for variants like:
    - <name>_viz.png
    - <name>_viz.jpg/jpeg
    - any *<name>*viz*.png in the same directory
    """
    if not original_image_path:
        return None
    directory = os.path.dirname(original_image_path)
    base, _ = os.path.splitext(os.path.basename(original_image_path))

    candidates = [
        os.path.join(directory, f"{base}_viz.png"),
        os.path.join(directory, f"{base}_viz.jpg"),
        os.path.join(directory, f"{base}_viz.jpeg"),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand

    wildcard = glob.glob(os.path.join(directory, f"*{base}*viz*.png"))
    if wildcard:
        return wildcard[0]

    return None


def parse_prediction_fields(pred_seg_results: str, seg_score: str) -> Tuple[str, str, str, str]:
    """Parse semicolon-separated predictions and scores.

    Returns: (top_pred, top_score, all_preds, all_scores)
    """
    preds = [p.strip() for p in (pred_seg_results or "").split(";") if p.strip()]
    scores = [s.strip() for s in (seg_score or "").split(";") if s.strip()]

    top_pred = preds[0] if preds else ""
    top_score = scores[0] if scores else ""
    all_preds = "; ".join(preds)
    all_scores = "; ".join(scores)
    return top_pred, top_score, all_preds, all_scores


def create_excel_from_csv(images_base: str, csv_path: str, output_file: str, limit: Optional[int] = None) -> bool:
    """Create an Excel workbook that mirrors the CSV columns and appends one last image column.

    limit: cap the number of rows processed (None for all)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "inference_results"

    temp_files: List[str] = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames: List[str] = reader.fieldnames or []

        # Headers = CSV headers + last image column
        headers = fieldnames + ["img"]
        for col_index, name in enumerate(headers, start=1):
            ws.cell(row=1, column=col_index, value=name)

        # Make the last column wide for images
        last_col_letter = get_column_letter(len(headers))
        ws.column_dimensions[last_col_letter].width = 30

        current_row = 2
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break

            # Write CSV fields as-is in order
            for col_index, key in enumerate(fieldnames, start=1):
                ws.cell(row=current_row, column=col_index, value=row.get(key, ""))

            # Resolve and insert image at the last column
            csv_img_path = row.get('img_path', '')
            abs_img_path = resolve_image_path(images_base, csv_img_path)

            # Set row height for image visibility
            ws.row_dimensions[current_row].height = 180

            image_col_letter = last_col_letter
            if abs_img_path and os.path.exists(abs_img_path):
                try:
                    temp_img_path = f"temp_img_{uuid.uuid4().hex[:8]}.png"
                    with PILImage.open(abs_img_path) as pil_img:
                        if pil_img.mode != 'RGB':
                            pil_img = pil_img.convert('RGB')
                        pil_img.thumbnail((300, 300), PILImage.Resampling.LANCZOS)
                        pil_img.save(temp_img_path, "PNG")
                    temp_files.append(temp_img_path)

                    img = openpyxl_image.Image(temp_img_path)
                    img.width = 180
                    img.height = 180
                    img.anchor = f'{image_col_letter}{current_row}'
                    ws.add_image(img)
                except Exception as e:
                    ws[f'{image_col_letter}{current_row}'] = f"Error: {e}"
            else:
                ws[f'{image_col_letter}{current_row}'] = "Image not found"

            current_row += 1

    wb.save(output_file)

    for path in temp_files:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

    return True


def main():
    # Configure your paths here (can be turned into CLI args if needed)
    IMAGES_BASE = \
        "/Users/rtm/Downloads/seg/v0.3_inference_20250801_v0.2/images"
    CSV_PATH = \
        "/Users/rtm/Downloads/seg/v0.3_inference_20250801_v0.2/inference_results.csv"

    output_file = \
        "/Users/rtm/Downloads/seg/v0.3_inference_20250801_v0.2/inference_results_with_image.xlsx"

    # Safety checks
    if not os.path.isdir(IMAGES_BASE):
        print(f"❌ Images base directory not found: {IMAGES_BASE}")
        sys.exit(1)
    if not os.path.isfile(CSV_PATH):
        print(f"❌ CSV file not found: {CSV_PATH}")
        sys.exit(1)

    print("📁 Images base:", IMAGES_BASE)
    print("📄 CSV path:", CSV_PATH)
    print("📊 Output:", output_file)

    success = create_excel_from_csv(IMAGES_BASE, CSV_PATH, output_file, limit=None)
    if success:
        print(f"✅ Excel created: {output_file}")
    else:
        print("❌ Failed to create Excel")
        sys.exit(1)


if __name__ == "__main__":
    main()


