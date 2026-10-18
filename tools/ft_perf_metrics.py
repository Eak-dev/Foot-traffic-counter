"""Pure unit-checked resource summaries; CPU is not total machine energy."""
import math


def summarize_resource(wall_seconds, user_seconds, system_seconds, peak_rss_bytes, logical_cpus):
    values = (wall_seconds, user_seconds, system_seconds, peak_rss_bytes)
    if (any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
            or wall_seconds <= 0 or min(values[1:]) < 0
            or type(logical_cpus) is not int or logical_cpus <= 0):
        raise ValueError('invalid resource measurement')
    cpu = user_seconds + system_seconds
    return dict(wall_seconds=round(wall_seconds, 6), cpu_core_seconds=round(cpu, 6),
                average_cpu_percent=round(100 * cpu / wall_seconds, 3),
                logical_capacity_fraction=round(cpu / wall_seconds / logical_cpus, 6),
                peak_worker_mib=round(peak_rss_bytes / 1024**2, 3),
                cpu_percent_basis='100_percent_equals_one_logical_cpu',
                gpu_energy_temperature='NOT_MEASURED')
