"""
What it does:
1. Generates synthetic 2MB carriers (PNG/WAV from noise) in a temporary folder.
2. Runs hide + extract for N iterations for each carrier×payload combination.
3. Measures wall time via perf_counter (median / P95 / min / max).
4. One representative run under cProfile -> top-30 hottest functions.
5. Checks the SLA: hide of a 2MB PNG <= 1000ms.
6. Writes the result to docs/profiling/baseline.md.

Run from the project root:
    python scripts/profile_pipeline.py
"""
from __future__ import annotations

import cProfile
import io
import os
import platform
import pstats
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

from stegambit.models.dto import StegoTaskRequest  # noqa: E402
from stegambit.services.stego_service import StegoService  # noqa: E402


# === Configuration ===
N_ITERATIONS = 10              # Runs per combination for statistics.
SLA_HIDE_2MB_PNG_MS = 1000.0   # SLA threshold.
ARTIFACTS = PROJECT_ROOT / "tests" / "artifacts"
REPORT_PATH = Path(__file__).resolve().parent / "baseline.md"


# === Synthetic carrier generation ===
def make_noise_png(path: Path, target_kb: int = 2048) -> None:
    """Creates a PNG from RGB noise of a given size (~target_kb after compression).

    The noise is chosen so PNG deflate cannot compress it.
    The size is picked iteratively from the side of the square.
    """
    # Empirically: ~1.05 bytes per pixel for random RGB after PNG compression.
    target_bytes = target_kb * 1024
    side = int((target_bytes / 1.05) ** 0.5)
    rng = np.random.default_rng(seed=42)
    arr = rng.integers(0, 256, size=(side, side, 3), dtype=np.uint8)
    Image.fromarray(arr, mode="RGB").save(path, format="PNG", compress_level=6)


def make_noise_wav(path: Path, duration_sec: float = 20.0, sr: int = 44100) -> None:
    """Creates a mono int16 WAV from white noise."""
    rng = np.random.default_rng(seed=42)
    samples = rng.integers(-30000, 30000, size=int(sr * duration_sec), dtype=np.int16)
    wavfile.write(path, sr, samples)


# === Measurements ===
def time_operation(fn, *args, **kwargs) -> float:
    """Times a single call of fn in milliseconds."""
    t0 = time.perf_counter()
    fn(*args, **kwargs)
    return (time.perf_counter() - t0) * 1000.0


def benchmark(service: StegoService, carrier: Path, payload: Path,
              workdir: Path, n: int = N_ITERATIONS,
              compute_visual_metrics: bool = False) -> dict:
    """Runs hide+extract n times and returns wall-time aggregates.

    Args:
        compute_visual_metrics: If True, hide_data computes SSIM (an expensive
            operation). Used to measure the accumulated overhead of the full
            analytics pipeline.
    """
    hide_times: list[float] = []
    extract_times: list[float] = []
    ext = carrier.suffix

    for i in range(n):
        stego_path = workdir / f"stego_{i}{ext}"
        extracted_path = workdir / f"extracted_{i}.bin"

        # Hide
        hide_ms = time_operation(service.hide_data, StegoTaskRequest(
            carrier_path=carrier,
            payload_path=payload,
            output_path=stego_path,
            password="bench_pwd",
            compute_visual_metrics=compute_visual_metrics,
        ))
        hide_times.append(hide_ms)

        # Extract (the flag does not matter here — SSIM is not computed during extract).
        ext_ms = time_operation(service.extract_data, StegoTaskRequest(
            carrier_path=stego_path,
            payload_path=stego_path,
            output_path=extracted_path,
            password="bench_pwd",
        ))
        extract_times.append(ext_ms)

    return {
        "hide": _aggregate(hide_times),
        "extract": _aggregate(extract_times),
    }


def _aggregate(samples: list[float]) -> dict:
    """median / P95 / min / max."""
    s = sorted(samples)
    return {
        "median": statistics.median(s),
        "p95": s[max(0, int(len(s) * 0.95) - 1)],
        "min": s[0],
        "max": s[-1],
    }


# === cProfile run ===
def profile_one_run(service: StegoService, carrier: Path, payload: Path,
                    workdir: Path, compute_visual_metrics: bool = False) -> str:
    """One hide run under cProfile; returns a formatted top-30."""
    stego_path = workdir / f"profiled_stego{carrier.suffix}"
    profiler = cProfile.Profile()

    profiler.enable()
    service.hide_data(StegoTaskRequest(
        carrier_path=carrier,
        payload_path=payload,
        output_path=stego_path,
        password="profile_pwd",
        compute_visual_metrics=compute_visual_metrics,
    ))
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(30)
    return stream.getvalue()


# === Report generation ===
def render_report(env: dict, scenarios_fast: list[dict], scenarios_full: list[dict],
                  cprofile_fast: str, cprofile_full: str,
                  sla_result: dict) -> str:
    """Builds a Markdown report with a before/after comparison."""

    def render_table(scenarios):
        rows = [
            "| Carrier | Carrier size | Payload | Payload size | Op | median (ms) | P95 (ms) | min (ms) | max (ms) |",
            "|---|---:|---|---:|---|---:|---:|---:|---:|",
        ]
        for sc in scenarios:
            for op in ("hide", "extract"):
                a = sc["agg"][op]
                rows.append(
                    f"| {sc['carrier_name']} | {sc['carrier_size_kb']:.1f} KB "
                    f"| {sc['payload_name']} | {sc['payload_size_kb']:.1f} KB "
                    f"| {op} | {a['median']:.1f} | {a['p95']:.1f} "
                    f"| {a['min']:.1f} | {a['max']:.1f} |"
                )
        return "\n".join(rows)

    # Hide delta for each scenario: full - fast.
    delta_rows = [
        "| Carrier | Payload | hide median (fast) | hide median (full) | overhead (ms) | overhead (%) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for sf, sl in zip(scenarios_fast, scenarios_full):
        m_fast = sf["agg"]["hide"]["median"]
        m_full = sl["agg"]["hide"]["median"]
        diff = m_full - m_fast
        pct = (diff / m_fast * 100.0) if m_fast > 0 else 0.0
        delta_rows.append(
            f"| {sf['carrier_name']} | {sf['payload_name']} "
            f"| {m_fast:.1f} | {m_full:.1f} | {diff:+.1f} | {pct:+.1f}% |"
        )

    lines = [
        "# Performance Baseline (Подтаска #25.1)",
        "",
        f"**Дата прогона:** {env['timestamp']}",
        "",
        "## 1. Методология",
        "",
        f"- **Платформа:** {env['platform']}",
        f"- **Python:** {env['python']}",
        f"- **CPU:** {env['cpu']}",
        f"- **Итераций на сценарий:** {N_ITERATIONS}",
        f"- **Агрегация:** median, P95, min, max (миллисекунды).",
        f"- **Носители:** PNG/WAV синтезируются из псевдошума (seed=42),",
        f"  JPEG — `tests/artifacts/carriers/photo.jpg`.",
        f"- **Payload'ы:** реальные файлы из `tests/artifacts/payloads/`.",
        f"- **Режимы:** FAST = `compute_visual_metrics=False` (production-",
        f"  путь, по умолчанию). FULL = `compute_visual_metrics=True`",
        f"  (опциональная аналитика для детальных отчётов в UI).",
        "",
        "## 2. Wall-time замеры — режим FAST (production)",
        "",
        "Этот режим используется при обычной работе пользователя. SSIM",
        "не считается, в `response.metrics` ключ `ssim` отсутствует.",
        "",
        render_table(scenarios_fast),
        "",
        "## 3. Wall-time замеры — режим FULL (с SSIM)",
        "",
        "Этот режим включается флагом из UI для детального отчёта качества.",
        "Дополнительные ~1.5s на 2MB PNG за счёт `skimage.structural_similarity`.",
        "",
        render_table(scenarios_full),
        "",
        "## 4. Сравнение режимов — overhead визуальных метрик",
        "",
        "Колонка `overhead` показывает, сколько добавляет SSIM-расчёт.",
        "",
        "\n".join(delta_rows),
        "",
        "## 5. SLA-проверка: hide 2MB PNG ≤ 1000 ms (режим FAST)",
        "",
        f"- **Сценарий:** {sla_result['scenario']}",
        f"- **Median:** {sla_result['median_ms']:.1f} ms",
        f"- **Порог:** {SLA_HIDE_2MB_PNG_MS:.0f} ms",
        f"- **Вердикт:** {'✅ PASS' if sla_result['passed'] else '❌ FAIL'}",
        "",
        "## 6. cProfile — top-30 в режиме FAST",
        "",
        "Один прогон hide на PNG 2MB без визуальных метрик.",
        "",
        "```",
        cprofile_fast.rstrip(),
        "```",
        "",
        "## 7. cProfile — top-30 в режиме FULL",
        "",
        "Один прогон hide на PNG 2MB со SSIM. Должен явно показывать",
        "`structural_similarity` и `uniform_filter` в топе.",
        "",
        "```",
        cprofile_full.rstrip(),
        "```",
        "",
        "## 8. Выводы",
        "",
        "_(заполняется вручную после анализа таблиц)_",
        "",
    ]
    return "\n".join(lines)


# === Main ===
def main() -> None:
    print(">>> Подготовка артефактов...")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="profile_") as tmp_str:
        tmp = Path(tmp_str)
        png_2mb = tmp / "noise_2mb.png"
        wav_1mb = tmp / "noise_1mb.wav"

        print("    Генерирую PNG 2MB из шума...")
        make_noise_png(png_2mb, target_kb=2048)
        print(f"    -> {png_2mb.stat().st_size / 1024:.1f} KB")

        print("    Генерирую WAV ~1MB из шума...")
        make_noise_wav(wav_1mb, duration_sec=20.0)
        print(f"    -> {wav_1mb.stat().st_size / 1024:.1f} KB")

        jpeg_real = ARTIFACTS / "carriers" / "photo.jpg"
        tiny = ARTIFACTS / "payloads" / "tiny.txt"
        payload_med = ARTIFACTS / "payloads" / "secret.pdf"
        payload_huge = ARTIFACTS / "payloads" / "huge.bin"

        for p in (jpeg_real, tiny, payload_med, payload_huge):
            if not p.exists():
                print(f"!!! Не найден артефакт: {p}", file=sys.stderr)
                sys.exit(1)

        service = StegoService()

        # Scenario matrix: which carrier×payload pairs to run.
        matrix = [
            (png_2mb,    "PNG 2MB (noise)", tiny, "tiny.txt"),
            (png_2mb,    "PNG 2MB (noise)", payload_med,  "secret.pdf"),
            (png_2mb,    "PNG 2MB (noise)", payload_huge, "huge.bin"),
            (wav_1mb,    "WAV 1MB (noise)", tiny, "tiny.txt"),
            (wav_1mb,    "WAV 1MB (noise)", payload_med,  "secret.pdf"),
            (jpeg_real,  "JPEG photo.jpg",  tiny, "tiny.txt"),
            (jpeg_real,  "JPEG photo.jpg",  payload_med,  "secret.pdf"),
        ]

        # Two runs: production mode (the default) and full-metrics
        # (compute_visual_metrics=True) — to compare SSIM overhead.
        scenarios_fast = []
        scenarios_full = []

        for carrier, c_name, payload, p_name in matrix:
            workdir_base = tmp / f"work_{c_name}_{p_name}".replace(" ", "_").replace("/", "_")

            # --- Run 1: production (without SSIM) ---
            print(f">>> [FAST] {c_name} <- {p_name} ({N_ITERATIONS} итераций)")
            workdir_fast = workdir_base.with_name(workdir_base.name + "_fast")
            workdir_fast.mkdir(exist_ok=True)
            agg_fast = benchmark(service, carrier, payload, workdir_fast,
                                 compute_visual_metrics=False)
            scenarios_fast.append({
                "carrier_name": c_name,
                "carrier_size_kb": carrier.stat().st_size / 1024,
                "payload_name": p_name,
                "payload_size_kb": payload.stat().st_size / 1024,
                "agg": agg_fast,
            })
            print(f"    hide median={agg_fast['hide']['median']:.1f}ms  "
                  f"extract median={agg_fast['extract']['median']:.1f}ms")

            # --- Run 2: full metrics (with SSIM) ---
            print(f">>> [FULL] {c_name} <- {p_name} ({N_ITERATIONS} итераций)")
            workdir_full = workdir_base.with_name(workdir_base.name + "_full")
            workdir_full.mkdir(exist_ok=True)
            agg_full = benchmark(service, carrier, payload, workdir_full,
                                 compute_visual_metrics=True)
            scenarios_full.append({
                "carrier_name": c_name,
                "carrier_size_kb": carrier.stat().st_size / 1024,
                "payload_name": p_name,
                "payload_size_kb": payload.stat().st_size / 1024,
                "agg": agg_full,
            })
            print(f"    hide median={agg_full['hide']['median']:.1f}ms  "
                  f"extract median={agg_full['extract']['median']:.1f}ms")

        # SLA check on a 2MB PNG plus a medium payload.
        sla_scenario = next(s for s in scenarios_fast
                            if "PNG 2MB" in s["carrier_name"]
                            and s["payload_name"] == "secret.pdf")
        sla_result = {
            "scenario": f"{sla_scenario['carrier_name']} <- {sla_scenario['payload_name']} (fast mode)",
            "median_ms": sla_scenario["agg"]["hide"]["median"],
            "passed": sla_scenario["agg"]["hide"]["median"] <= SLA_HIDE_2MB_PNG_MS,
        }

        # Two cProfile runs: production (fast) and full (with SSIM).
        # The comparison shows where time goes in each mode.
        print(">>> cProfile-прогон [FAST] на PNG 2MB...")
        profile_workdir_fast = tmp / "profile_work_fast"
        profile_workdir_fast.mkdir()
        cprofile_dump_fast = profile_one_run(
            service, png_2mb, payload_med, profile_workdir_fast,
            compute_visual_metrics=False,
        )

        print(">>> cProfile-прогон [FULL] на PNG 2MB...")
        profile_workdir_full = tmp / "profile_work_full"
        profile_workdir_full.mkdir()
        cprofile_dump_full = profile_one_run(
            service, png_2mb, payload_med, profile_workdir_full,
            compute_visual_metrics=True,
        )

        env = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cpu": platform.processor() or "unknown",
        }

        report = render_report(
            env, scenarios_fast, scenarios_full,
            cprofile_dump_fast, cprofile_dump_full, sla_result,
        )
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f">>> Отчёт записан: {REPORT_PATH}")


if __name__ == "__main__":
    main()