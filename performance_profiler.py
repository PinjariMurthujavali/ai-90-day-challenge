"""
DAY 33: Performance Profiling & Benchmarking
================================================
- Function-level profiler (call count, total/avg/min/max time)
- Line-level bottleneck detection via cProfile wrapper
- Benchmark comparator (compare 2+ implementations head-to-head)
- Memory usage tracking
- Auto-generated performance report
"""

import time
import cProfile
import pstats
import io
import tracemalloc
import functools
import statistics
from collections import defaultdict


# ---------------- FUNCTION-LEVEL PROFILER ----------------

class Profiler:
    """Tracks call count + timing stats per function across the whole app."""

    def __init__(self):
        self.records = defaultdict(list)  # func_name -> [elapsed_ms, ...]

    def track(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.records[func.__qualname__].append(elapsed_ms)
            return result
        return wrapper

    def report(self):
        rows = []
        for name, times in self.records.items():
            rows.append({
                "function": name,
                "calls": len(times),
                "total_ms": round(sum(times), 3),
                "avg_ms": round(statistics.mean(times), 3),
                "min_ms": round(min(times), 3),
                "max_ms": round(max(times), 3),
            })
        return sorted(rows, key=lambda r: r["total_ms"], reverse=True)

    def print_report(self):
        rows = self.report()
        print(f"{'Function':<30}{'Calls':>8}{'Total(ms)':>12}{'Avg(ms)':>10}{'Min(ms)':>10}{'Max(ms)':>10}")
        print("-" * 80)
        for r in rows:
            print(f"{r['function']:<30}{r['calls']:>8}{r['total_ms']:>12}{r['avg_ms']:>10}{r['min_ms']:>10}{r['max_ms']:>10}")


profiler = Profiler()


# ---------------- LINE-LEVEL BOTTLENECK DETECTION (cProfile wrapper) ----------------

def profile_deep(func, *args, top_n=8, **kwargs):
    """Run cProfile on a function call, return top N slowest internal calls."""
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args, **kwargs)
    pr.disable()

    stream = io.StringIO()
    stats = pstats.Stats(pr, stream=stream).sort_stats("cumulative")
    stats.print_stats(top_n)
    return result, stream.getvalue()


# ---------------- MEMORY TRACKING ----------------

def track_memory(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracemalloc.start()
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(f"🧠 {func.__name__}: current={current/1024:.1f}KB, peak={peak/1024:.1f}KB")
        return result
    return wrapper


# ---------------- BENCHMARK COMPARATOR ----------------

def benchmark_compare(implementations: dict, iterations=1000, *args, **kwargs):
    """
    Compare multiple implementations of the same logic head-to-head.
    implementations = {"name": func, ...}
    """
    results = {}
    for name, func in implementations.items():
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            times.append((time.perf_counter() - start) * 1000)
        results[name] = {
            "total_ms": round(sum(times), 3),
            "avg_ms": round(statistics.mean(times), 5),
            "median_ms": round(statistics.median(times), 5),
        }

    fastest = min(results.items(), key=lambda x: x[1]["avg_ms"])
    print(f"\n🏁 Benchmark ({iterations} iterations each):")
    for name, stats_ in results.items():
        marker = "🏆" if name == fastest[0] else "  "
        speedup = "" if name == fastest[0] else f"  ({stats_['avg_ms']/fastest[1]['avg_ms']:.1f}x slower)"
        print(f"   {marker} {name}: avg={stats_['avg_ms']}ms, median={stats_['median_ms']}ms{speedup}")
    return results


# ---------------- DEMO: compare 2 implementations of the same task ----------------

@profiler.track
def search_linear(data, target):
    for item in data:
        if item == target:
            return True
    return False


@profiler.track
def search_set(data_set, target):
    return target in data_set


@track_memory
def build_large_list(n=100000):
    return [i * 2 for i in range(n)]


def demo():
    print("=" * 50)
    print("DAY 33: PERFORMANCE PROFILING & BENCHMARKING")
    print("=" * 50)

    data = list(range(10000))
    data_set = set(data)
    target = 9999

    print("\n📊 Running tracked functions a few times...")
    for _ in range(5):
        search_linear(data, target)
        search_set(data_set, target)

    print("\n📋 Function-level profiler report:")
    profiler.print_report()

    print("\n🧠 Memory tracking:")
    build_large_list(100000)

    benchmark_compare(
        {"list_search (O(n))": lambda: search_linear.__wrapped__(data, target),
         "set_search (O(1))": lambda: search_set.__wrapped__(data_set, target)},
        iterations=2000,
    )


if __name__ == "__main__":
    demo()
