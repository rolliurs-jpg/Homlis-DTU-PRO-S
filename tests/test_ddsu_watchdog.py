from ddsu_watchdog import DdsuWatchdog


def meter(value=10):
    # Trois registres de série, 44 de mesure, puis le code interne DTU.
    return {"meter_registers": [1, 2, 3] + [value] * 44 + [0]}


def test_confirms_fresh_measurements_when_registers_change():
    watchdog = DdsuWatchdog()
    assert watchdog.observe(meter(10), reference_grid_w=500, now=0)["state"] == "checking"
    status = watchdog.observe(meter(11), reference_grid_w=500, now=300)
    assert status["state"] == "online"


def test_alerts_only_after_stale_data_with_real_grid_flow():
    watchdog = DdsuWatchdog()
    watchdog.observe(meter(10), reference_grid_w=500, now=0)
    status = watchdog.observe(meter(10), reference_grid_w=500, now=20 * 60)
    assert status["state"] == "offline"
    assert "figées" in status["message"]


def test_does_not_alert_for_static_data_without_network_flow():
    watchdog = DdsuWatchdog()
    watchdog.observe(meter(10), reference_grid_w=0, now=0)
    status = watchdog.observe(meter(10), reference_grid_w=0, now=60 * 60)
    assert status["state"] == "checking"
