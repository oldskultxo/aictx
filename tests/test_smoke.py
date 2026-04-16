from aictx.state import default_global_config


def test_default_global_config_has_workspace():
    cfg = default_global_config()
    assert cfg["active_workspace"] == "default"
