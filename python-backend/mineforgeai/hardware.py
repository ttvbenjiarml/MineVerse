from __future__ import annotations

import os
import platform
import re
from ctypes import Structure, byref, c_ulong, c_ulonglong, sizeof, windll
from dataclasses import dataclass


@dataclass(slots=True)
class HardwareProfile:
    device: str
    preset: str
    precision: str
    gpu_memory_gb: float = 0.0
    performance_tier: str = "low"
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    total_virtual_memory_gb: float = 0.0
    available_virtual_memory_gb: float = 0.0
    virtual_memory_enabled: bool = False


class _MemoryStatusEx(Structure):
    _fields_ = [
        ("dwLength", c_ulong),
        ("dwMemoryLoad", c_ulong),
        ("ullTotalPhys", c_ulonglong),
        ("ullAvailPhys", c_ulonglong),
        ("ullTotalPageFile", c_ulonglong),
        ("ullAvailPageFile", c_ulonglong),
        ("ullTotalVirtual", c_ulonglong),
        ("ullAvailVirtual", c_ulonglong),
        ("ullAvailExtendedVirtual", c_ulonglong),
    ]


def _bytes_to_gb(value: int) -> float:
    return round(value / (1024 ** 3), 2)


def _detect_memory() -> dict:
    system = platform.system()
    result = {
        "total_ram_gb": 0.0,
        "available_ram_gb": 0.0,
        "total_virtual_memory_gb": 0.0,
        "available_virtual_memory_gb": 0.0,
        "virtual_memory_enabled": False,
    }

    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        result.update(
            {
                "total_ram_gb": _bytes_to_gb(int(vm.total)),
                "available_ram_gb": _bytes_to_gb(int(vm.available)),
                "total_virtual_memory_gb": _bytes_to_gb(int(vm.total + swap.total)),
                "available_virtual_memory_gb": _bytes_to_gb(int(vm.available + swap.free)),
                "virtual_memory_enabled": bool(swap.total > 0),
            }
        )
        return result
    except Exception:
        pass

    if system == "Windows":
        try:
            status = _MemoryStatusEx()
            status.dwLength = sizeof(_MemoryStatusEx)
            windll.kernel32.GlobalMemoryStatusEx(byref(status))
            result.update(
                {
                    "total_ram_gb": _bytes_to_gb(int(status.ullTotalPhys)),
                    "available_ram_gb": _bytes_to_gb(int(status.ullAvailPhys)),
                    "total_virtual_memory_gb": _bytes_to_gb(int(status.ullTotalPageFile)),
                    "available_virtual_memory_gb": _bytes_to_gb(int(status.ullAvailPageFile)),
                    "virtual_memory_enabled": bool(status.ullTotalPageFile > status.ullTotalPhys),
                }
            )
            return result
        except Exception:
            return result

    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_pages = os.sysconf("SC_PHYS_PAGES")
        avail_pages = os.sysconf("SC_AVPHYS_PAGES")
        result["total_ram_gb"] = _bytes_to_gb(int(page_size * total_pages))
        result["available_ram_gb"] = _bytes_to_gb(int(page_size * avail_pages))
    except Exception:
        pass

    if os.path.exists("/proc/meminfo"):
        try:
            text = open("/proc/meminfo", "r", encoding="utf-8").read()
            total_swap = re.search(r"SwapTotal:\s+(\d+)\s+kB", text)
            free_swap = re.search(r"SwapFree:\s+(\d+)\s+kB", text)
            total_swap_kb = int(total_swap.group(1)) if total_swap else 0
            free_swap_kb = int(free_swap.group(1)) if free_swap else 0
            result["total_virtual_memory_gb"] = round(result["total_ram_gb"] + (total_swap_kb / (1024 ** 2)), 2)
            result["available_virtual_memory_gb"] = round(result["available_ram_gb"] + (free_swap_kb / (1024 ** 2)), 2)
            result["virtual_memory_enabled"] = total_swap_kb > 0
        except Exception:
            pass
    return result


def recommended_virtual_context_window(profile: HardwareProfile) -> int:
    if profile.performance_tier in {"high", "enthusiast"} and profile.available_virtual_memory_gb >= 32:
        return 262144
    if profile.available_virtual_memory_gb >= 12:
        return 131072
    if profile.available_virtual_memory_gb >= 6:
        return 65536
    return 32768


def detect_hardware() -> HardwareProfile:
    memory = _detect_memory()
    try:
        import torch  # type: ignore
    except Exception:
        return HardwareProfile(device="cpu", preset="tiny", precision="int8_dynamic", performance_tier="low", **memory)

    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return HardwareProfile(device="mps", preset="small", precision="float16", performance_tier="mid", **memory)
    if torch.cuda.is_available():
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if total_gb >= 24:
            return HardwareProfile(device="cuda", preset="large_local", precision="bfloat16", gpu_memory_gb=total_gb, performance_tier="enthusiast", **memory)
        if total_gb >= 10:
            return HardwareProfile(device="cuda", preset="medium", precision="float16", gpu_memory_gb=total_gb, performance_tier="high", **memory)
        return HardwareProfile(device="cuda", preset="small", precision="float16", gpu_memory_gb=total_gb, performance_tier="mid", **memory)
    return HardwareProfile(device="cpu", preset="tiny", precision="int8_dynamic", performance_tier="low", **memory)
