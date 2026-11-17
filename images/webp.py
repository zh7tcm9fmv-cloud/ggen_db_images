#!/usr/bin/env python3
"""
Convert PNG/JPG images to WebP beside the source — same pixel size, max quality.

Never resizes. Never strips alpha. Default is lossless WebP for every mode so
UI plates / portraits keep exact pixels. Optional --lossy for smaller RGB files.

Usage (from this folder or with an explicit path):
  python webp.py
  python webp.py --base-dir "C:/Users/Mikew0911/Desktop/ggen_db_images"
  python webp.py --dry-run
  python webp.py --no-skip-existing
  python webp.py --lossy --quality 95
"""

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# Repo root is parent of images/ when this file lives at …/ggen_db_images/images/webp.py
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "images" else SCRIPT_DIR
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

_RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})


def save_image_as_webp(
    img: Image.Image,
    dest: Path,
    *,
    lossless: bool,
    quality: int,
) -> tuple[int, int]:
    """
    Write WebP at the same width×height as the source (no resample).

    Returns (width, height) written.
    """
    w, h = img.size
    # Keep palette / alpha fidelity: expand P/LA to RGBA before encode.
    if img.mode in ("RGBA", "LA", "P") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        # Always lossless for alpha — lossy WebP wrecks edges / can invent black boxes.
        rgba.save(dest, "WEBP", lossless=True, exact=True, method=6)
        return rgba.size
    if lossless:
        rgb = img.convert("RGB")
        rgb.save(dest, "WEBP", lossless=True, exact=True, method=6)
        return rgb.size
    rgb = img.convert("RGB")
    rgb.save(dest, "WEBP", quality=quality, method=6)
    return rgb.size


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
    lossless: bool,
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
            src_size = img.size
            out_w, out_h = save_image_as_webp(
                img, webp_path, lossless=lossless, quality=quality
            )
            if (out_w, out_h) != src_size:
                # Should never happen — hard fail so a bad Pillow path cannot ship.
                webp_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"resolution changed {src_size} → {(out_w, out_h)}; refused to keep WebP"
                )
        print(f"  [ok] {rel}  {src_size[0]}×{src_size[1]}")
        return 1, 0, 0
    except Exception as e:
        print(f"  [error] {src_path}: {e}")
        return 0, 0, 1


def convert_directory_recursive(
    base_dir: Path,
    *,
    lossless: bool = True,
    quality: int = 100,
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
            lossless=lossless,
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
    *,
    lossless: bool = True,
    quality: int = 100,
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

    indexed_folders = set()
    for folder in image_index.keys():
        src_dir = resolve_index_folder(base_dir, folder)
        if src_dir.exists():
            indexed_folders.add(src_dir.resolve())

    images_dir = base_dir / "images" if (base_dir / "images").exists() else base_dir
    all_image_folders = find_all_image_folders(images_dir)

    unindexed_folders = []
    for folder in all_image_folders:
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
        print("WARNING: Found folders with images NOT in image_index.json:")
        for folder in sorted(unindexed_folders):
            rel = _rel_for_print(folder, base_dir)
            print(f"  - {rel}")
        print("  These will be converted, but consider updating image_index.json\n")

    all_folders_to_process = indexed_folders | all_image_folders

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
                lossless=lossless,
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
        description=(
            "Convert PNG/JPG → WebP at the same resolution. "
            "Default = lossless (max quality). Never downscales."
        )
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
        "--lossy",
        action="store_true",
        help=(
            "Allow lossy WebP for opaque RGB only (smaller files). "
            "RGBA/transparent always stays lossless. Default is fully lossless."
        ),
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=100,
        help="Lossy WebP quality 1-100 when --lossy is set (default: 100). Ignored for lossless.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without writing files",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-convert even if WebP already exists (use to upgrade old lossy encodes)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        dest="convert_all",
        help="Convert all PNG/JPG in base-dir recursively (ignore image_index)",
    )
    args = parser.parse_args()

    if args.base_dir is not None:
        base_dir = Path(args.base_dir).resolve()
    else:
        static_images = PROJECT_ROOT / "static" / "images"
        if static_images.exists():
            base_dir = PROJECT_ROOT / "static"
        else:
            # Default when script lives under ggen_db_images/images/
            base_dir = PROJECT_ROOT

    if not base_dir.exists():
        print(f"Error: Base directory does not exist: {base_dir}")
        sys.exit(1)

    lossless = not args.lossy
    quality = min(100, max(1, args.quality))
    skip_existing = not args.no_skip_existing

    print(
        f"Mode: {'lossless (max quality)' if lossless else f'lossy RGB quality={quality} (RGBA still lossless)'}"
    )
    print("Resize: never — output WebP keeps source width×height")

    if args.convert_all:
        print(f"Converting all PNG/JPG in: {base_dir}")
        if args.dry_run:
            print("(Dry run - no files will be written)")
        print()
        converted, skipped, errors = convert_directory_recursive(
            base_dir=base_dir,
            lossless=lossless,
            quality=quality,
            dry_run=args.dry_run,
            skip_existing=skip_existing,
        )
    else:
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
            lossless=lossless,
            quality=quality,
            dry_run=args.dry_run,
            skip_existing=skip_existing,
        )

    print()
    print(f"Done: {converted} converted, {skipped} skipped (existing), {errors} errors")


if __name__ == "__main__":
    main()
