"""Micro-benchmark of edge detection in SmartSpreader to confirm
the hypothesis from task #25.2.

Checks:
1. What percent of samples land in the edge pool for WAV vs PNG.
2. How long _build_edge_pool takes separately for each format.
3. Whether edge detection for WAV is worth it at all (in practice it is a no-op
   if it filters out <5% of samples).

The report is written to tests/scripts/baseline_wav.md so it does not overwrite
the main baseline.md from 25.1.

Run from the project root:
    python tests/scripts/profile_edge_pool.py
"""
from __future__ import annotations

import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import wavfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stegambit.core.formats.png import PngFormat  # noqa: E402
from stegambit.core.formats.wav import WavFormat  # noqa: E402
from stegambit.core.formats.jpeg import JpegFormat  # noqa: E402
from stegambit.core.stego.spreader import SmartSpreader  # noqa: E402


N_ITERATIONS = 20  # more runs of _build_edge_pool; the operation is cheap.
ARTIFACTS = PROJECT_ROOT / "tests" / "artifacts"
REPORT_PATH = Path(__file__).resolve().parent / "baseline_wav.md"


# === Synthetic carrier generation ===
def make_noise_png(path: Path, target_kb: int = 2048) -> None:
    target_bytes = target_kb * 1024
    side = int((target_bytes / 1.05) ** 0.5)
    rng = np.random.default_rng(seed=42)
    arr = rng.integers(0, 256, size=(side, side, 3), dtype=np.uint8)
    Image.fromarray(arr, mode="RGB").save(path, format="PNG", compress_level=6)


def make_noise_wav(path: Path, duration_sec: float = 20.0, sr: int = 44100) -> None:
    rng = np.random.default_rng(seed=42)
    samples = rng.integers(-30000, 30000, size=int(sr * duration_sec), dtype=np.int16)
    wavfile.write(path, sr, samples)


def make_quiet_wav(path: Path, duration_sec: float = 20.0, sr: int = 44100) -> None:
    """A quiet sine — the worst case for the hypothesis (little noise -> a small
    gradient -> something may actually get filtered). Control case.
    """
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # Quiet (amplitude ~500) 440 Hz sine plus a little white noise.
    rng = np.random.default_rng(seed=42)
    samples = (500 * np.sin(2 * np.pi * 440 * t)
               + rng.integers(-10, 10, size=t.size)).astype(np.int16)
    wavfile.write(path, sr, samples)


# === Measurements ===
def measure_edge_pool(container: np.ndarray, n: int = N_ITERATIONS) -> dict:
    """Measures the percent of filtered positions and the time of _build_edge_pool."""
    spreader = SmartSpreader()
    total = container.size

    # One run for the rejection-percentage statistic.
    pool = spreader._build_edge_pool(container)
    pool_size = int(pool.size)
    pct_in = pool_size / total * 100.0 if total > 0 else 0.0
    pct_filtered_out = 100.0 - pct_in

    # N runs to measure time.
    times_ms: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        spreader._build_edge_pool(container)
        times_ms.append((time.perf_counter() - t0) * 1000.0)

    return {
        "total_positions": total,
        "pool_size": pool_size,
        "pct_in_pool": pct_in,
        "pct_filtered_out": pct_filtered_out,
        "time_median_ms": statistics.median(times_ms),
        "time_min_ms": min(times_ms),
        "time_max_ms": max(times_ms),
    }


# === Report ===
def render_report(env: dict, results: list[dict]) -> str:
    lines = [
        "# Edge-detection Analysis для WAV (Подтаска #25.2)",
        "",
        f"**Дата прогона:** {env['timestamp']}",
        "",
        "## 1. Цель",
        "",
        "Проверить гипотезу из ТЗ #25:",
        "> Для аудио (1D-массив WAV), edge-detection считает разность",
        "> между соседними сэмплами. Порог `GRADIENT_THRESHOLD = 8` на",
        "> шкале -32768..+32767 ничего не фильтрует -> почти все сэмплы",
        "> попадают в пул, edge-detection становится no-op.",
        "",
        "## 2. Методология",
        "",
        f"- **Платформа:** {env['platform']}",
        f"- **Python:** {env['python']}",
        f"- **Итераций для замера времени:** {N_ITERATIONS}",
        f"- **GRADIENT_THRESHOLD:** {SmartSpreader.GRADIENT_THRESHOLD}",
        "- **Метрики:**",
        "  - `pool_size / total` — какой процент позиций прошёл фильтр.",
        "  - Если > 95% — фильтр практически не работает (гипотеза подтверждена).",
        "  - Если < 50% — фильтр осмыслен.",
        "  - Время `_build_edge_pool` — стоимость 'no-op' фильтрации.",
        "",
        "## 3. Результаты",
        "",
        "| Носитель | Total positions | В пуле | % в пуле | % отфильтровано | time median (ms) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} "
            f"| {r['total_positions']:,} "
            f"| {r['pool_size']:,} "
            f"| {r['pct_in_pool']:.2f}% "
            f"| {r['pct_filtered_out']:.2f}% "
            f"| {r['time_median_ms']:.2f} |"
        )

    # Automatic verdict on the hypothesis.
    wav_results = [r for r in results if "WAV" in r["name"]]
    png_results = [r for r in results if "PNG" in r["name"]]

    lines += [
        "",
        "## 4. Вердикт по гипотезе",
        "",
    ]

    if wav_results:
        wav_pct = statistics.mean(r["pct_in_pool"] for r in wav_results)
        lines.append(f"**WAV: средний % в пуле = {wav_pct:.2f}%**")
        if wav_pct > 95.0:
            lines.append("- ❌ Edge-detection для WAV — **no-op** (фильтрует <5%).")
            lines.append("- 🔧 **Рекомендация:** отключить edge-detection для 1D-аудио")
            lines.append("  ИЛИ повысить порог до значения, осмысленного на шкале int16")
            lines.append("  (например, 256 = 1% от полного диапазона).")
        elif wav_pct > 70.0:
            lines.append("- ⚠️ Edge-detection для WAV — слабая фильтрация.")
            lines.append("- 🔧 **Рекомендация:** поднять порог.")
        else:
            lines.append("- ✅ Edge-detection для WAV работает осмысленно.")
            lines.append("- Гипотеза из ТЗ не подтвердилась.")

    lines.append("")

    if png_results:
        png_pct = statistics.mean(r["pct_in_pool"] for r in png_results)
        lines.append(f"**PNG (контроль): средний % в пуле = {png_pct:.2f}%**")
        if png_pct < 95.0:
            lines.append("- ✅ Для изображений фильтр работает (контроль OK).")
        else:
            lines.append("- ❌ Даже на PNG фильтр пропускает >95% — проблема глубже.")

    lines += [
        "",
        "## 5. Стоимость no-op (если гипотеза подтверждена)",
        "",
        "Время `_build_edge_pool` для WAV показывает, сколько секунд",
        "тратится на бессмысленную фильтрацию. Если оно небольшое",
        "относительно полного hide_data (~260 ms для WAV), оптимизация",
        "имеет малый приоритет.",
        "",
        "## 6. Выводы",
        "",
        "_(заполняется вручную после анализа таблицы)_",
        "",
    ]
    return "\n".join(lines)


# === Main ===
def main() -> None:
    print(">>> Подготовка артефактов...")

    with tempfile.TemporaryDirectory(prefix="edge_") as tmp_str:
        tmp = Path(tmp_str)
        png_2mb = tmp / "noise_2mb.png"
        wav_noise = tmp / "noise_wav.wav"
        wav_quiet = tmp / "quiet_wav.wav"

        print("    Генерирую PNG 2MB из шума...")
        make_noise_png(png_2mb)
        print("    Генерирую WAV (белый шум, амплитуда ~30k)...")
        make_noise_wav(wav_noise)
        print("    Генерирую WAV (тихая синусоида, амплитуда ~500)...")
        make_quiet_wav(wav_quiet)

        jpeg_real = ARTIFACTS / "carriers" / "photo.jpg"

        # Load each one through its format handler -> ndarray.
        png_arr = PngFormat().load(png_2mb)
        wav_noise_arr = WavFormat().load(wav_noise)
        wav_quiet_arr = WavFormat().load(wav_quiet)

        # A PNG from a real photo, for contrast with the synthetic data.
        # Take photo.jpg and decode it to an RGB ndarray by hand so we do
        # not depend on the JPEG pipeline (that yields a DCT container, not an ndarray).
        photo_arr = np.array(Image.open(jpeg_real).convert("RGB"), dtype=np.uint8)

        cases = [
            ("PNG 2MB (synthetic noise)", png_arr),
            ("PNG photo.jpg (decoded to RGB)", photo_arr),
            ("WAV (white noise, amp~30k)", wav_noise_arr),
            ("WAV (quiet sine, amp~500)", wav_quiet_arr),
        ]

        print(">>> Замеры edge-pool...")
        results = []
        for name, arr in cases:
            print(f"    {name}: shape={arr.shape}, dtype={arr.dtype}")
            r = measure_edge_pool(arr)
            r["name"] = name
            results.append(r)
            print(f"      -> в пуле {r['pct_in_pool']:.2f}%, "
                  f"отфильтровано {r['pct_filtered_out']:.2f}%, "
                  f"time median={r['time_median_ms']:.2f}ms")

        import platform
        env = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
        }

        report = render_report(env, results)
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f">>> Отчёт записан: {REPORT_PATH}")


if __name__ == "__main__":
    main()