from dtu_generation_watchdog import DtuGenerationWatchdog


def sample(power=1, voltage=43, timestamp=1000):
    return {"state": "online", "timestamp": timestamp, "panels": [
        {"port": port, "power_w": power, "voltage_v": voltage} for port in range(1, 5)
    ]}


def test_alerts_after_low_house_output_with_daylight_at_cabanon():
    watcher = DtuGenerationWatchdog()
    assert watcher.observe(sample(), cabanon_power_w=600, now=1000)["state"] == "checking"
    result = watcher.observe(sample(timestamp=1900), cabanon_power_w=600, now=1900)
    assert result["state"] == "alert"
    assert "4 panneaux maison" in result["message"]


def test_does_not_alert_when_cabanon_is_not_producing():
    watcher = DtuGenerationWatchdog()
    assert watcher.observe(sample(), cabanon_power_w=10, now=1000)["state"] == "online"


def test_recovers_when_house_panels_produce():
    watcher = DtuGenerationWatchdog()
    watcher.observe(sample(), cabanon_power_w=600, now=1000)
    assert watcher.observe(sample(power=120, timestamp=1900), cabanon_power_w=600, now=1900)["state"] == "online"
