"""Appairage local et unique du HMS-WB via un proxy ESPHome."""
import asyncio
import json
import time
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BASE = (Path.home() / "Library" / "Application Support" / "BoiteNoireHoymiles" if sys.platform == "darwin" else Path.home() / "AppData" / "Local" / "BoiteNoireHoymiles")
CONFIG_FILE = BASE / "config_v5.json"
PAIR_STAGE = BASE / "hoymiles_pair_stage.txt"

def _generate_ble_id():
    import hashlib
    import uuid
    raw = f"{int(time.time() * 1000)}{uuid.uuid4()}".encode("utf-8")
    digits = [int(c, 16) % 10 for c in hashlib.md5(raw).hexdigest()]
    order = [0,5,10,15,20,25,1,6,11,16,21,26,2,7,12,17,22,27]
    return str(int("".join(str(digits[i]) for i in order)))
async def pair(pin):
    import bleak
    import habluetooth
    from bleak_esphome import APIConnectionManager

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    proxy = cfg.setdefault("hoymiles_proxy", {})
    host = str(proxy.get("host") or "192.168.1.239")
    address = str(proxy.get("address") or "").upper()
    sn = str(proxy.get("serial_tail") or "")
    if not address or not sn:
        raise ValueError("Renseignez address et serial_tail dans hoymiles_proxy avant l’appairage.")
    ble_id = str(proxy.get("ble_id") or _generate_ble_id())

    manager = habluetooth.BluetoothManager()
    habluetooth.set_manager(manager)
    await manager.async_setup()
    bleak.BleakClient = habluetooth.HaBleakClientWrapper
    bleak.BleakScanner = habluetooth.HaBleakScannerWrapper
    from hiflow_ble.hiflow import HiFlow
    connection = APIConnectionManager({"address": host, "noise_psk": None})
    hf = None
    try:
        PAIR_STAGE.write_text("connexion au proxy", encoding="utf-8")
        await asyncio.wait_for(connection.start(), 25)
        device = None
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            device = manager.async_ble_device_from_address(address, connectable=True)
            if device is not None:
                break
            await asyncio.sleep(0.5)
        if device is None:
            raise RuntimeError("L’onduleur n’est pas visible depuis le proxy ESP32.")
        hf = HiFlow(address, enc_rand=None, sn=sn, timeout=15,
                    max_reconnect_attempts=1, ble_id=ble_id, pin=pin)
        PAIR_STAGE.write_text("connexion Bluetooth", encoding="utf-8")
        await asyncio.wait_for(hf.connect(), 45)
        PAIR_STAGE.write_text("lecture de la clé chiffrée", encoding="utf-8")
        enc_rand = await asyncio.wait_for(hf.async_extract_enc_rand(), 30)
        PAIR_STAGE.write_text("vérification du code Bluetooth", encoding="utf-8")
        await asyncio.wait_for(hf.async_do_comm_cmd_handshake(
            ble_id=ble_id, pin=pin, tz_offset=7200), 45)
        PAIR_STAGE.write_text("lecture de la puissance", encoding="utf-8")
        real = await asyncio.wait_for(hf.async_get_real_data_new(), 40)
        if real is None or not real.sgs_data:
            raise RuntimeError("Le code Bluetooth a été refusé ou la lecture n’a pas répondu.")
        power_w = sum(float(row.active_power) for row in real.sgs_data) / 10.0
        proxy.update({
            "enabled": True,
            "host": host,
            "port": 6053,
            "address": address,
            "serial_tail": sn,
            "enc_rand": enc_rand.hex(),
            "ble_id": hf.ble_id or ble_id,
        })
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return power_w
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

def main():
    root = tk.Tk()
    root.withdraw()
    pin = simpledialog.askstring(
        "Connexion Hoymiles",
        "Saisissez le code Bluetooth défini lors de l’installation du micro-onduleur :",
        parent=root)
    if pin is None:
        root.destroy()
        return
    try:
        power = asyncio.run(pair(pin))
    except Exception as exc:
        messagebox.showerror("Connexion Hoymiles",
            "Appairage non terminé.\n\nÉtape : " + (PAIR_STAGE.read_text(encoding="utf-8") if PAIR_STAGE.exists() else "inconnue") + "\nErreur : " + type(exc).__name__ + (" — " + str(exc) if str(exc) else ""), parent=root)
    else:
        messagebox.showinfo("Connexion Hoymiles",
            f"Connexion validée.\nPuissance lue : {power:.1f} W.\n\nVous pouvez relancer la Boîte Noire Hoymiles.",
            parent=root)
    finally:
        pin = None
        root.destroy()

if __name__ == "__main__":
    main()






