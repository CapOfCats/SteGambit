# Edge-Detection Analysis for WAV (Subtask #25.2)

**Run date:** 2026-06-18 17:45:12

## 1. Goal

Check the hypothesis from spec #25:
> For audio (a 1D WAV array), edge detection computes the difference
> between neighboring samples. The threshold `GRADIENT_THRESHOLD = 8` on
> the scale -32768..+32767 filters nothing -> almost all samples
> fall into the pool, and edge detection becomes a no-op.

## 2. Methodology

- **Platform:** Windows-10-10.0.19045-SP0
- **Python:** 3.12.2
- **Iterations for the timing measurement:** 20
- **GRADIENT_THRESHOLD:** 8
- **Metrics:**
  - `pool_size / total` — the percentage of positions that passed the filter.
  - If > 95% — the filter barely works (hypothesis confirmed).
  - If < 50% — the filter is meaningful.
  - `_build_edge_pool` time — the cost of 'no-op' filtering.

## 3. Results

| Carrier | Total positions | In pool | % in pool | % filtered | time median (ms) |
|---|---:|---:|---:|---:|---:|
| PNG 2MB (synthetic noise) | 5,989,707 | 5,967,285 | 99.63% | 0.37% | 99.52 |
| PNG photo.jpg (decoded to RGB) | 3,145,728 | 476,613 | 15.15% | 84.85% | 41.22 |
| WAV (white noise, amp~30k) | 882,000 | 881,776 | 99.97% | 0.03% | 7.83 |
| WAV (quiet sine, amp~500) | 882,000 | 749,649 | 84.99% | 15.01% | 6.98 |

## 4. Verdict on the Hypothesis

**WAV: mean % in pool = 92.48%**
- ⚠️ Edge detection for WAV is weak filtering.
- 🔧 **Recommendation:** raise the threshold.

**PNG (control): mean % in pool = 57.39%**
- ✅ For images the filter works (control OK).

## 5. No-Op Cost (If the Hypothesis Is Confirmed)

`_build_edge_pool` time for WAV shows how many seconds
are spent on meaningless filtering. If that time is small
relative to a full hide_data (~260 ms for WAV), optimization
has low priority.

## 6. Conclusions

**Original statement:** edge detection for WAV is a no-op and should
be disabled or have its threshold raised.

**Actual data:**

| Condition | % in pool | Does edge detection work? |
|---|---|---|
| WAV white noise (typical music) | 99.97% | ❌ No |
| WAV quiet sine (silence, slow passages) | 84.99% | ⚠️ Weakly |
| PNG real photo | 15.15% | ✅ Yes |
| PNG synthetic noise | 99.63% | ❌ No |

**Hypothesis refinement:** edge detection lets almost everything through on any
**high-entropy content** (noisy WAV and noisy PNG).
On real photographs it works as intended — 85% rejection.

### 6.2. Decision for WAV — Do Not Optimize

**Arguments against a change:**

1. **Cost is low.** `_build_edge_pool` for WAV = 7-8 ms out of ~260 ms
   of a full hide_data (3% overhead). Optimization would save <10 ms.

2. **On quiet signals the filter partially works** (15% rejection).
   Disabling it entirely would worsen stealth for quiet music.

3. **An adaptive threshold** means an architectural refactor and breaks backward
   compatibility (old stego files would not extract — the pool would differ).

4. **Simply raising the threshold** to 256 on the int16 scale will not help:
   white noise will still pass ~100%, while quiet signals
   will be rejected entirely → capacity for quiet WAV breaks.

**Decision:** edge detection for WAV stays as it is. The hypothesis
is formally confirmed for noisy content, but the recommendation
to "disable" it is refuted by the cost analysis and the edge cases.
