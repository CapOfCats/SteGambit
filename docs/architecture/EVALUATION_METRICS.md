# Metrics Architecture and Quality Assessment (Evaluation Methods)

**Context:** Effectiveness of a steganographic system rests on two conflicting parameters: visual/auditory transparency (here — Imperceptibility) and capacity (here — Capacity). An analytics module was added to the SteGambit core for automated control of these parameters.

## 1. Mathematical Metric Profiles

The system uses objective mathematical metrics to compare the original carrier ($C$) and the modified stego-carrier ($S$).

### 1.1. Mean Squared Error (MSE)
Mean squared error computes the averaged sum of differences between the original and modified states. The base formula in the spatial domain:

$$MSE = \frac{1}{M \cdot N} \sum_{i=1}^{M} \sum_{j=1}^{N} (C_{i,j} - S_{i,j})^2$$

*Where:*
* $M, N$ — dimensions of the data matrix.
* $C_{i,j}$ — element value of the original carrier.
* $S_{i,j}$ — element value of the stego-carrier.

*Architectural detail:* For multidimensional arrays (RGB, stereo WAV), MSE is computed as the mean across all dimensions.

### 1.2. Peak Signal-to-Noise Ratio (PSNR)
Peak signal-to-noise ratio. The primary distortion metric, measured in decibels (dB). Computed from MSE:

$$PSNR = 10 \cdot \log_{10} \left( \frac{MAX^2}{MSE} \right)$$

*Where:*
* $MAX$ — the maximum possible element value (255 for an 8-bit image).
* If $MSE = 0$ (the carriers are identical), $PSNR \to \infty$.

### 1.3. Size Deviation
Estimate of carrier overhead. The metric is used as a trigger that protects against structural steganalysis (a change in file entropy).

$$Deviation (\%) = \frac{Size_S - Size_C}{Size_C} \cdot 100$$

---

## 2. Architectural Quality Triggers

Hard "quality triggers" are configured for QA automation in the SteGambit pipeline. The facade (`StegoService`) and the UI layer make decisions from the following thresholds:

### Trigger 1: Visual Transparency (PSNR Threshold)
Sets the operation status from the level of introduced noise.
* **PSNR $\ge$ 40 dB:** `[ SUCCESS ]` Excellent transparency. Changes are guaranteed to be imperceptible to the HVS (Human Visual System) and the HAS (Human Auditory System). The process is marked safe.
* **30 dB $\le$ PSNR $<$ 40 dB:** `[ WARNING ]` Acceptable quality, but potentially detectable by statistical methods (inside the risk zone). The UI raises a warning (yellow).
* **PSNR $<$ 30 dB:** `[ ANOMALY ]` Unacceptable degradation. The stego-carrier is visually or audibly distorted. The UI marks the operation red (`???`).

### Trigger 2: Identity Anomaly (Infinite PSNR Zero-Embed)
* **Condition:** Computed $MSE = 0$ ($PSNR = \infty$).
* **System action:** Raise `RuntimeError("Zero-Embed")`.
* **Rationale:** If the arrays are fully identical after the pipeline runs, that is an architectural failure (the payload was not written). Steganography failed.

### Trigger 3: Structural Anomaly (Capacity Overflow)
* **Condition:** $Deviation > 30\%$.
* **System action:** Force a notification to the user.
* **Rationale:** A large file-size increase out of proportion to the original carrier is the main marker for classic antivirus products and DLP (Data Loss Prevention) systems.
