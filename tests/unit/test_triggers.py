
from droplegen.pipeline.triggers import (
    TimeTrigger,
    VolumeTrigger,
    ThresholdTrigger,
    ConditionTrigger,
    ConfirmationTrigger,
    create_trigger,
)


class TestTimeTrigger:
    def test_not_triggered_immediately(self):
        t = TimeTrigger(duration_s=10.0)
        t.reset()
        assert not t.check(lambda i: 0, lambda i: 0)

    def test_triggered_after_duration(self):
        t = TimeTrigger(duration_s=0.0)
        t.reset()
        assert t.check(lambda i: 0, lambda i: 0)

    def test_progress(self):
        t = TimeTrigger(duration_s=1.0)
        t.reset()
        p = t.progress()
        assert 0.0 <= p <= 1.0

    def test_description(self):
        t = TimeTrigger(duration_s=30.0)
        assert "30" in t.description()


class TestVolumeTrigger:
    def test_not_triggered_at_zero(self):
        t = VolumeTrigger(sensor_index=0, target_volume_ul=10.0)
        t.reset()
        assert not t.check(lambda i: 0, lambda i: 0.0)

    def test_triggered_at_target(self):
        t = VolumeTrigger(sensor_index=0, target_volume_ul=10.0)
        t.reset()
        # First check records start volume
        t.check(lambda i: 0, lambda i: 0.0)
        # Second check with enough volume
        assert t.check(lambda i: 0, lambda i: 10.0)

    def test_progress_tracking(self):
        t = VolumeTrigger(sensor_index=0, target_volume_ul=100.0)
        t.reset()
        t.check(lambda i: 0, lambda i: 0.0)
        t.check(lambda i: 0, lambda i: 50.0)
        assert abs(t.progress() - 0.5) < 0.01

    def test_description(self):
        t = VolumeTrigger(sensor_index=0, target_volume_ul=75.0)
        desc = t.description()
        assert "75" in desc
        assert "sensor 0" in desc


class TestThresholdTrigger:
    def test_not_triggered_out_of_range(self):
        t = ThresholdTrigger(sensor_index=0, target=100.0, tolerance_pct=5.0, stable_duration_s=1.0)
        t.reset()
        # Flow is 0, well outside 95-105 range
        assert not t.check(lambda i: 0.0, lambda i: 0)

    def test_not_triggered_immediately_in_range(self):
        t = ThresholdTrigger(sensor_index=0, target=100.0, tolerance_pct=5.0, stable_duration_s=10.0)
        t.reset()
        # In range but hasn't been stable long enough
        assert not t.check(lambda i: 100.0, lambda i: 0)

    def test_resets_on_exit(self):
        t = ThresholdTrigger(sensor_index=0, target=100.0, tolerance_pct=5.0, stable_duration_s=0.0)
        t.reset()
        # In range with 0 duration — should trigger
        assert t.check(lambda i: 100.0, lambda i: 0)

    def test_description(self):
        t = ThresholdTrigger(sensor_index=0, target=100.0)
        assert "100.0" in t.description()


class TestConditionTrigger:
    def test_min_value_not_met(self):
        t = ConditionTrigger(sensor_index=0, min_value=50.0)
        t.reset()
        assert not t.check(lambda i: 10.0, lambda i: 0)

    def test_min_value_met(self):
        t = ConditionTrigger(sensor_index=0, min_value=50.0)
        t.reset()
        assert t.check(lambda i: 60.0, lambda i: 0)

    def test_max_value_not_met(self):
        t = ConditionTrigger(sensor_index=0, max_value=50.0)
        t.reset()
        assert not t.check(lambda i: 60.0, lambda i: 0)

    def test_max_value_met(self):
        t = ConditionTrigger(sensor_index=0, max_value=50.0)
        t.reset()
        assert t.check(lambda i: 40.0, lambda i: 0)

    def test_range(self):
        t = ConditionTrigger(sensor_index=0, min_value=10.0, max_value=50.0)
        t.reset()
        assert not t.check(lambda i: 5.0, lambda i: 0)
        t.reset()
        assert t.check(lambda i: 30.0, lambda i: 0)

    def test_stays_triggered(self):
        t = ConditionTrigger(sensor_index=0, min_value=50.0)
        t.reset()
        t.check(lambda i: 60.0, lambda i: 0)
        # Once triggered, stays triggered even if value drops
        assert t.check(lambda i: 10.0, lambda i: 0)

    def test_progress(self):
        t = ConditionTrigger(sensor_index=0, min_value=50.0)
        t.reset()
        assert t.progress() == 0.0
        t.check(lambda i: 60.0, lambda i: 0)
        assert t.progress() == 1.0


class TestConfirmationTrigger:
    def test_blocks_until_confirmed(self):
        t = ConfirmationTrigger(message="Proceed?")
        t.reset()
        assert not t.check(lambda i: 0, lambda i: 0)
        t.confirm()
        assert t.check(lambda i: 0, lambda i: 0)

    def test_message(self):
        t = ConfirmationTrigger(message="Ready?")
        assert t.message == "Ready?"

    def test_reset_clears(self):
        t = ConfirmationTrigger(message="Go?")
        t.confirm()
        assert t.check(lambda i: 0, lambda i: 0)
        t.reset()
        assert not t.check(lambda i: 0, lambda i: 0)


class TestCreateTrigger:
    def test_time(self):
        t = create_trigger("time", {"duration_s": 5.0})
        assert isinstance(t, TimeTrigger)

    def test_volume(self):
        t = create_trigger("volume", {"sensor_index": 0, "target_volume_ul": 10.0})
        assert isinstance(t, VolumeTrigger)

    def test_threshold(self):
        t = create_trigger("threshold", {"sensor_index": 0, "target": 100.0})
        assert isinstance(t, ThresholdTrigger)

    def test_condition(self):
        t = create_trigger("condition", {"sensor_index": 0, "min_value": 50.0})
        assert isinstance(t, ConditionTrigger)

    def test_confirmation(self):
        t = create_trigger("confirmation", {"message": "OK?"})
        assert isinstance(t, ConfirmationTrigger)

    def test_unknown_raises(self):
        try:
            create_trigger("invalid", {})
            assert False, "Should have raised"
        except ValueError:
            pass
