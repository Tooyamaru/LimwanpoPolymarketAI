"""
Engine Health registry tests — core/engine_health.py.

All tested functions are synchronous and deterministic, so no async
setup is required.  The shared module-level dict is reset before each
test via an autouse fixture.
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.core import engine_health


@pytest.fixture(autouse=True)
def clear_registry():
    """Wipe the heartbeat dict and registered list before and after every test."""
    engine_health._heartbeats.clear()
    engine_health._registered.clear()
    yield
    engine_health._heartbeats.clear()
    engine_health._registered.clear()


# ── record_heartbeat ───────────────────────────────────────────────────────────

class TestRecordHeartbeat:

    def test_registers_new_engine(self):
        engine_health.record_heartbeat("engine_a")
        assert "engine_a" in engine_health._heartbeats

    def test_timestamp_is_tz_aware(self):
        engine_health.record_heartbeat("engine_a")
        ts = engine_health._heartbeats["engine_a"]
        assert ts.tzinfo is not None

    def test_overwrites_previous_timestamp(self):
        engine_health.record_heartbeat("engine_a")
        t1 = engine_health._heartbeats["engine_a"]
        engine_health.record_heartbeat("engine_a")
        t2 = engine_health._heartbeats["engine_a"]
        assert t2 >= t1

    def test_multiple_engines_independent(self):
        engine_health.record_heartbeat("engine_a")
        engine_health.record_heartbeat("engine_b")
        assert "engine_a" in engine_health._heartbeats
        assert "engine_b" in engine_health._heartbeats


# ── seconds_since ──────────────────────────────────────────────────────────────

class TestSecondsSince:

    def test_unknown_engine_returns_none(self):
        assert engine_health.seconds_since("nonexistent") is None

    def test_fresh_heartbeat_returns_small_positive(self):
        engine_health.record_heartbeat("engine_a")
        age = engine_health.seconds_since("engine_a")
        assert age is not None
        assert 0.0 <= age < 5.0  # should be nearly instant

    def test_explicit_now_gives_exact_age(self):
        now = datetime.now(timezone.utc)
        engine_health._heartbeats["engine_a"] = now - timedelta(seconds=42)
        age = engine_health.seconds_since("engine_a", now=now)
        assert abs(age - 42.0) < 0.01

    def test_sixty_second_old_heartbeat(self):
        now = datetime.now(timezone.utc)
        engine_health._heartbeats["engine_a"] = now - timedelta(seconds=60)
        age = engine_health.seconds_since("engine_a", now=now)
        assert abs(age - 60.0) < 0.01

    def test_stall_detection_above_threshold(self):
        now = datetime.now(timezone.utc)
        engine_health._heartbeats["engine_a"] = now - timedelta(seconds=400)
        age = engine_health.seconds_since("engine_a", now=now)
        assert age > 300  # exceeds typical WATCHDOG_STALL_SECONDS


# ── get_heartbeats ─────────────────────────────────────────────────────────────

class TestGetHeartbeats:

    def test_empty_when_nothing_registered(self):
        assert engine_health.get_heartbeats() == {}

    def test_returns_all_registered(self):
        engine_health.record_heartbeat("engine_a")
        engine_health.record_heartbeat("engine_b")
        result = engine_health.get_heartbeats()
        assert "engine_a" in result
        assert "engine_b" in result

    def test_returns_copy_not_reference(self):
        engine_health.record_heartbeat("engine_a")
        result = engine_health.get_heartbeats()
        original_val = engine_health._heartbeats["engine_a"]
        result["engine_a"] = None          # mutate the returned copy
        assert engine_health._heartbeats["engine_a"] == original_val  # unchanged

    def test_values_are_datetime_objects(self):
        engine_health.record_heartbeat("engine_a")
        result = engine_health.get_heartbeats()
        assert isinstance(result["engine_a"], datetime)


# ── register_engines / get_registered ─────────────────────────────────────────

class TestRegisterEngines:

    def test_empty_before_registration(self):
        assert engine_health.get_registered() == []

    def test_register_stores_names(self):
        engine_health.register_engines(["price_refresh", "signal_engine"])
        result = engine_health.get_registered()
        assert result == ["price_refresh", "signal_engine"]

    def test_register_overwrites_previous_list(self):
        engine_health.register_engines(["engine_a"])
        engine_health.register_engines(["engine_b", "engine_c"])
        result = engine_health.get_registered()
        assert result == ["engine_b", "engine_c"]

    def test_get_registered_returns_copy(self):
        engine_health.register_engines(["engine_a"])
        result = engine_health.get_registered()
        result.append("intruder")          # mutate copy
        assert engine_health._registered == ["engine_a"]  # original unchanged

    def test_not_started_engine_absent_from_heartbeats(self):
        engine_health.register_engines(["price_refresh", "signal_engine"])
        # Record heartbeat for only one engine
        engine_health.record_heartbeat("price_refresh")
        hbs = engine_health.get_heartbeats()
        assert "price_refresh" in hbs
        assert "signal_engine" not in hbs  # still not_started
