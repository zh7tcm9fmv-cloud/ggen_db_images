#!/usr/bin/env python3
"""
Convert PNG/JPG images to WebP format for faster page loads.

Uses image_index.json to find images. Run from project root or specify --base-dir.

Usage:
  # Convert images in local static folder (default)
  python scripts/convert_to_webp.py

  # Convert images in the ggen_db_images repo
  python scripts/convert_to_webp.py --base-dir "C:/path/to/ggen_db_images"

  # Dry run (show what would be converted)
  python scripts/convert_to_webp.py --dry-run

  # Custom quality (default 85, range 1-100)
  python scripts/convert_to_webp.py --quality 90
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


def load_image_index(project_root: Path) -> dict:
    """Load image_index.json from project root."""
    index_path = project_root / "image_index.json"
    if not index_path.exists():
        return {}
    with open(index_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_index_folder(base_dir: Path, folder_key: str) -> Path:
    """
    Join image_index folder keys to base_dir without duplicating 'images/'.

    Keys are like 'images/Background' or 'images/Option-Part (Modification)/Sprite'.
    If base_dir already ends with .../images, strip the leading 'images/' from the key
    so we don't get .../images/images/...
    """
    base_dir = base_dir.resolve()
    fk = folder_key.replace("\\", "/").strip("/")
    if base_dir.name.lower() == "images" and fk.startswith("images/"):
        fk = fk[len("images/") :]
    return base_dir / fk


def convert_directory_recursive(
    base_dir: Path,
    quality: int = 85,
    dry_run: bool = False,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """
    Convert all PNG/JPG in directory tree to WebP (ignores image_index).
    Returns (converted_count, skipped_count, error_count).
    """
    converted = 0
    skipped = 0
    errors = 0

    for src_path in base_dir.rglob("*"):
        if not src_path.is_file():
            continue
        if src_path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue

        webp_path = src_path.with_suffix(".webp")
        if skip_existing and webp_path.exists():
            skipped += 1
            continue

        if dry_run:
            print(f"  [would convert] {src_path.relative_to(base_dir)}")
            converted += 1
            continue

        try:
            with Image.open(src_path) as img:
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    img.save(webp_path, "WEBP", quality=quality, method=6)
                else:
                    img = img.convert("RGB")
                    img.save(webp_path, "WEBP", quality=quality, method=6)
            converted += 1
            if converted % 100 == 0:
                print(f"  ... {converted} converted", flush=True)
        except Exception as e:
            errors += 1
            print(f"  [error] {src_path}: {e}", flush=True)

    return converted, skipped, errors


def convert_to_webp(
    base_dir: Path,
    image_index: dict,
    quality: int = 85,
    dry_run: bool = False,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """
    Convert all indexed images to WebP.
    Returns (converted_count, skipped_count, error_count).
    """
    converted = 0
    skipped = 0
    errors = 0

    for folder, files in image_index.items():
        # folder is e.g. "images/Background", "images/Option-Part (Modification)/Sprite"
        src_dir = resolve_index_folder(base_dir, folder)
        if not src_dir.exists():
            if not dry_run:
                print(f"  [skip] Folder not found: {src_dir}")
            continue

        for filename in files:
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            src_path = src_dir / filename
            webp_name = Path(filename).stem + ".webp"
            webp_path = src_dir / webp_name

            if not src_path.exists():
                if not dry_run:
                    print(f"  [skip] Source not found: {src_path}")
                continue

            if skip_existing and webp_path.exists():
                skipped += 1
                continue

            if dry_run:
                print(f"  [would convert] {src_path} -> {webp_path}")
                converted += 1
                continue

            try:
                with Image.open(src_path) as img:
                    # Handle transparency for PNG
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGBA")
                        img.save(webp_path, "WEBP", quality=quality, method=6)
                    else:
                        img = img.convert("RGB")
                        img.save(webp_path, "WEBP", quality=quality, method=6)
                converted += 1
                print(f"  [ok] {folder}/{filename} -> {webp_name}")
            except Exception as e:
                errors += 1
                print(f"  [error] {src_path}: {e}")

    return converted, skipped, errors


def main():
    parser = argparse.ArgumentParser(
        description="Convert PNG/JPG images to WebP using image_index.json"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help=(
            "Root for image files. With image_index mode: repo root (…/ggen_db_images) OR "
            "…/ggen_db_images/images — both work. With --recursive: scanned recursively."
        ),
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="WebP quality 1-100 (default: 85)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without writing files",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-convert even if WebP already exists",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        dest="convert_all",
        help="Convert all PNG/JPG in base-dir recursively (ignore image_index)",
    )
    args = parser.parse_args()

    # Resolve base directory
    if args.base_dir is not None:
        base_dir = Path(args.base_dir).resolve()
    else:
        # Default: use static folder if it exists, else project root
        static_images = PROJECT_ROOT / "static" / "images"
        if (PROJECT_ROOT / "static" / "images").exists():
            base_dir = PROJECT_ROOT / "static"
        else:
            base_dir = PROJECT_ROOT

    if not base_dir.exists():
        print(f"Error: Base directory does not exist: {base_dir}")
        sys.exit(1)

    quality = min(100, max(1, args.quality))
    skip_existing = not args.no_skip_existing

    if args.convert_all:
        # Recursive conversion - no index needed
        print(f"Converting all PNG/JPG in: {base_dir}")
        if args.dry_run:
            print("(Dry run - no files will be written)")
        print()
        converted, skipped, errors = convert_directory_recursive(
            base_dir=base_dir,
            quality=quality,
            dry_run=args.dry_run,
            skip_existing=skip_existing,
        )
    else:
        # Use image_index
        image_index = load_image_index(PROJECT_ROOT)
        if not image_index:
            print("Error: image_index.json not found or empty")
            sys.exit(1)

        total_files = sum(
            len([f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg"))])
            for files in image_index.values()
        )
        print(f"Found {total_files} images in index across {len(image_index)} folders")
        print(f"Base directory: {base_dir}")
        if base_dir.name.lower() == "images":
            print("(Index paths join without duplicating 'images/' — OK for …/ggen_db_images/images)")
        if args.dry_run:
            print("(Dry run - no files will be written)")
        print()

        converted, skipped, errors = convert_to_webp(
            base_dir=base_dir,
            image_index=image_index,
            quality=quality,
            dry_run=args.dry_run,
            skip_existing=skip_existing,
        )

    print()
    print(f"Done: {converted} converted, {skipped} skipped (existing), {errors} errors")


if __name__ == "__main__":
    main()
