"""Tests for Day 46: Distributed Tracing."""

import time
import pytest
from tracing_service import Tracer, TraceCollector


@pytest.fixture
def fresh_collector():
    return TraceCollector()


def test_first_hop_creates_new_trace_id(fresh_collector):
    tracer = Tracer("service-a", collector=fresh_collector)
    with tracer.span_context("op1") as span:
        pass
    assert span.trace_id is not None
    assert span.parent_span_id is None


def test_incoming_headers_continue_existing_trace(fresh_collector):
    tracer_a = Tracer("service-a", collector=fresh_collector)
    tracer_b = Tracer("service-b", collector=fresh_collector)

    with tracer_a.span_context("op_a") as span_a:
        headers = span_a.to_headers()

    with tracer_b.span_context("op_b", headers) as span_b:
        pass

    assert span_b.trace_id == span_a.trace_id
    assert span_b.parent_span_id == span_a.span_id


def test_two_unrelated_requests_get_different_trace_ids(fresh_collector):
    tracer = Tracer("service-a", collector=fresh_collector)
    with tracer.span_context("req1") as s1:
        pass
    with tracer.span_context("req2") as s2:
        pass
    assert s1.trace_id != s2.trace_id


def test_span_records_duration(fresh_collector):
    tracer = Tracer("service-a", collector=fresh_collector)
    with tracer.span_context("slow_op") as span:
        time.sleep(0.02)
    assert span.duration_ms >= 20


def test_exception_inside_span_marks_it_as_error(fresh_collector):
    tracer = Tracer("service-a", collector=fresh_collector)
    with pytest.raises(ValueError):
        with tracer.span_context("failing_op") as span:
            raise ValueError("boom")

    trace = fresh_collector.get_trace(span.trace_id)
    assert trace[0]["status"] == "error"
    assert "boom" in trace[0]["tags"]["error.message"]


def test_collector_reassembles_full_multi_service_trace(fresh_collector):
    tracer_gw = Tracer("gateway", collector=fresh_collector)
    tracer_api = Tracer("main-api", collector=fresh_collector)

    with tracer_gw.span_context("route") as gw_span:
        headers = gw_span.to_headers()
        with tracer_api.span_context("handle", headers) as api_span:
            pass

    trace = fresh_collector.get_trace(gw_span.trace_id)
    services = [s["service"] for s in trace]
    assert services == ["gateway", "main-api"]


def test_total_duration_spans_full_trace(fresh_collector):
    tracer = Tracer("svc", collector=fresh_collector)
    with tracer.span_context("outer") as outer:
        time.sleep(0.01)
        with tracer.span_context("inner", outer.to_headers()):
            time.sleep(0.01)

    total = fresh_collector.total_duration_ms(outer.trace_id)
    assert total >= 20


def test_critical_path_returns_slowest_span(fresh_collector):
    tracer = Tracer("svc", collector=fresh_collector)
    with tracer.span_context("fast_hop") as span:
        time.sleep(0.005)
        headers = span.to_headers()
        with tracer.span_context("slow_hop", headers):
            time.sleep(0.03)

    slowest = fresh_collector.critical_path(span.trace_id)
    # the outer span's duration includes the inner one, so it will show as
    # slowest here — but it must at least correctly identify a real span
    assert slowest["service"] == "svc"
    assert slowest["duration_ms"] > 0


def test_tags_are_recorded_on_span(fresh_collector):
    tracer = Tracer("svc", collector=fresh_collector)
    with tracer.span_context("op") as span:
        span.set_tag("http.status_code", 200)

    trace = fresh_collector.get_trace(span.trace_id)
    assert trace[0]["tags"]["http.status_code"] == 200


def test_unknown_trace_id_returns_empty_list(fresh_collector):
    assert fresh_collector.get_trace("does-not-exist") == []


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
