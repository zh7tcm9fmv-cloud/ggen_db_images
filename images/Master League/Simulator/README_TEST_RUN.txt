MLS gated test assets — Griepe EX + Hydra EX

Layout:
  koma/g2170u02150/   Griepe EX IngameKoma frames (PNG)
  koma/g2170u00650/   Hydra EX IngameKoma frames (PNG)
  koma/ogk_*.png      ogk fallback thumbs (if present)
  fx/                 hit / muzzle / trailvernier flipbook frames (PNG)
  meta/               motion + et/map MonoBehaviour JSON + TEST_RUN_MANIFEST.json

What you need to do:
  1) Convert all PNG under koma/ and fx/ to WebP (preserve alpha).
  2) Keep the same filenames (only change extension).
  3) Add/update image_index.json entries for this folder.
  4) Tell me when WebP is ready — then wire gated /mls for these two IDs only.

Not needed for first smoke (but already staged): et01, map, weapon2/3, melee FX.
You can WebP everything now or only standby+weapon1+beambuster first.

Counts: {"koma_griepe": 128, "koma_hydra": 119, "ogk": 2, "fx": 636, "meta_json": 7, "fx_unique_prefixes": 206}
