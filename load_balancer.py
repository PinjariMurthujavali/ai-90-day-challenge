"""
DAY 42: Service Discovery & Load Balancing
==============================================
Extends Day 41's ServiceRegistry (single URL per service name) into a
LoadBalancedRegistry: multiple INSTANCES can register under the same
service name, and callers get routed across them using real load
balancing strategies — the same core idea behind Kubernetes Services,
AWS ELB, and nginx upstream blocks, simplified to fit in one file.

Strategies implemented:
  - Round Robin      — cycle through instances evenly
  - Least Connections — send to whichever instance has the fewest active calls
  - Random            — pick a healthy instance at random
  - Weighted          — bias towards instances with higher declared capacity

Run tests:
    pytest test_load_balancer.py -v
"""

import random
import time
import threading
from collections import defaultdict


class ServiceInstance:
    """One running copy of a service (e.g. analytics-service replica #2)."""

    def __init__(self, url, weight=1):
        self.url = url
        self.weight = weight
        self.active_connections = 0
        self.total_requests = 0
        self.last_heartbeat = time.time()
        self.healthy = True

    def is_healthy(self, timeout=30):
        return self.healthy and (time.time() - self.last_heartbeat) <= timeout

    def __repr__(self):
        return f"<Instance {self.url} conns={self.active_connections} healthy={self.healthy}>"


class LoadBalancedRegistry:
    """
    Service discovery + load balancing combined: services register multiple
    instances under one name, and `get_instance()` picks the "next" one
    according to the chosen strategy.
    """

    def __init__(self, strategy="round_robin"):
        self.strategy = strategy
        self._instances = defaultdict(list)  # service_name -> [ServiceInstance, ...]
        self._rr_counters = defaultdict(int)  # service_name -> next round-robin index
        self._lock = threading.Lock()

    # ---------------- Registration ----------------

    def register(self, service_name, url, weight=1):
        with self._lock:
            existing = self._find(service_name, url)
            if existing:
                existing.healthy = True
                existing.last_heartbeat = time.time()
                return existing
            instance = ServiceInstance(url, weight=weight)
            self._instances[service_name].append(instance)
            return instance

    def deregister(self, service_name, url):
        with self._lock:
            self._instances[service_name] = [
                i for i in self._instances[service_name] if i.url != url
            ]

    def heartbeat(self, service_name, url):
        with self._lock:
            inst = self._find(service_name, url)
            if inst:
                inst.last_heartbeat = time.time()
                inst.healthy = True
                return True
            return False

    def mark_unhealthy(self, service_name, url):
        with self._lock:
            inst = self._find(service_name, url)
            if inst:
                inst.healthy = False

    def _find(self, service_name, url):
        for inst in self._instances[service_name]:
            if inst.url == url:
                return inst
        return None

    def _healthy_instances(self, service_name):
        return [i for i in self._instances[service_name] if i.is_healthy()]

    # ---------------- Load-balanced selection ----------------

    def get_instance(self, service_name, strategy=None):
        """Return the URL of the instance to route this call to, per strategy."""
        strategy = strategy or self.strategy
        with self._lock:
            healthy = self._healthy_instances(service_name)
            if not healthy:
                return None

            if strategy == "round_robin":
                idx = self._rr_counters[service_name] % len(healthy)
                self._rr_counters[service_name] += 1
                chosen = healthy[idx]

            elif strategy == "least_connections":
                chosen = min(healthy, key=lambda i: i.active_connections)

            elif strategy == "random":
                chosen = random.choice(healthy)

            elif strategy == "weighted":
                pool = []
                for inst in healthy:
                    pool.extend([inst] * max(1, inst.weight))
                chosen = random.choice(pool)

            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            chosen.total_requests += 1
            return chosen.url

    # ---------------- Connection tracking (for least-connections + observability) ----------------

    def start_call(self, service_name, url):
        inst = self._find(service_name, url)
        if inst:
            inst.active_connections += 1

    def end_call(self, service_name, url):
        inst = self._find(service_name, url)
        if inst and inst.active_connections > 0:
            inst.active_connections -= 1

    def call_with_tracking(self, service_name, strategy=None):
        """Context-manager-style helper: pick an instance and auto-track its load."""
        url = self.get_instance(service_name, strategy=strategy)
        if not url:
            return None
        self.start_call(service_name, url)
        return _TrackedCall(self, service_name, url)

    # ---------------- Observability ----------------

    def status(self, service_name):
        return [
            {
                "url": i.url,
                "healthy": i.is_healthy(),
                "active_connections": i.active_connections,
                "total_requests": i.total_requests,
                "weight": i.weight,
            }
            for i in self._instances[service_name]
        ]


class _TrackedCall:
    """Lets callers do: `with registry.call_with_tracking('svc') as url: requests.get(url)`
    and have active_connections auto-decrement when the call finishes."""

    def __init__(self, registry, service_name, url):
        self.registry = registry
        self.service_name = service_name
        self.url = url

    def __enter__(self):
        return self.url

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.registry.end_call(self.service_name, self.url)
        return False


# ---------------- DEMO ----------------

def demo():
    registry = LoadBalancedRegistry(strategy="round_robin")

    registry.register("analytics-service", "http://10.0.0.1:5001", weight=1)
    registry.register("analytics-service", "http://10.0.0.2:5001", weight=2)
    registry.register("analytics-service", "http://10.0.0.3:5001", weight=1)

    print("=== Round Robin (10 calls) ===")
    for _ in range(10):
        print(" ->", registry.get_instance("analytics-service", strategy="round_robin"))

    print("\n=== Weighted (10 calls, .2 should get ~2x traffic) ===")
    from collections import Counter
    picks = Counter(
        registry.get_instance("analytics-service", strategy="weighted") for _ in range(1000)
    )
    for url, count in picks.items():
        print(f"   {url}: {count} calls")

    print("\n=== Simulated load, then least-connections ===")
    registry.start_call("analytics-service", "http://10.0.0.1:5001")
    registry.start_call("analytics-service", "http://10.0.0.1:5001")
    registry.start_call("analytics-service", "http://10.0.0.2:5001")
    print("Status:", registry.status("analytics-service"))
    print("Least-loaded pick:", registry.get_instance("analytics-service", strategy="least_connections"))


if __name__ == "__main__":
    demo()
