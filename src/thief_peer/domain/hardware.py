"""Best-effort hardware/platform probing for the Step-0 declaration (Phase 5).

Every probe is wrapped so a value that cannot be genuinely determined becomes
``None`` plus an explanatory ``status`` string -- NEVER a fabricated value. GPU/
VRAM is intentionally always ``None`` + status on a typical dev machine (no
reliable cross-platform probe), which is the correct, honest result.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HardwareInfo:
    """A snapshot of this machine, with per-field availability status.

    Field set frozen against `docs/schemas/declaration.schema.json`
    (session recovery step C, resolving risk #14) -- byte-identical to the
    Police repo's `HardwareInfo`, including the explicit `gpu_available`
    flag and `vram_status`, which this dataclass previously lacked.
    """

    operating_system: str
    platform_detail: str
    python_version: str
    cpu_model: str | None
    cpu_model_status: str
    cpu_cores: int | None
    ram_gb: float | None
    ram_status: str
    gpu_model: str | None
    gpu_available: bool
    gpu_status: str
    vram_gb: float | None
    vram_status: str


def _probe_cpu_model() -> tuple[str | None, str]:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip(), "ok"
        elif system == "Linux":
            for line in _read_cpuinfo():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip(), "ok"
        processor = platform.processor()
        if processor:
            return processor, "ok (platform.processor fallback)"
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, "unavailable: cpu probe raised"
    return None, "unavailable on this platform"


def _read_cpuinfo() -> list[str]:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            return fh.readlines()
    except OSError:
        return []


def _probe_ram_gb() -> tuple[float | None, str]:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        phys_pages = os.sysconf("SC_PHYS_PAGES")
        gb = (page_size * phys_pages) / (1024**3)
        return round(gb, 2), "ok (os.sysconf)"
    except (ValueError, OSError, AttributeError):
        return None, "unavailable: no os.sysconf RAM query on this platform"


def probe_hardware() -> HardwareInfo:
    """Gather a full, honest hardware snapshot for the declaration."""
    cpu_model, cpu_status = _probe_cpu_model()
    ram_gb, ram_status = _probe_ram_gb()
    return HardwareInfo(
        operating_system=platform.system() or "unknown",
        platform_detail=platform.platform(),
        python_version=sys.version.split()[0],
        cpu_cores=os.cpu_count(),
        cpu_model=cpu_model,
        cpu_model_status=cpu_status,
        ram_gb=ram_gb,
        ram_status=ram_status,
        gpu_model=None,
        gpu_available=False,
        gpu_status="unavailable: no reliable cross-platform GPU/VRAM probe",
        vram_gb=None,
        vram_status="unavailable: no reliable cross-platform GPU/VRAM probe",
    )
