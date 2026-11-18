# ADR 010: Encapsulating Spreading Logic and Detaching Service from Crypto

**Date:** 10.06.2026
**Status:** Accepted

## Context
While integrating the LSB (with edge detection) and DCT (with mid-frequency coefficients) algorithms, the logic for pseudo-random shuffling of the coordinate pool (password-based PRNG) leaked into the facade layer (`StegoService`). An asymmetry appeared: for `SmartSpreader` (LSB), capacity was computed through the Spreader object, while for DCT `StegoService` accessed the pool and the functions in `seeding.py` directly.

## Decision
1. Introduce a single polymorphic Spreader interface: `SmartSpreader` for LSB and `DctSpreader` for DCT.
2. The Spreader contract includes the methods `generate_coords(...)` and `get_max_capacity_bits(...)`.
3. The service layer talks only to the Spreader abstraction. The `analyze_capacity` estimate is fully delegated to Spreaders.
4. Do not introduce redundant wrapper classes (`PasswordSeededShuffler`, `EdgeDetector`). Prefer functional composition (pure functions from `seeding.py` and private methods inside Spreader), following the Pythonic way and YAGNI.

## Consequences
* **Positive:** Full SRP compliance. Formats and algorithms are no longer mixed in the facade. Capacity-estimate test failures are gone, because DCT capacity is now computed with Spreader logic taken into account.
* **Negative:** None found. The codebase is cleaner without excess OOP overhead.
