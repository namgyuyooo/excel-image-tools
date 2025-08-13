#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import glob
from typing import Optional

from create_excel_from_seg_csv import normalize_relative_path, resolve_image_path


IMAGES_BASE = \
    "/Users/rtm/Downloads/seg/v0.3_inference_20250801_v0.2/images"
CSV_PATH = \
    "/Users/rtm/Downloads/seg/v0.3_inference_20250801_v0.2/inference_results.csv"


def debug_resolve(images_base: str, csv_img_path: str) -> None:
    rel = normalize_relative_path(csv_img_path)
    candidate = os.path.join(images_base, rel)
    rel_dir = os.path.dirname(rel)
    rel_base, _ = os.path.splitext(os.path.basename(rel))
    viz_candidate = os.path.join(images_base, rel_dir, f"{rel_base}_viz.png")

    print(f"csv_img_path     : {csv_img_path}")
    print(f"rel              : {rel}")
    print(f"candidate        : {candidate} -> {'✔' if os.path.exists(candidate) else '✘'}")
    print(f"viz_candidate    : {viz_candidate} -> {'✔' if os.path.exists(viz_candidate) else '✘'}")

    basename = os.path.basename(rel)
    base_no_ext, _ = os.path.splitext(basename)
    patterns = [
        os.path.join(images_base, "**", basename),
        os.path.join(images_base, "**", f"{base_no_ext}.*"),
        os.path.join(images_base, "**", f"*{base_no_ext}*.*"),
    ]
    for p in patterns:
        matches = glob.glob(p, recursive=True)
        print(f"glob {p} -> {len(matches)} match(es)")
        for m in matches[:3]:
            print(f"  - {m}")

    resolved = resolve_image_path(images_base, csv_img_path)
    print(f"resolved         : {resolved}")
    print('-' * 80)


def main():
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 20:
                break
            debug_resolve(IMAGES_BASE, row.get('img_path', ''))


if __name__ == "__main__":
    main()


