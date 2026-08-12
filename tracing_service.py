"""
DAY 46: Distributed Tracing (Jaeger-style)
==============================================
When a request crosses the gateway (Day 43) -> main API -> analytics
service (Day 41) -> inter-service call (Day 44), and something is slow or
broken, "which hop caused it?" is impossible to answer from logs alone —
each service only sees its own slice.

Distributed tracing fixes that: every request gets one trace_id that
follows it across every service it touches, and every individual hop gets
its own span_id + parent_span_id, so the whole journey can be reassembled
into one timeline afterward. This is the same core model Jaeger, Zipkin,
and OpenTelemetry all use — simplified to an in-memory collector so it
runs with zero extra infrastructure.

Run tests:
    pytest test_tracing.py -v
"""

import time
import uuid
import contextvars
from collections import defaultdict


# ============================================
# TRACE CONTEXT (propagated across service boundaries)
# ============================================

# contextvars so concurrent requests in the same process don't clobber
# each other's "current span" — each async/thread context gets its own.
_current_span = contextvars.ContextVar("current_span", default=None)


class Span:
    def __init__(self, trace_id, span_id, parent_span_id, service_name, operation_name):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.service_name = service_name
        self.operation_name = operation_name
        self.start_time = time.time()
        self.end_time = None
        self.tags = {}
        self.status = "ok"

    def set_tag(self, key, value):
        self.tags[key] = value

    def finish(self, status="ok"):
        self.end_time = time.time()
        self.status = status

    @property
    def duration_ms(self):
        end = self.end_time or time.time()
        return round((end - self.start_time) * 1000, 3)

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service": self.service_name,
            "operation": self.operation_name,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "tags": self.tags,
        }

    def to_headers(self):
        """How this span's context gets propagated over an actual HTTP
        call to the next service — the receiving service reads these
        headers to continue the same trace instead of starting a new one."""
        return {
            "X-Trace-Id": self.trace_id,
            "X-Parent-Span-Id": self.span_id,
        }


# ============================================
# IN-MEMORY COLLECTOR (stands in for Jaeger's storage backend)
# ============================================

class TraceCollector:
    def __init__(self):
        self.spans_by_trace = defaultdict(list)

    def record(self, span):
        self.spans_by_trace[span.trace_id].append(span)

    def get_trace(self, trace_id):
        """Returns every span belonging to one trace, in start order —
        the reassembled end-to-end timeline for one request."""
        spans = sorted(self.spans_by_trace.get(trace_id, []), key=lambda s: s.start_time)
        return [s.to_dict() for s in spans]

    def total_duration_ms(self, trace_id):
        spans = self.spans_by_trace.get(trace_id, [])
        if not spans:
            return 0
        earliest = min(s.start_time for s in spans)
        latest = max(s.end_time or time.time() for s in spans)
        return round((latest - earliest) * 1000, 3)

    def critical_path(self, trace_id):
        """The single slowest span in the trace — usually where to look
        first when a request is slow."""
        spans = self.spans_by_trace.get(trace_id, [])
        if not spans:
            return None
        slowest = max(spans, key=lambda s: s.duration_ms)
        return slowest.to_dict()


collector = TraceCollector()


# ============================================
# TRACER (creates spans, links them into the current trace)
# ============================================

class Tracer:
    def __init__(self, service_name, collector=collector):
        self.service_name = service_name
        self.collector = collector

    def start_span(self, operation_name, incoming_headers=None):
        """
        Starts a new span. If `incoming_headers` carries an X-Trace-Id
        (meaning this call arrived FROM another service), the new span
        joins that existing trace as a child. Otherwise this is the very
        first hop, so a brand-new trace_id is minted here.
        """
        parent_ctx = _current_span.get()
        incoming_headers = incoming_headers or {}

        if incoming_headers.get("X-Trace-Id"):
            trace_id = incoming_headers["X-Trace-Id"]
            parent_span_id = incoming_headers.get("X-Parent-Span-Id")
        elif parent_ctx:
            trace_id = parent_ctx.trace_id
            parent_span_id = parent_ctx.span_id
        else:
            trace_id = str(uuid.uuid4())
            parent_span_id = None

        span = Span(
            trace_id=trace_id,
            span_id=str(uuid.uuid4())[:12],
            parent_span_id=parent_span_id,
            service_name=self.service_name,
            operation_name=operation_name,
        )
        return span

    def finish_span(self, span, status="ok"):
        span.finish(status=status)
        self.collector.record(span)

    def span_context(self, operation_name, incoming_headers=None):
        """Context manager: `with tracer.span_context('handle_request') as span: ...`
        Automatically finishes and records the span, even on exception."""
        return _SpanContext(self, operation_name, incoming_headers)


class _SpanContext:
    def __init__(self, tracer, operation_name, incoming_headers):
        self.tracer = tracer
        self.operation_name = operation_name
        self.incoming_headers = incoming_headers
        self.span = None
        self._token = None

    def __enter__(self):
        self.span = self.tracer.start_span(self.operation_name, self.incoming_headers)
        self._token = _current_span.set(self.span)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        status = "error" if exc_type else "ok"
        if exc_type:
            self.span.set_tag("error.message", str(exc_val))
        self.tracer.finish_span(self.span, status=status)
        _current_span.reset(self._token)
        return False  # don't swallow exceptions


# ============================================
# DEMO: a request crossing gateway -> main-api -> analytics-service
# ============================================

def demo():
    gateway_tracer = Tracer("api-gateway")
    main_api_tracer = Tracer("main-api")
    analytics_tracer = Tracer("analytics-service")

    # Hop 1: request enters at the gateway (no incoming trace headers -> new trace)
    with gateway_tracer.span_context("route_request") as gw_span:
        gw_span.set_tag("http.path", "/api/v1/analytics/summary")
        time.sleep(0.01)

        # Gateway forwards to main-api, propagating trace context via headers
        outgoing_headers = gw_span.to_headers()

        # Hop 2: main-api receives the call, continuing the SAME trace
        with main_api_tracer.span_context("handle_analytics_request", outgoing_headers) as api_span:
            time.sleep(0.02)

            # main-api calls analytics-service, propagating context again
            headers_to_analytics = api_span.to_headers()

            # Hop 3: analytics-service, still the same trace
            with analytics_tracer.span_context("compute_summary", headers_to_analytics) as an_span:
                an_span.set_tag("db.query", "SELECT COUNT(*) FROM users")
                time.sleep(0.05)  # the slow part

    trace_id = gw_span.trace_id
    print(f"=== Full trace: {trace_id} ===")
    for span in collector.get_trace(trace_id):
        indent = "  " if span["parent_span_id"] else ""
        print(f"{indent}[{span['service']}] {span['operation']} — {span['duration_ms']}ms")

    print(f"\nTotal end-to-end duration: {collector.total_duration_ms(trace_id)}ms")
    print(f"Slowest hop (critical path): {collector.critical_path(trace_id)['service']} "
          f"/ {collector.critical_path(trace_id)['operation']}")


if __name__ == "__main__":
    demo()
