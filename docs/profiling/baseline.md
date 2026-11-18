# Performance Baseline (Subtask #25.1)

**Run date:** 2026-06-18 17:33:18

## 1. Methodology

- **Platform:** Windows-10-10.0.19045-SP0
- **Python:** 3.12.2
- **CPU:** Intel64 Family 6 Model 158 Stepping 10, GenuineIntel
- **Iterations per scenario:** 10
- **Aggregation:** median, P95, min, max (milliseconds).
- **Carriers:** PNG/WAV are synthesized from pseudonoise (seed=42),
  JPEG — `tests/artifacts/carriers/photo.jpg`.
- **Payloads:** real files from `tests/artifacts/payloads/`.
- **Modes:** FAST = `compute_visual_metrics=False` (production
  path, the default). FULL = `compute_visual_metrics=True`
  (optional analytics for detailed reports in the UI).

## 2. Wall-Time Measurements — FAST Mode (production)

This mode is used during ordinary user work. SSIM
is not computed, and the `ssim` key is absent from `response.metrics`.

| Carrier | Carrier size | Payload | Payload size | Op | median (ms) | P95 (ms) | min (ms) | max (ms) |
|---|---:|---|---:|---|---:|---:|---:|---:|
| PNG 2MB (noise) | 5858.8 KB | tiny.txt | 0.1 KB | hide | 989.5 | 1021.1 | 910.3 | 1073.2 |
| PNG 2MB (noise) | 5858.8 KB | tiny.txt | 0.1 KB | extract | 1090.9 | 1246.6 | 1016.8 | 2058.3 |
| PNG 2MB (noise) | 5858.8 KB | secret.pdf | 7.5 KB | hide | 941.5 | 968.2 | 913.6 | 1001.3 |
| PNG 2MB (noise) | 5858.8 KB | secret.pdf | 7.5 KB | extract | 1008.2 | 1040.2 | 969.4 | 1092.2 |
| PNG 2MB (noise) | 5858.8 KB | huge.bin | 499.1 KB | hide | 1053.7 | 1142.8 | 941.0 | 1405.9 |
| PNG 2MB (noise) | 5858.8 KB | huge.bin | 499.1 KB | extract | 1132.7 | 1211.8 | 1008.9 | 1364.3 |
| WAV 1MB (noise) | 1722.7 KB | tiny.txt | 0.1 KB | hide | 256.7 | 403.4 | 253.4 | 602.4 |
| WAV 1MB (noise) | 1722.7 KB | tiny.txt | 0.1 KB | extract | 275.3 | 288.3 | 268.8 | 291.2 |
| WAV 1MB (noise) | 1722.7 KB | secret.pdf | 7.5 KB | hide | 260.1 | 266.6 | 256.3 | 278.7 |
| WAV 1MB (noise) | 1722.7 KB | secret.pdf | 7.5 KB | extract | 282.1 | 296.7 | 274.4 | 303.0 |
| JPEG photo.jpg | 204.4 KB | tiny.txt | 0.1 KB | hide | 283.7 | 297.9 | 272.0 | 306.4 |
| JPEG photo.jpg | 204.4 KB | tiny.txt | 0.1 KB | extract | 258.6 | 260.3 | 256.7 | 267.5 |
| JPEG photo.jpg | 204.4 KB | secret.pdf | 7.5 KB | hide | 275.1 | 299.9 | 273.1 | 308.9 |
| JPEG photo.jpg | 204.4 KB | secret.pdf | 7.5 KB | extract | 259.6 | 271.7 | 256.9 | 274.9 |

## 3. Wall-Time Measurements — FULL Mode (with SSIM)

This mode is enabled by a UI flag for a detailed quality report.
An extra ~1.5s on a 2MB PNG comes from `skimage.structural_similarity`.

| Carrier | Carrier size | Payload | Payload size | Op | median (ms) | P95 (ms) | min (ms) | max (ms) |
|---|---:|---|---:|---|---:|---:|---:|---:|
| PNG 2MB (noise) | 5858.8 KB | tiny.txt | 0.1 KB | hide | 1910.5 | 2019.6 | 1832.0 | 2106.3 |
| PNG 2MB (noise) | 5858.8 KB | tiny.txt | 0.1 KB | extract | 1026.2 | 1088.7 | 992.6 | 1093.1 |
| PNG 2MB (noise) | 5858.8 KB | secret.pdf | 7.5 KB | hide | 1898.1 | 1979.6 | 1865.8 | 2003.3 |
| PNG 2MB (noise) | 5858.8 KB | secret.pdf | 7.5 KB | extract | 1026.2 | 1159.7 | 1013.2 | 1230.1 |
| PNG 2MB (noise) | 5858.8 KB | huge.bin | 499.1 KB | hide | 1991.6 | 2040.9 | 1837.9 | 2223.2 |
| PNG 2MB (noise) | 5858.8 KB | huge.bin | 499.1 KB | extract | 1066.5 | 1106.6 | 984.8 | 1173.8 |
| WAV 1MB (noise) | 1722.7 KB | tiny.txt | 0.1 KB | hide | 257.8 | 262.0 | 255.7 | 267.0 |
| WAV 1MB (noise) | 1722.7 KB | tiny.txt | 0.1 KB | extract | 280.7 | 315.8 | 273.1 | 321.4 |
| WAV 1MB (noise) | 1722.7 KB | secret.pdf | 7.5 KB | hide | 259.8 | 261.1 | 253.1 | 261.8 |
| WAV 1MB (noise) | 1722.7 KB | secret.pdf | 7.5 KB | extract | 283.2 | 287.7 | 272.8 | 300.6 |
| JPEG photo.jpg | 204.4 KB | tiny.txt | 0.1 KB | hide | 279.7 | 302.0 | 273.6 | 303.0 |
| JPEG photo.jpg | 204.4 KB | tiny.txt | 0.1 KB | extract | 260.7 | 274.4 | 257.5 | 291.7 |
| JPEG photo.jpg | 204.4 KB | secret.pdf | 7.5 KB | hide | 275.3 | 286.3 | 273.3 | 309.7 |
| JPEG photo.jpg | 204.4 KB | secret.pdf | 7.5 KB | extract | 258.3 | 262.3 | 256.2 | 264.7 |

## 4. Mode Comparison — Visual-Metrics Overhead

The `overhead` column shows how much the SSIM computation adds.

| Carrier | Payload | hide median (fast) | hide median (full) | overhead (ms) | overhead (%) |
|---|---|---:|---:|---:|---:|
| PNG 2MB (noise) | tiny.txt | 989.5 | 1910.5 | +921.0 | +93.1% |
| PNG 2MB (noise) | secret.pdf | 941.5 | 1898.1 | +956.6 | +101.6% |
| PNG 2MB (noise) | huge.bin | 1053.7 | 1991.6 | +937.9 | +89.0% |
| WAV 1MB (noise) | tiny.txt | 256.7 | 257.8 | +1.1 | +0.4% |
| WAV 1MB (noise) | secret.pdf | 260.1 | 259.8 | -0.3 | -0.1% |
| JPEG photo.jpg | tiny.txt | 283.7 | 279.7 | -4.0 | -1.4% |
| JPEG photo.jpg | secret.pdf | 275.1 | 275.3 | +0.1 | +0.1% |

## 5. SLA Check: hide 2MB PNG ≤ 1000 ms (FAST mode)

- **Scenario:** PNG 2MB (noise) <- secret.pdf (fast mode)
- **Median:** 941.5 ms
- **Threshold:** 1000 ms
- **Verdict:** ✅ PASS

## 6. cProfile — top-30 in FAST Mode

One hide run on a 2MB PNG without visual metrics.

```
         3751 function calls (3735 primitive calls) in 0.890 seconds

   Ordered by: cumulative time
   List reduced from 241 to 30 due to restriction <30>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.001    0.001    0.887    0.887 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\stego_service.py:59(hide_data)
        1    0.251    0.251    0.336    0.336 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\stego\spreader.py:66(generate_coords)
        1    0.001    0.001    0.224    0.224 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\formats\png.py:58(save)
        1    0.000    0.000    0.220    0.220 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\Image.py:2591(save)
        1    0.000    0.000    0.220    0.220 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\PngImagePlugin.py:1325(_save)
        1    0.000    0.000    0.220    0.220 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\ImageFile.py:644(_save)
        1    0.000    0.000    0.220    0.220 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\ImageFile.py:672(_encode_tile)
      187    0.211    0.001    0.211    0.001 {method 'encode' of 'ImagingEncoder' objects}
        1    0.000    0.000    0.207    0.207 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\crypto\engine.py:67(encrypt)
        1    0.000    0.000    0.207    0.207 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\crypto\key_manager.py:23(derive_key)
        1    0.207    0.207    0.207    0.207 {method 'derive' of 'cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC' objects}
        1    0.010    0.010    0.085    0.085 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\stego\spreader.py:30(_build_edge_pool)
        1    0.003    0.003    0.068    0.068 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\stego_service.py:362(_compute_metrics)
        1    0.036    0.036    0.064    0.064 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\analytics\metrics.py:36(calculate_psnr)
        1    0.000    0.000    0.040    0.040 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\formats\png.py:30(load)
        3    0.001    0.000    0.039    0.013 {built-in method numpy.array}
        1    0.001    0.001    0.037    0.037 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\Image.py:811(__array_interface__)
        1    0.000    0.000    0.037    0.037 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\Image.py:849(tobytes)
        5    0.033    0.007    0.033    0.007 {method 'astype' of 'numpy.ndarray' objects}
        1    0.000    0.000    0.032    0.032 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\ImageFile.py:291(load)
        1    0.029    0.029    0.031    0.031 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\stego\spreader.py:19(_to_grayscale_mask)
        2    0.000    0.000    0.030    0.015 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\numpy\_core\fromnumeric.py:48(_wrapfunc)
       93    0.029    0.000    0.029    0.000 {method 'decode' of 'ImagingDecoder' objects}
        1    0.000    0.000    0.021    0.021 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\numpy\_core\fromnumeric.py:437(repeat)
        1    0.021    0.021    0.021    0.021 {method 'repeat' of 'numpy.ndarray' objects}
       92    0.000    0.000    0.012    0.000 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\PngImagePlugin.py:1142(write)
       94    0.000    0.000    0.012    0.000 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\PngImagePlugin.py:1124(putchunk)
        1    0.000    0.000    0.009    0.009 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\numpy\_core\numeric.py:679(flatnonzero)
        1    0.000    0.000    0.009    0.009 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\numpy\_core\fromnumeric.py:1993(nonzero)
        1    0.009    0.009    0.009    0.009 {method 'nonzero' of 'numpy.ndarray' objects}
```

## 7. cProfile — top-30 in FULL Mode

One hide run on a 2MB PNG with SSIM. It should clearly show
`structural_similarity` and `uniform_filter` at the top.

```
         4570 function calls (4551 primitive calls) in 1.858 seconds

   Ordered by: cumulative time
   List reduced from 275 to 30 due to restriction <30>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.001    0.001    1.854    1.854 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\stego_service.py:59(hide_data)
        1    0.003    0.003    1.024    1.024 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\stego_service.py:362(_compute_metrics)
        1    0.000    0.000    0.957    0.957 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\analytics\metrics.py:67(calculate_ssim)
      4/1    0.478    0.120    0.957    0.957 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\skimage\metrics\_structural_similarity.py:15(structural_similarity)
       15    0.011    0.001    0.452    0.030 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\scipy\ndimage\_filters.py:1549(uniform_filter)
       30    0.000    0.000    0.440    0.015 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\scipy\ndimage\_filters.py:1498(uniform_filter1d)
       30    0.439    0.015    0.439    0.015 {built-in method scipy.ndimage._nd_image.uniform_filter1d}
        1    0.255    0.255    0.341    0.341 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\stego\spreader.py:66(generate_coords)
        1    0.001    0.001    0.230    0.230 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\formats\png.py:58(save)
        1    0.000    0.000    0.223    0.223 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\Image.py:2591(save)
        1    0.000    0.000    0.223    0.223 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\PngImagePlugin.py:1325(_save)
        1    0.000    0.000    0.223    0.223 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\ImageFile.py:644(_save)
        1    0.000    0.000    0.223    0.223 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\ImageFile.py:672(_encode_tile)
      187    0.214    0.001    0.214    0.001 {method 'encode' of 'ImagingEncoder' objects}
        1    0.000    0.000    0.208    0.208 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\crypto\engine.py:67(encrypt)
        1    0.000    0.000    0.208    0.208 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\crypto\key_manager.py:23(derive_key)
        1    0.208    0.208    0.208    0.208 {method 'derive' of 'cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC' objects}
        1    0.010    0.010    0.086    0.086 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\stego\spreader.py:30(_build_edge_pool)
        1    0.036    0.036    0.063    0.063 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\services\analytics\metrics.py:36(calculate_psnr)
       11    0.055    0.005    0.055    0.005 {method 'astype' of 'numpy.ndarray' objects}
        1    0.000    0.000    0.040    0.040 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\formats\png.py:30(load)
        6    0.002    0.000    0.039    0.007 {built-in method numpy.array}
        1    0.001    0.001    0.038    0.038 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\Image.py:811(__array_interface__)
        1    0.000    0.000    0.037    0.037 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\Image.py:849(tobytes)
        1    0.000    0.000    0.032    0.032 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\PIL\ImageFile.py:291(load)
        1    0.029    0.029    0.032    0.032 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\src\stegambit\core\stego\spreader.py:19(_to_grayscale_mask)
        2    0.000    0.000    0.030    0.015 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\numpy\_core\fromnumeric.py:48(_wrapfunc)
       93    0.029    0.000    0.029    0.000 {method 'decode' of 'ImagingDecoder' objects}
        1    0.000    0.000    0.021    0.021 D:\рефераты\УчебаМага\KursovikStegMoved\SteGambit\SteGambit\.venv\Lib\site-packages\numpy\_core\fromnumeric.py:437(repeat)
        1    0.021    0.021    0.021    0.021 {method 'repeat' of 'numpy.ndarray' objects}
```

## 8. Conclusions

_(filled in manually after the tables are analyzed)_
