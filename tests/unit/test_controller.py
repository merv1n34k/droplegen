
from droplegen.config import Step, PIPELINES
from droplegen.controller import Controller


class TestExpandSteps:
    def setup_method(self):
        self.ctrl = Controller.__new__(Controller)

    def test_no_groups_no_repeat(self):
        steps = [
            Step(name="a", sensor_setpoints={0: 1.0}, trigger_type="time", trigger_params={"duration_s": 1}),
            Step(name="b", sensor_setpoints={0: 2.0}, trigger_type="time", trigger_params={"duration_s": 2}),
        ]
        result = self.ctrl._expand_steps(steps)
        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"

    def test_repeat_single(self):
        steps = [
            Step(name="a", sensor_setpoints={0: 1.0}, trigger_type="time", trigger_params={"duration_s": 1}, repeat=3),
        ]
        result = self.ctrl._expand_steps(steps)
        assert len(result) == 3
        assert all(s.name == "a" for s in result)

    def test_group_repeat(self):
        steps = [
            Step(name="a", sensor_setpoints={0: 1.0}, trigger_type="time", trigger_params={"duration_s": 1}, group="g", repeat=2),
            Step(name="b", sensor_setpoints={0: 2.0}, trigger_type="time", trigger_params={"duration_s": 2}, group="g", repeat=2),
        ]
        result = self.ctrl._expand_steps(steps)
        assert len(result) == 4
        assert [s.name for s in result] == ["a", "b", "a", "b"]

    def test_mixed_groups(self):
        steps = [
            Step(name="solo", sensor_setpoints={0: 1.0}, trigger_type="time", trigger_params={"duration_s": 1}),
            Step(name="g1", sensor_setpoints={0: 1.0}, trigger_type="time", trigger_params={"duration_s": 1}, group="x", repeat=2),
            Step(name="g2", sensor_setpoints={0: 1.0}, trigger_type="time", trigger_params={"duration_s": 1}, group="x", repeat=2),
        ]
        result = self.ctrl._expand_steps(steps)
        assert len(result) == 5
        assert result[0].name == "solo"

    def test_dropsec_expansion(self):
        steps = PIPELINES["Drop-Seq"]
        result = self.ctrl._expand_steps(steps)
        # Prerun (1) + group "run" with 2 steps repeated 3 times (6) = 7
        assert len(result) == 7


class TestSettingsSaveLoad:
    def test_round_trip(self, tmp_path):
        ctrl = Controller.__new__(Controller)
        ctrl.SETTINGS_FILE = tmp_path / "settings.json"

        data = [
            {"flow_setpoint": 250.0, "calibration": "H2O"},
            {"flow_setpoint": 67.0, "calibration": "None"},
        ]
        ctrl.save_settings(data)
        loaded = ctrl.load_settings()
        assert loaded == data

    def test_load_missing(self, tmp_path):
        ctrl = Controller.__new__(Controller)
        ctrl.SETTINGS_FILE = tmp_path / "nonexistent.json"
        assert ctrl.load_settings() is None

    def test_load_corrupt(self, tmp_path):
        ctrl = Controller.__new__(Controller)
        ctrl.SETTINGS_FILE = tmp_path / "bad.json"
        ctrl.SETTINGS_FILE.write_text("not json")
        assert ctrl.load_settings() is None


class TestPipelineSaveLoad:
    def test_round_trip(self, tmp_path):
        ctrl = Controller.__new__(Controller)
        ctrl._pipeline_dir = lambda: tmp_path

        steps_data = [
            {
                "name": "test",
                "sensor_setpoints": {"0": 100.0},
                "trigger_type": "time",
                "trigger_params": {"duration_s": 5},
                "on_complete": "zero",
                "confirm_message": "",
                "repeat": 1,
                "group": "",
            }
        ]
        ctrl.save_pipeline("test_pipe", steps_data)

        loaded = ctrl.load_saved_pipeline("test_pipe")
        assert len(loaded) == 1
        assert loaded[0].name == "test"
        assert loaded[0].sensor_setpoints == {0: 100.0}
        assert loaded[0].trigger_type == "time"

    def test_list_saved(self, tmp_path):
        ctrl = Controller.__new__(Controller)
        ctrl._pipeline_dir = lambda: tmp_path

        (tmp_path / "alpha.json").write_text("[]")
        (tmp_path / "beta.json").write_text("[]")

        names = ctrl.list_saved_pipelines()
        assert names == ["alpha", "beta"]
