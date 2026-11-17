import json

from mouse_jiggler.config import Config


def test_round_trip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(mode=2, last_host="AA:BB", path=path)
    config.save()

    loaded = Config.load(path)
    assert loaded.mode == 2
    assert loaded.last_host == "AA:BB"


def test_missing_file_uses_defaults(tmp_path):
    loaded = Config.load(tmp_path / "nope.json")
    assert loaded.mode == 0
    assert loaded.last_host == ""


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = Config.load(path)
    assert loaded.mode == 0


def test_mode_is_clamped_on_load(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mode": 99}), encoding="utf-8")
    assert Config.load(path).mode == 99 % 3


def test_save_is_atomic(tmp_path):
    path = tmp_path / "nested" / "config.json"
    Config(mode=1, path=path).save()
    assert path.exists()
    assert not path.with_suffix(".tmp").exists()


def test_device_name_round_trip(tmp_path):
    path = tmp_path / "config.json"
    Config(device_name="Desk Mouse", path=path).save()
    assert Config.load(path).device_name == "Desk Mouse"


def test_device_name_is_sanitized(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"device_name": "   "}), encoding="utf-8")
    assert Config.load(path).device_name == "CardputerZero Mouse"

    long_name = "x" * 50
    path.write_text(json.dumps({"device_name": long_name}), encoding="utf-8")
    assert len(Config.load(path).device_name) == 20
