"""
DAY 47: Service Mesh (Istio Basics)
=======================================
Days 41-46 built real distributed-systems building blocks — a registry,
a load balancer, resilient inter-service calls, distributed tracing — but
every service had to explicitly call into that code itself. That's the
pre-service-mesh world.

A service mesh's actual innovation is moving all of that OUT of
application code and into a transparent "sidecar" that sits next to every
service and intercepts its traffic automatically. The service just makes
a normal call; the sidecar quietly adds retries, circuit breaking,
mTLS, tracing, and traffic routing around it — no code changes required
in the service itself. This is exactly what Istio's Envoy sidecars do.

This module simulates that sidecar layer in-process, reusing Day 44's
resilience client and Day 46's tracer under the hood — the same way a
real mesh reuses the same underlying primitives, just relocated.

New capability this file adds beyond Days 44/46: traffic splitting
(Istio VirtualService-style canary/weighted routing between service
versions) and simulated mutual TLS (Istio PeerAuthentication-style).

Run tests:
    pytest test_service_mesh.py -v
"""

import random
from inter_service_client import InterServiceClient, ServiceUnavailableError
from tracing_service import Tracer, TraceCollector


# ============================================
# SIMULATED mTLS (PeerAuthentication-style)
# ============================================

class CertificateStore:
    """
    In a real mesh, every sidecar gets an auto-rotated cert from the mesh's
    CA and refuses plaintext traffic from anything without one — that's
    mutual TLS. This simulates just the trust decision: does the caller
    present a cert issued by a service this mesh trusts?
    """

    def __init__(self):
        self._trusted_services = set()

    def issue_certificate(self, service_name):
        self._trusted_services.add(service_name)
        return f"cert::{service_name}"

    def verify(self, cert):
        if not cert or not cert.startswith("cert::"):
            return False
        service_name = cert.split("::", 1)[1]
        return service_name in self._trusted_services

    def revoke(self, service_name):
        self._trusted_services.discard(service_name)


# ============================================
# TRAFFIC SPLITTING (Istio VirtualService-style canary routing)
# ============================================

class TrafficPolicy:
    """
    Routes a percentage of traffic to different versions of the same
    service — e.g. 90% to v1 (stable), 10% to v2 (canary) — without the
    CALLER knowing multiple versions even exist. This is how safe rollouts
    work in a mesh: ship v2, watch the 10% slice, ramp up if it's healthy.
    """

    def __init__(self):
        self._splits = {}  # service_name -> [(version, weight), ...]

    def set_split(self, service_name, version_weights):
        total = sum(w for _, w in version_weights)
        if abs(total - 100) > 0.001:
            raise ValueError(f"Weights must sum to 100, got {total}")
        self._splits[service_name] = version_weights

    def pick_version(self, service_name):
        splits = self._splits.get(service_name)
        if not splits:
            return None
        roll = random.uniform(0, 100)
        cumulative = 0
        for version, weight in splits:
            cumulative += weight
            if roll <= cumulative:
                return version
        return splits[-1][0]  # floating-point safety net


# ============================================
# THE SIDECAR (ties mTLS + traffic splitting + resilience + tracing together)
# ============================================

class Sidecar:
    """
    Sits "next to" one service and intercepts every outbound call it
    makes. The service just calls `sidecar.call(...)` like a normal
    function — everything below is invisible to it, exactly like a real
    Envoy sidecar intercepting traffic transparently at the network layer.
    """

    def __init__(self, service_name, cert_store, traffic_policy,
                 tracer=None, resilience_client=None):
        self.service_name = service_name
        self.cert_store = cert_store
        self.traffic_policy = traffic_policy
        self.own_cert = cert_store.issue_certificate(service_name)
        self.tracer = tracer or Tracer(service_name)
        self.resilience_client = resilience_client or InterServiceClient()
        self.metrics = {"calls": 0, "mtls_rejections": 0, "canary_routed": 0}

    def call(self, target_service, operation, call_func, incoming_trace_headers=None):
        """
        The one method a service actually calls. Everything a real mesh
        sidecar does happens inside here, transparently:
          1. mTLS: verify we HAVE a valid cert to present (identity check)
          2. Traffic split: which version of target_service do we actually hit?
          3. Tracing: wrap the call in a span, propagate trace context
          4. Resilience: retries + circuit breaker around the real call
        """
        self.metrics["calls"] += 1

        # 1. mTLS identity check — this sidecar must have a cert the mesh trusts
        if not self.cert_store.verify(self.own_cert):
            self.metrics["mtls_rejections"] += 1
            raise PermissionError(f"mTLS rejected: '{self.service_name}' has no valid mesh certificate")

        # 2. Traffic splitting — pick which version of the target to route to
        version = self.traffic_policy.pick_version(target_service)
        if version:
            self.metrics["canary_routed"] += 1

        # 3 + 4. Trace the call, and run it through the resilience client
        with self.tracer.span_context(f"call:{target_service}.{operation}", incoming_trace_headers) as span:
            span.set_tag("mesh.target_service", target_service)
            span.set_tag("mesh.target_version", version or "default")
            span.set_tag("mesh.mtls", "verified")

            def resilient_wrapped():
                return call_func(version)

            result = self.resilience_client.call(target_service, resilient_wrapped)
            outgoing_headers = span.to_headers()

        return result, outgoing_headers


# ============================================
# DEMO
# ============================================

def demo():
    certs = CertificateStore()
    traffic = TrafficPolicy()
    traffic.set_split("analytics-service", [("v1", 90), ("v2", 10)])

    sidecar = Sidecar("main-api", certs, traffic)

    print("=== Canary routing over 1000 calls (expect ~90/10 split) ===")
    from collections import Counter
    version_counts = Counter()

    def fake_call(version):
        version_counts[version] += 1
        return f"response from {version}"

    for _ in range(1000):
        sidecar.call("analytics-service", "get_summary", fake_call)

    print(dict(version_counts))

    print("\n=== mTLS rejection: an untrusted/revoked service ===")
    certs.revoke("main-api")
    try:
        sidecar.call("analytics-service", "get_summary", fake_call)
    except PermissionError as e:
        print("Blocked:", e)

    print("\n=== Sidecar metrics ===")
    print(sidecar.metrics)


if __name__ == "__main__":
    demo()
