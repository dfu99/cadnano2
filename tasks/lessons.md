# Lessons — cadnano2

_Hard-won lessons, gotchas, and things that broke before._
_This file is append-mostly. Only remove entries proven wrong._

## General

- Headless testing of AgentMethods works with `QT_QPA_PLATFORM=offscreen` + `cadnano.initAppWithGui()` + a MockDC class. `HeadlessCadnano` is missing `documentWasCreatedSignal`, so the GUI init path (with offscreen platform) is required.
- Insertions in cadnano are position-based, not strand-based. Adding an insertion to a scaffold strand at index X also appears on the staple at index X. `listInsertions` will report both scaffold and staple entries for the same position — this is correct. When adding insertion patterns, only add to one strand type per position.
- `removeCrossoversForPair` removes more crossovers than `addCrossoversForPair` creates — because `addCrossoversForPair` creates double crossovers (2 half-crossovers as one logical unit), but the removal counts each half-crossover individually. This is cosmetic (removal is correct) but the count mismatch can be confusing.
- The DocumentController method for creating a honeycomb part is `actionAddHoneycombPartSlot()`, not `actionNewHoneycombPartSlot()`.
- The autobreak plugin's `__init__.py` has legacy `import cadnano` (not `cadnano2`). To import `autobreak.py` functions from agent code, use `importlib.util` to load the file directly and bypass the package init.
- `Oligo.color()` not `Oligo.getColor()` — cadnano2 uses `color()` as property-style method.
- 1×N linear chain scaffold routing only works for even N ≥ 4. Odd N is geometrically impossible: the honeycomb crossover table ordering (High = Low + 1 for all directions) makes the interior helix constraint (pair_ret < pair_out) incompatible with the end helix parity constraint (even end helix needs pair_out < pair_ret) for adjacent same-direction helices. The 2×N grid avoids this because cross-row connections use different directions with different crossover tables.
- `moveCrossover` had a bug: the overlap check rejected moves even when the only "neighboring" strands were the other half-crossover strands being moved simultaneously. Fixed by collecting `moving_strands` set and skipping overlap checks against co-moving strands.
- `listCrossovers` and `getValidCrossoverPositions` return strings, not dicts. To use their output programmatically, parse with regex + `ast.literal_eval`.
- Staple double crossovers have widely spaced half-crossover positions (e.g., low_idx=63, high_idx=83) unlike scaffold crossovers which are adjacent (88, 89). `moveCrossover` doesn't yet handle staple crossovers correctly — the intermediate strand segments between the two half-crossover positions aren't accounted for.
- Headless screenshot capture works: `scene.render(painter, source=items_rect)` on a `QImage` with `QT_QPA_PLATFORM=offscreen`. Use `items_rect = scene.itemsBoundingRect()` with margins for good framing.
