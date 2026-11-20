#!/usr/bin/env python3
"""
Convert PNG/JPG images to WebP beside the source — same pixel size, max quality.

Never resizes. Never strips alpha. Default is lossless WebP for every mode so
UI plates / portraits keep exact pixels. Optional --lossy for smaller RGB files.

Speed note: default lossless + method=6 is the slowest Pillow WebP encode
(highest effort). That is intentional for fidelity — not a hang. Use
--method 4 (or lower) for faster runs; --lossy for opaque RGB only.

Usage (from this folder or with an explicit path):
  python webp.py
  python webp.py --base-dir "C:/Users/Mikew0911/Desktop/ggen_db_images"
  python webp.py --dry-run
  python webp.py --no-skip-existing
  python webp.py --lossy --quality 95
  python webp.py --method 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore[misc, assignment]

_RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})


def save_image_as_webp(
    img: Image.Image,
    dest: Path,
    *,
    lossless: bool,
    quality: int,
    method: int,
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
        rgba.save(dest, "WEBP", lossless=True, exact=True, method=method)
        return rgba.size
    if lossless:
        rgb = img.convert("RGB")
        rgb.save(dest, "WEBP", lossless=True, exact=True, method=method)
        return rgb.size
    rgb = img.convert("RGB")
    rgb.save(dest, "WEBP", quality=quality, method=method)
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


def _fmt_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:  # NaN
        return "--:--"
    sec = int(round(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


class Progress:
    """
    Live progress: count, %, elapsed, ETA, rate, current file.
    Uses tqdm when installed; otherwise a single-line \\r bar (no extra deps).
    """

    def __init__(self, total: int, *, enabled: bool = True, desc: str = "webp"):
        self.total = max(0, total)
        self.enabled = enabled and self.total > 0
        self.done = 0
        self.converted = 0
        self.skipped = 0
        self.errors = 0
        self._t0 = time.monotonic()
        self._bar = None
        self._last_len = 0
        if not self.enabled:
            return
        if tqdm is not None:
            self._bar = tqdm(
                total=self.total,
                desc=desc,
                unit="file",
                dynamic_ncols=True,
                mininterval=0.2,
            )

    def update(
        self,
        *,
        converted: int = 0,
        skipped: int = 0,
        errors: int = 0,
        current: str = "",
    ) -> None:
        self.done += 1
        self.converted += converted
        self.skipped += skipped
        self.errors += errors
        if not self.enabled:
            return
        if self._bar is not None:
            postfix = {
                "ok": self.converted,
                "skip": self.skipped,
                "err": self.errors,
            }
            self._bar.set_postfix(postfix, refresh=False)
            if current:
                # Keep postfix readable — short name only.
                name = Path(current).name
                self._bar.set_description_str(f"webp {name[:28]}")
            self._bar.update(1)
            return
        elapsed = time.monotonic() - self._t0
        rate = self.done / elapsed if elapsed > 0 else 0.0
        remain = self.total - self.done
        eta = (remain / rate) if rate > 0 else float("nan")
        pct = 100.0 * self.done / self.total if self.total else 100.0
        bar_w = 24
        filled = int(bar_w * self.done / self.total) if self.total else bar_w
        bar = "#" * filled + "-" * (bar_w - filled)
        name = Path(current).name if current else ""
        if len(name) > 36:
            name = name[:33] + "..."
        line = (
            f"\r[{bar}] {self.done}/{self.total} {pct:5.1f}%  "
            f"ok={self.converted} skip={self.skipped} err={self.errors}  "
            f"{rate:0.2f}/s  elapsed {_fmt_duration(elapsed)}  "
            f"ETA {_fmt_duration(eta)}  {name}"
        )
        pad = max(0, self._last_len - len(line))
        sys.stdout.write(line + (" " * pad))
        sys.stdout.flush()
        self._last_len = len(line)

    def close(self) -> None:
        if not self.enabled:
            return
        if self._bar is not None:
            self._bar.close()
            return
        sys.stdout.write("\n")
        sys.stdout.flush()


def convert_one_raster(
    src_path: Path,
    *,
    base_dir: Path,
    lossless: bool,
    quality: int,
    method: int,
    dry_run: bool,
    skip_existing: bool,
    quiet: bool,
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
        if not quiet:
            print(f"  [would convert] {rel}")
        return 1, 0, 0
    try:
        with Image.open(src_path) as img:
            src_size = img.size
            out_w, out_h = save_image_as_webp(
                img,
                webp_path,
                lossless=lossless,
                quality=quality,
                method=method,
            )
            if (out_w, out_h) != src_size:
                # Should never happen — hard fail so a bad Pillow path cannot ship.
                webp_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"resolution changed {src_size} → {(out_w, out_h)}; refused to keep WebP"
                )
        if not quiet:
            print(f"  [ok] {rel}  {src_size[0]}×{src_size[1]}")
        return 1, 0, 0
    except Exception as e:
        # Always show errors even with a progress bar.
        print(f"\n  [error] {src_path}: {e}", flush=True)
        return 0, 0, 1


def _iter_rasters_under(folder: Path):
    for src_path in folder.rglob("*"):
        if not src_path.is_file():
            continue
        if src_path.suffix.lower() not in _RASTER_SUFFIXES:
            continue
        yield src_path


def collect_rasters_recursive(base_dir: Path) -> list[Path]:
    return sorted(_iter_rasters_under(base_dir), key=lambda p: str(p).lower())


def collect_rasters_for_index(
    base_dir: Path,
    image_index: dict,
) -> tuple[list[Path], list[Path]]:
    """
    Build the work list (deduped) and report unindexed folders.
    Returns (jobs, unindexed_folders).
    """
    indexed_folders: set[Path] = set()
    for folder in image_index.keys():
        src_dir = resolve_index_folder(base_dir, folder)
        if src_dir.exists():
            indexed_folders.add(src_dir.resolve())

    images_dir = base_dir / "images" if (base_dir / "images").exists() else base_dir
    all_image_folders = find_all_image_folders(images_dir)

    unindexed_folders: list[Path] = []
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

    all_folders_to_process = indexed_folders | all_image_folders
    processed: set[Path] = set()
    jobs: list[Path] = []
    for src_dir in sorted(all_folders_to_process):
        if not src_dir.exists():
            continue
        for src_path in _iter_rasters_under(src_dir):
            key = src_path.resolve()
            if key in processed:
                continue
            processed.add(key)
            jobs.append(src_path)
    jobs.sort(key=lambda p: str(p).lower())
    return jobs, sorted(unindexed_folders)


def report_missing_index_files(base_dir: Path, image_index: dict, *, dry_run: bool) -> None:
    for folder, files in image_index.items():
        src_dir = resolve_index_folder(base_dir, folder)
        if not src_dir.exists():
            continue
        for filename in files:
            if not filename.lower().endswith(tuple(_RASTER_SUFFIXES)):
                continue
            src_path = src_dir / filename
            if not src_path.is_file() and not dry_run:
                print(f"  [skip] Index lists missing file: {folder}/{filename}")


def run_jobs(
    jobs: list[Path],
    *,
    base_dir: Path,
    lossless: bool,
    quality: int,
    method: int,
    dry_run: bool,
    skip_existing: bool,
    show_progress: bool,
    verbose: bool,
) -> tuple[int, int, int]:
    total = len(jobs)
    # Quiet per-file logs when the bar is on (unless --verbose).
    quiet = bool(show_progress and not verbose and not dry_run)
    if show_progress:
        print(f"Queued: {total} raster file(s) to scan/convert", flush=True)
        if not dry_run and lossless and method >= 6:
            print(
                "Note: lossless method=6 is slow by design (max encode effort). "
                "Not stuck — watch the bar / ETA. Faster: --method 4",
                flush=True,
            )
        print(flush=True)

    prog = Progress(total, enabled=show_progress and total > 0)
    converted = skipped = errors = 0
    try:
        for src_path in jobs:
            c, s, e = convert_one_raster(
                src_path,
                base_dir=base_dir,
                lossless=lossless,
                quality=quality,
                method=method,
                dry_run=dry_run,
                skip_existing=skip_existing,
                quiet=quiet,
            )
            converted += c
            skipped += s
            errors += e
            prog.update(
                converted=c,
                skipped=s,
                errors=e,
                current=_rel_for_print(src_path, base_dir),
            )
    finally:
        prog.close()
    return converted, skipped, errors


def convert_directory_recursive(
    base_dir: Path,
    *,
    lossless: bool = True,
    quality: int = 100,
    method: int = 6,
    dry_run: bool = False,
    skip_existing: bool = True,
    show_progress: bool = True,
    verbose: bool = False,
) -> tuple[int, int, int]:
    """
    Convert all PNG/JPG in directory tree to WebP (ignores image_index).
    Returns (converted_count, skipped_count, error_count).
    """
    print("Scanning for PNG/JPG…", flush=True)
    t0 = time.monotonic()
    jobs = collect_rasters_recursive(base_dir)
    print(f"Scan done in {_fmt_duration(time.monotonic() - t0)} ({len(jobs)} files)", flush=True)
    return run_jobs(
        jobs,
        base_dir=base_dir,
        lossless=lossless,
        quality=quality,
        method=method,
        dry_run=dry_run,
        skip_existing=skip_existing,
        show_progress=show_progress,
        verbose=verbose,
    )


def convert_to_webp(
    base_dir: Path,
    image_index: dict,
    *,
    lossless: bool = True,
    quality: int = 100,
    method: int = 6,
    dry_run: bool = False,
    skip_existing: bool = True,
    show_progress: bool = True,
    verbose: bool = False,
) -> tuple[int, int, int]:
    """
    For each folder key in image_index, recursively find all PNG/JPG/JPEG under that
    directory (including subfolders and files not listed in the index), and convert
    each once (paths deduplicated across folders).

    ALSO discovers folders not in the index and converts them too.

    Indexed filenames that are missing on disk are reported once per entry.
    Returns (converted_count, skipped_count, error_count).
    """
    print("Scanning folders / building job list…", flush=True)
    t0 = time.monotonic()
    jobs, unindexed_folders = collect_rasters_for_index(base_dir, image_index)
    print(
        f"Scan done in {_fmt_duration(time.monotonic() - t0)} "
        f"({len(jobs)} files across {len(set(p.parent for p in jobs))} folders)",
        flush=True,
    )

    if unindexed_folders:
        print("WARNING: Found folders with images NOT in image_index.json:")
        for folder in unindexed_folders:
            rel = _rel_for_print(folder, base_dir)
            print(f"  - {rel}")
        print("  These will be converted, but consider updating image_index.json\n")

    report_missing_index_files(base_dir, image_index, dry_run=dry_run)

    return run_jobs(
        jobs,
        base_dir=base_dir,
        lossless=lossless,
        quality=quality,
        method=method,
        dry_run=dry_run,
        skip_existing=skip_existing,
        show_progress=show_progress,
        verbose=verbose,
    )


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
        "--method",
        type=int,
        default=6,
        choices=range(0, 7),
        metavar="0-6",
        help=(
            "WebP encoder effort 0=fast … 6=slowest/best (Pillow default here: 6). "
            "Lossless method=6 is why big batches feel slow — try 4 for a speed bump."
        ),
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
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the progress bar (print every file instead)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each converted file even when the progress bar is on",
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
    method = int(args.method)
    skip_existing = not args.no_skip_existing
    show_progress = not args.no_progress

    print(
        f"Mode: {'lossless (max quality)' if lossless else f'lossy RGB quality={quality} (RGBA still lossless)'}"
    )
    print(f"Encoder method: {method}/6 ({'slowest' if method >= 6 else 'faster' if method <= 3 else 'balanced'})")
    print("Resize: never — output WebP keeps source width×height")
    if show_progress and tqdm is None:
        print("(Progress: built-in bar — pip install tqdm for a richer bar)")

    if args.convert_all:
        print(f"Converting all PNG/JPG in: {base_dir}")
        if args.dry_run:
            print("(Dry run - no files will be written)")
        print()
        converted, skipped, errors = convert_directory_recursive(
            base_dir=base_dir,
            lossless=lossless,
            quality=quality,
            method=method,
            dry_run=args.dry_run,
            skip_existing=skip_existing,
            show_progress=show_progress,
            verbose=args.verbose,
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
            method=method,
            dry_run=args.dry_run,
            skip_existing=skip_existing,
            show_progress=show_progress,
            verbose=args.verbose,
        )

    print()
    print(f"Done: {converted} converted, {skipped} skipped (existing), {errors} errors")


if __name__ == "__main__":
    main()
