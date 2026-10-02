"""Liaison HMS via ESPHome, avec commandes explicitement activables."""
import asyncio
import threading
import time

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DEFAULT_PROXY = {
    "enabled": False,
    "host": "192.168.1.239",
    "port": 6053,
    "address": "",
    "serial_tail": "",
    "enc_rand": "",
    "ble_id": "",
}

class ProxyReader:
    def __init__(self, config):
        self.config = {**DEFAULT_PROXY, **(config or {})}
        self._lock = threading.Lock()
        self._state = {"state": "disabled", "commands_enabled": False}
        self._stop = threading.Event()
        self._thread = None
        self._pending_limit = None
        self._control = {}

    def snapshot(self):
        with self._lock:
            state = {**self._state, **self._control}
        if state.get("timestamp") and time.time() - state["timestamp"] > 45:
            state.update(state="stale", reason="Mesure Hoymiles ancienne")
            state.pop("power_w", None)
            state.pop("limit_pct", None)
        return state

    def _set(self, **state):
        with self._lock:
            self._state = {"commands_enabled": False, **state}

    def request_limit(self, percent):
        if not self.config.get("commands_enabled") or isinstance(percent, bool) or not isinstance(percent, int) or not 1 <= percent <= 100:
            return False
        with self._lock:
            self._pending_limit = (percent, time.time())
        return True

    def start(self):
        if self.config["enabled"] and self._thread is None:
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _worker(self):
        while not self._stop.is_set():
            try:
                asyncio.run(self.session())
                if self.snapshot()["state"] == "authentication_required":
                    return
            except Exception as exc:
                self._set(state="offline", reason="Lecture interrompue : " + type(exc).__name__)
            if self._stop.wait(45):
                break

    async def session(self, once=False):
        import bleak
        import habluetooth
        from bleak_esphome import APIConnectionManager

        cfg = self.config
        enc_hex = str(cfg.get("enc_rand") or "").strip()
        ble_id = str(cfg.get("ble_id") or "").strip()
        if len(enc_hex) != 32 or not ble_id:
            self._set(state="authentication_required",
                      reason="Appairage Bluetooth Hoymiles requis")
            return

        try:
            enc_rand = bytes.fromhex(enc_hex)
        except ValueError:
            self._set(state="authentication_required",
                      reason="Appairage Bluetooth Hoymiles à refaire")
            return

        manager = habluetooth.BluetoothManager()
        habluetooth.set_manager(manager)
        await manager.async_setup()
        bleak.BleakClient = habluetooth.HaBleakClientWrapper
        bleak.BleakScanner = habluetooth.HaBleakScannerWrapper
        from hiflow_ble.hiflow import HiFlow

        connection = APIConnectionManager({
            "address": str(cfg["host"]),
            "noise_psk": None,
        })
        hf = None
        self._set(state="connecting", reason="Connexion au relais ESP32")
        try:
            await asyncio.wait_for(connection.start(), 25)
            address = str(cfg["address"]).upper()
            device = None
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and not self._stop.is_set():
                device = manager.async_ble_device_from_address(address, connectable=True)
                if device is not None:
                    break
                await asyncio.sleep(0.5)
            if device is None:
                raise RuntimeError("InverterNotSeen")

            self._set(state="connecting", reason="Connexion Bluetooth à l’onduleur")
            hf = HiFlow(device, enc_rand=enc_rand,
                        sn=str(cfg.get("serial_tail") or "4161A38B58B4"),
                        timeout=15, max_reconnect_attempts=1, ble_id=ble_id)
            await asyncio.wait_for(hf.connect(), 45)
            await asyncio.wait_for(hf.async_extract_enc_rand(), 30)
            self._set(state="authenticating", reason="Ouverture de la session Hoymiles")
            from hiflow_ble.hiflow import _get_action_sts
            raw_request = hf._raw_request
            login_status = {}
            async def observed_request(*args, **kwargs):
                response = await raw_request(*args, **kwargs)
                if args and args[0] == 0xA319 and response is not None:
                    action, status = _get_action_sts(response)
                    if action == 64:
                        login_status["status"] = status
                return response
            hf._raw_request = observed_request
            handshake_ok = await asyncio.wait_for(hf.async_do_comm_cmd_handshake(
                ble_id=ble_id, tz_offset=7200), 45)
            if login_status.get("status") == 3:
                self._set(state="authentication_required", reason="L’onduleur demande explicitement le code Bluetooth.")
                return
            if not handshake_ok:
                raise RuntimeError("InverterHandshakeUnavailable")

            while not self._stop.is_set():
                real = await asyncio.wait_for(hf.async_get_real_data_new(), 40)
                if real is None or not real.sgs_data:
                    raise RuntimeError("InverterDataUnavailable")
                power_w = sum(float(row.active_power) for row in real.sgs_data) / 10.0
                serial_value = int(real.sgs_data[0].serial_number) if real.sgs_data else 0
                serial = f"{serial_value:012X}" if serial_value else str(cfg.get("serial_tail", ""))
                limit_pct = None
                raw_limit = int(real.sgs_data[0].power_limit) if real.sgs_data else 0
                limit_pct = raw_limit / 100.0
                self._set(state="online", timestamp=time.time(), power_w=round(power_w, 1),
                          limit_pct=limit_pct, serial=serial,
                          reason="Lecture locale via ESP32")
                if cfg.get("commands_enabled"):
                    with self._lock:
                        pending = self._pending_limit
                        self._pending_limit = None
                    if pending and 0 <= time.time()-pending[1] <= 30 and abs(pending[0]-limit_pct) >= 1:
                        target = pending[0]
                        response = await asyncio.wait_for(hf.async_set_power_limit(target), 20)
                        if response is None or response.err_code != 0:
                            raise RuntimeError("LimitCommandRejected")
                        confirmed = await asyncio.wait_for(hf.async_get_real_data_new(), 40)
                        if confirmed is None or not confirmed.sgs_data:
                            raise RuntimeError("LimitConfirmationMissing")
                        observed = confirmed.sgs_data[0].power_limit / 100.0
                        if abs(observed-target) > 1:
                            # Restore full production on an unconfirmed reduction.
                            await asyncio.wait_for(hf.async_set_power_limit(100), 20)
                            raise RuntimeError("LimitNotConfirmed")
                        with self._lock:
                            self._control = {"commands_enabled": True, "last_command_pct": target,
                                             "last_command_timestamp": time.time(), "last_command_confirmed": True}
                        self._set(state="online", timestamp=time.time(),
                                  power_w=round(sum(float(row.active_power) for row in confirmed.sgs_data)/10, 1),
                                  limit_pct=observed, serial=serial, reason="Lecture locale via ESP32")
                if once:
                    return
                for _ in range(15):
                    if self._stop.is_set():
                        return
                    await asyncio.sleep(1)
        finally:
            if hf is not None:
                try:
                    await hf.disconnect()
                except Exception:
                    pass
            try:
                await connection.stop()
            except Exception:
                pass
