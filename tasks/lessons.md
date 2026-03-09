# Lessons — cadnano2

_Hard-won lessons, gotchas, and things that broke before._
_This file is append-mostly. Only remove entries proven wrong._

## General

- 1×N linear chain scaffold routing only works for even N ≥ 4. Odd N is geometrically impossible: the honeycomb crossover table ordering (High = Low + 1 for all directions) makes the interior helix constraint (pair_ret < pair_out) incompatible with the end helix parity constraint (even end helix needs pair_out < pair_ret) for adjacent same-direction helices. The 2×N grid avoids this because cross-row connections use different directions with different crossover tables.
