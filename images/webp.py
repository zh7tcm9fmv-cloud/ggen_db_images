#!/usr/bin/env python3
"""
Convert PNG/JPG images to WebP format for faster page loads.

Uses image_index.json for folder roots, then scans each root recursively for PNG/JPG/JPEG
(including files not listed in the index). Run from project root or specify --base-dir.

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

_RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})


def save_image_as_webp(img: Image.Image, dest: Path, quality: int) -> None:
    """
    Write WebP. Use lossless encoding for RGBA (portraits/UI with transparency).
    Lossy RGB WebP can damage alpha and cause black boxes or edge artifacts.
    """
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        img.save(dest, "WEBP", lossless=True, method=6)
    else:
        img = img.convert("RGB")
        img.save(dest, "WEBP", quality=quality, method=6)


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


def find_all_image_folders(base_dir: Path) -> set[Path]:
    """
    Find all folders containing PNG/JPG/JPEG files recursively.
    Returns set of folder paths.
    """
    image_folders = set()
    for root, dirs, files in os.walk(base_dir):
        root_path = Path(root)
        # Check if this folder has any raster images
        has_images = any(
            Path(f).suffix.lower() in _RASTER_SUFFIXES for f in files
        )
        if has_images:
            image_folders.add(root_path)
    return image_folders


def _rel_for_print(path: Path, base_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(base_dir.resolve()))
    except ValueError:
        return str(path)


def convert_one_raster(
    src_path: Path,
    *,
    base_dir: Path,
    quality: int,
    dry_run: bool,
    skip_existing: bool,
) -> tuple[int, int, int]:
    """
    Convert a single PNG/JPG/JPEG to WebP beside the source.
    Returns (converted, skipped, errors) as 0/1 increments.
    """
    if not src_path.is_file():
        return 0, 0, 0
    if src_path.suffix.lower() not in _RASTER_SUFFIXES:
        return 0, 0, 0
    webp_path = src_path.with_suffix(".webp")
    if skip_existing and webp_path.exists():
        return 0, 1, 0
    rel = _rel_for_print(src_path, base_dir)
    if dry_run:
        print(f"  [would convert] {rel}")
        return 1, 0, 0
    try:
        with Image.open(src_path) as img:
            save_image_as_webp(img, webp_path, quality)
        print(f"  [ok] {rel}")
        return 1, 0, 0
    except Exception as e:
        print(f"  [error] {src_path}: {e}")
        return 0, 0, 1


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
        if src_path.suffix.lower() not in _RASTER_SUFFIXES:
            continue

        c, s, e = convert_one_raster(
            src_path,
            base_dir=base_dir,
            quality=quality,
            dry_run=dry_run,
            skip_existing=skip_existing,
        )
        converted += c
        skipped += s
        errors += e
        if c and converted % 100 == 0 and not dry_run:
            print(f"  ... {converted} converted", flush=True)

    return converted, skipped, errors


def convert_to_webp(
    base_dir: Path,
    image_index: dict,
    quality: int = 85,
    dry_run: bool = False,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    """
    For each folder key in image_index, recursively find all PNG/JPG/JPEG under that
    directory (including subfolders and files not listed in the index), and convert
    each once (paths deduplicated across folders).

    ALSO discovers folders not in the index and converts them too.

    Indexed filenames that are missing on disk are reported once per entry.
    Returns (converted_count, skipped_count, error_count).
    """
    converted = 0
    skipped = 0
    errors = 0
    processed = set()

    # Build set of indexed folder paths
    indexed_folders = set()
    for folder in image_index.keys():
        src_dir = resolve_index_folder(base_dir, folder)
        if src_dir.exists():
            indexed_folders.add(src_dir.resolve())

    # Find all folders containing images (even if not indexed)
    images_dir = base_dir / "images" if (base_dir / "images").exists() else base_dir
    all_image_folders = find_all_image_folders(images_dir)
    
    # Warn about unindexed folders
    unindexed_folders = []
    for folder in all_image_folders:
        # Check if this folder or any parent is indexed
        is_covered = False
        for indexed in indexed_folders:
            try:
                folder.relative_to(indexed)
                is_covered = True
                break
            except ValueError:
                continue
        if not is_covered:
            unindexed_folders.append(folder)
    
    if unindexed_folders:
        print("⚠️  WARNING: Found folders with images NOT in image_index.json:")
        for folder in sorted(unindexed_folders):
            rel = _rel_for_print(folder, base_dir)
            print(f"  - {rel}")
        print("  These will be converted, but consider updating image_index.json\n")

    # Combine indexed folders with all discovered folders
    all_folders_to_process = indexed_folders | all_image_folders

    # Warn on index entries pointing to missing flat paths (helps typos / stale index).
    for folder, files in image_index.items():
        src_dir = resolve_index_folder(base_dir, folder)
        if not src_dir.exists():
            continue
        for filename in files:
            if not filename.lower().endswith(tuple(_RASTER_SUFFIXES)):
                continue
            src_path = src_dir / filename
            if not src_path.is_file():
                if not dry_run:
                    print(f"  [skip] Index lists missing file: {folder}/{filename}")

    # Process all folders (indexed + discovered)
    for src_dir in sorted(all_folders_to_process):
        if not src_dir.exists():
            continue
        for src_path in src_dir.rglob("*"):
            key = src_path.resolve()
            if key in processed:
                continue
            if not src_path.is_file():
                continue
            if src_path.suffix.lower() not in _RASTER_SUFFIXES:
                continue
            processed.add(key)
            c, s, e = convert_one_raster(
                src_path,
                base_dir=base_dir,
                quality=quality,
                dry_run=dry_run,
                skip_existing=skip_existing,
            )
            converted += c
            skipped += s
            errors += e
            if c and converted % 100 == 0 and not dry_run:
                print(f"  ... {converted} converted", flush=True)

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
            print("Warning: image_index.json not found or empty - will scan all folders")
            image_index = {}

        print(
            f"Indexed folder roots: {len(image_index)} "
            f"(scanning ALL folders with images, including those not in index)"
        )
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