"""
若茗 PaaS - 服务监控服务
基于 psutil 采集系统指标：CPU / 内存 / 磁盘 / 网络
Author: ruoming
"""
import platform
import time
from datetime import datetime, timezone

import psutil


class ServerMonitorService:
    """服务器监控数据采集"""

    @staticmethod
    def get_system_info() -> dict:
        """获取系统基础信息（一次性，不需要频繁刷新）"""
        boot_ts = psutil.boot_time()
        boot_dt = datetime.fromtimestamp(boot_ts, tz=timezone.utc)
        uptime_seconds = int(time.time() - boot_ts)

        h, remainder = divmod(uptime_seconds, 3600)
        m, s = divmod(remainder, 60)
        uptime_str = f"{h}小时{m}分{s}秒"

        uname = platform.uname()
        return {
            "hostname": uname.node,
            "os": f"{uname.system} {uname.release}",
            "arch": uname.machine,
            "kernel": uname.version[:64] if uname.version else None,
            "cpu_brand": _get_cpu_brand(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "boot_time": boot_dt.isoformat(),
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
        }

    @staticmethod
    def get_metrics() -> dict:
        """获取实时性能指标（CPU / 内存 / Swap / 磁盘）"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.2)
        cpu_freq = psutil.cpu_freq()
        load_avg = list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else [0, 0, 0]

        # 内存
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # 磁盘（所有挂载点）
        disk_partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_partitions.append({
                    "device": part.device,
                    "mount": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                continue

        return {
            "cpu": {
                "percent": cpu_percent,
                "count_logical": psutil.cpu_count(logical=True),
                "count_physical": psutil.cpu_count(logical=False),
                "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
                "load_avg_1m": round(load_avg[0], 2),
                "load_avg_5m": round(load_avg[1], 2),
                "load_avg_15m": round(load_avg[2], 2),
            },
            "memory": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "percent": mem.percent,
            },
            "swap": {
                "total_gb": round(swap.total / (1024 ** 3), 2),
                "used_gb": round(swap.used / (1024 ** 3), 2),
                "percent": swap.percent,
            },
            "disk": disk_partitions,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    @staticmethod
    def get_network(iface: str | None = None) -> dict:
        """获取网络接口列表及流量统计"""
        counters = psutil.net_io_counters(pernic=True)
        interfaces = [k for k in counters if not k.startswith("lo")]

        stats = {}
        for name, c in counters.items():
            if name.startswith("lo"):
                continue
            stats[name] = {
                "bytes_sent": c.bytes_sent,
                "bytes_recv": c.bytes_recv,
                "packets_sent": c.packets_sent,
                "packets_recv": c.packets_recv,
                "errin": c.errin,
                "errout": c.errout,
            }

        return {
            "interfaces": interfaces,
            "stats": stats,
            "selected": iface if iface and iface in stats else (interfaces[0] if interfaces else None),
        }


def _get_cpu_brand() -> str:
    """尝试读取 CPU 品牌名称"""
    try:
        import subprocess
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown"
