from droplegen.config import Step, PIPELINES, SENSOR_CALIBRATIONS, SENSOR_CHANNEL_NAMES


class TestStep:
    def test_defaults(self):
        s = Step(
            name="test",
            sensor_setpoints={0: 100.0},
            trigger_type="time",
            trigger_params={"duration_s": 10},
        )
        assert s.on_complete == "hold"
        assert s.confirm_message == ""
        assert s.repeat == 1
        assert s.group == ""

    def test_custom_fields(self):
        s = Step(
            name="custom",
            sensor_setpoints={0: 50.0, 1: 30.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 0, "target_volume_ul": 100},
            on_complete="zero",
            confirm_message="Ready?",
            repeat=3,
            group="g1",
        )
        assert s.on_complete == "zero"
        assert s.confirm_message == "Ready?"
        assert s.repeat == 3
        assert s.group == "g1"
        assert len(s.sensor_setpoints) == 2


class TestPipelines:
    def test_builtin_pipelines_exist(self):
        assert "Drop-Seq" in PIPELINES
        assert "Priming" in PIPELINES

    def test_dropsec_steps(self):
        steps = PIPELINES["Drop-Seq"]
        assert len(steps) == 3
        assert steps[0].name == "Prerun"
        assert steps[0].trigger_type == "volume"

    def test_priming_has_confirmations(self):
        steps = PIPELINES["Priming"]
        assert all(s.confirm_message for s in steps)

    def test_all_steps_have_valid_trigger_types(self):
        valid = {"time", "volume", "threshold", "condition"}
        for name, steps in PIPELINES.items():
            for s in steps:
                assert s.trigger_type in valid, f"{name}/{s.name}: {s.trigger_type}"


class TestSensorCalibrations:
    def test_calibrations_present(self):
        assert len(SENSOR_CALIBRATIONS) >= 5
        assert "H2O" in SENSOR_CALIBRATIONS
        assert "None" in SENSOR_CALIBRATIONS

    def test_calibration_values_are_ints(self):
        for name, val in SENSOR_CALIBRATIONS.items():
            assert isinstance(val, int)

    def test_channel_names(self):
        assert len(SENSOR_CHANNEL_NAMES) == 3
        assert "Oil" in SENSOR_CHANNEL_NAMES[0]
