"""Tests for Day 47: Service Mesh (Istio Basics)."""

import pytest
from collections import Counter
from service_mesh import CertificateStore, TrafficPolicy, Sidecar
from tracing_service import TraceCollector, Tracer
from inter_service_client import InterServiceClient


# ---------------- mTLS ----------------

def test_issued_certificate_is_trusted():
    store = CertificateStore()
    cert = store.issue_certificate("svc-a")
    assert store.verify(cert) is True


def test_unissued_certificate_is_not_trusted():
    store = CertificateStore()
    assert store.verify("cert::never-issued") is False


def test_revoked_certificate_is_no_longer_trusted():
    store = CertificateStore()
    cert = store.issue_certificate("svc-a")
    store.revoke("svc-a")
    assert store.verify(cert) is False


def test_malformed_certificate_rejected():
    store = CertificateStore()
    assert store.verify("not-a-real-cert") is False
    assert store.verify(None) is False


# ---------------- TRAFFIC SPLITTING ----------------

def test_weights_must_sum_to_100():
    policy = TrafficPolicy()
    with pytest.raises(ValueError):
        policy.set_split("svc", [("v1", 50), ("v2", 40)])


def test_single_version_gets_all_traffic():
    policy = TrafficPolicy()
    policy.set_split("svc", [("v1", 100)])
    picks = {policy.pick_version("svc") for _ in range(20)}
    assert picks == {"v1"}


def test_split_roughly_matches_configured_weights():
    policy = TrafficPolicy()
    policy.set_split("svc", [("v1", 80), ("v2", 20)])
    picks = Counter(policy.pick_version("svc") for _ in range(2000))
    ratio = picks["v1"] / picks["v2"]
    assert 3.0 < ratio < 5.5  # ~4:1 expected, allow statistical slack


def test_unconfigured_service_returns_none():
    policy = TrafficPolicy()
    assert policy.pick_version("never-configured") is None


# ---------------- SIDECAR INTEGRATION ----------------

@pytest.fixture
def mesh():
    certs = CertificateStore()
    traffic = TrafficPolicy()
    traffic.set_split("target-svc", [("v1", 100)])
    collector = TraceCollector()
    tracer = Tracer("caller-svc", collector=collector)
    sidecar = Sidecar("caller-svc", certs, traffic, tracer=tracer,
                       resilience_client=InterServiceClient(max_retries=1))
    return sidecar, certs, collector


def test_sidecar_call_succeeds_with_valid_cert(mesh):
    sidecar, certs, collector = mesh
    result, headers = sidecar.call("target-svc", "op", lambda version: "ok")
    assert result == "ok"
    assert "X-Trace-Id" in headers


def test_sidecar_blocks_call_when_cert_revoked(mesh):
    sidecar, certs, collector = mesh
    certs.revoke("caller-svc")
    with pytest.raises(PermissionError):
        sidecar.call("target-svc", "op", lambda version: "ok")


def test_sidecar_passes_resolved_version_to_call(mesh):
    sidecar, certs, collector = mesh
    received = {}

    def capture(version):
        received["version"] = version
        return "done"

    sidecar.call("target-svc", "op", capture)
    assert received["version"] == "v1"


def test_sidecar_records_a_span_for_every_call(mesh):
    sidecar, certs, collector = mesh
    sidecar.call("target-svc", "op", lambda version: "ok")
    assert sidecar.tracer.service_name == "caller-svc"
    # exactly one trace was recorded in the collector
    assert len(collector.spans_by_trace) == 1


def test_sidecar_metrics_track_calls_and_rejections(mesh):
    sidecar, certs, collector = mesh
    sidecar.call("target-svc", "op", lambda version: "ok")
    certs.revoke("caller-svc")
    with pytest.raises(PermissionError):
        sidecar.call("target-svc", "op", lambda version: "ok")

    assert sidecar.metrics["calls"] == 2
    assert sidecar.metrics["mtls_rejections"] == 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
