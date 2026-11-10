"""Accès Tuya Cloud minimal pour le relais d'alimentation du DTU.

Les identifiants sont lus uniquement depuis ``~/.config/tuya-relay.env`` sur
le Raspberry. Ils ne font jamais partie du fichier de configuration du site,
des journaux, ni de Git.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_ENV_FILE = Path.home() / ".config" / "tuya-relay.env"


class TuyaRelayError(RuntimeError):
    """Erreur contrôlée d'accès au relais Tuya."""


class TuyaRelay:
    """Pilote d'un interrupteur Tuya, sans dépendance Python externe."""

    def __init__(self, env_file: Path = DEFAULT_ENV_FILE):
        self.env_file = Path(env_file)
        self._lock = threading.RLock()
        self._token = ""
        self._token_expires_at = 0.0

    def _settings(self) -> dict[str, str]:
        try:
            lines = self.env_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise TuyaRelayError("configuration Tuya absente") from exc
        settings: dict[str, str] = {}
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
        required = ("TUYA_ENDPOINT", "TUYA_ACCESS_ID", "TUYA_ACCESS_SECRET", "TUYA_DEVICE_ID")
        if any(not settings.get(key) for key in required):
            raise TuyaRelayError("configuration Tuya incomplète")
        settings["TUYA_ENDPOINT"] = settings["TUYA_ENDPOINT"].rstrip("/")
        return settings

    @staticmethod
    def _string_to_sign(method: str, path: str, body: bytes) -> str:
        digest = hashlib.sha256(body).hexdigest()
        return f"{method}\n{digest}\n\n{path}"

    def _request(self, method: str, path: str, *, payload: dict | None = None,
                 access_token: str = "") -> dict:
        settings = self._settings()
        body = b"" if payload is None else json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        timestamp = str(int(time.time() * 1000))
        string_to_sign = self._string_to_sign(method, path, body)
        signing_text = (
            f"{settings['TUYA_ACCESS_ID']}{access_token}{timestamp}{string_to_sign}"
            if access_token
            else f"{settings['TUYA_ACCESS_ID']}{timestamp}{string_to_sign}"
        )
        signature = hmac.new(
            settings["TUYA_ACCESS_SECRET"].encode("utf-8"),
            signing_text.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()
        headers = {
            "client_id": settings["TUYA_ACCESS_ID"],
            "t": timestamp,
            "sign_method": "HMAC-SHA256",
            "sign": signature,
        }
        if access_token:
            headers["access_token"] = access_token
        if body:
            headers["Content-Type"] = "application/json"
        request = Request(
            settings["TUYA_ENDPOINT"] + path,
            data=body or None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=12) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise TuyaRelayError(f"API Tuya indisponible : {type(exc).__name__}") from exc
        if not result.get("success"):
            # Le message Tuya est volontairement réduit : il ne doit jamais
            # contenir d'identifiant, token ou secret dans les journaux.
            raise TuyaRelayError(f"API Tuya refusée (code {result.get('code', '?')})")
        return result.get("result") or {}

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        result = self._request("GET", "/v1.0/token?grant_type=1")
        token = str(result.get("access_token") or "")
        if not token:
            raise TuyaRelayError("jeton Tuya absent")
        expires = max(60, int(result.get("expire_time") or 3600) - 60)
        self._token = token
        self._token_expires_at = time.monotonic() + expires
        return token

    def _device_id(self) -> str:
        return self._settings()["TUYA_DEVICE_ID"]

    def status(self) -> dict:
        """Retourne le statut cloud et la position du relais, en lecture seule."""
        with self._lock:
            result = self._request(
                "GET", f"/v1.0/devices/{self._device_id()}/status",
                access_token=self._access_token(),
            )
        values = {str(row.get("code")): row.get("value") for row in result if isinstance(row, dict)}
        return {"online": bool(values.get("online_state", True)), "switch": values.get("switch")}

    def set_switch(self, enabled: bool) -> dict:
        """Envoie la seule commande autorisée : couper ou remettre le DTU."""
        with self._lock:
            return self._request(
                "POST", f"/v1.0/devices/{self._device_id()}/commands",
                payload={"commands": [{"code": "switch", "value": bool(enabled)}]},
                access_token=self._access_token(),
            )


class DtuPowerRecovery:
    """Relance électrique non bloquante, strictement opt-in, du seul DTU."""

    def __init__(self, config_getter, relay: TuyaRelay, log_path: Path):
        self._config_getter = config_getter
        self._relay = relay
        self._log_path = Path(log_path)
        self._lock = threading.RLock()
        self._active = False
        self._attempts = 0
        self._last_attempt_at = 0.0
        self._message = "relance électrique désactivée"

    @staticmethod
    def _positive_int(value, fallback: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return fallback

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "active": self._active,
                "attempts": self._attempts,
                "message": self._message,
            }

    def note_dtu_online(self) -> None:
        with self._lock:
            self._attempts = 0
            if not self._active:
                self._message = "DTU à nouveau joignable"

    def _record(self, message: str) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}; {message}\n")
        except OSError:
            pass

    def maybe_start(self, failure_seconds: float) -> str:
        cfg = self._config_getter().get("dtu_power_recovery", {})
        if not cfg.get("enabled"):
            return ""
        after_s = self._positive_int(cfg.get("after_minutes", 10), 10) * 60
        cooldown_s = self._positive_int(cfg.get("cooldown_minutes", 60), 60) * 60
        max_attempts = self._positive_int(cfg.get("max_attempts", 2), 2)
        if failure_seconds < after_s:
            return ""
        with self._lock:
            now = time.monotonic()
            if self._active:
                return self._message
            if self._attempts >= max_attempts:
                self._message = f"relance DTU bloquée après {max_attempts} essai(s)"
                return self._message
            if self._last_attempt_at and now - self._last_attempt_at < cooldown_s:
                return self._message
            self._active = True
            self._attempts += 1
            self._last_attempt_at = now
            off_seconds = self._positive_int(cfg.get("off_seconds", 30), 30)
            boot_seconds = self._positive_int(cfg.get("boot_seconds", 240), 240)
            self._message = f"relance électrique DTU en cours ({self._attempts}/{max_attempts})"
            thread = threading.Thread(
                target=self._cycle,
                args=(off_seconds, boot_seconds),
                name="dtu-power-recovery",
                daemon=True,
            )
            thread.start()
            return self._message

    def _cycle(self, off_seconds: int, boot_seconds: int) -> None:
        try:
            self._relay.set_switch(False)
            self._record(f"DTU coupé {off_seconds} s par relais Tuya")
            time.sleep(off_seconds)
            self._relay.set_switch(True)
            self._record(f"DTU remis sous tension, attente démarrage {boot_seconds} s")
            time.sleep(boot_seconds)
            message = "relance électrique terminée, contrôle DTU en attente"
        except TuyaRelayError as exc:
            message = f"relance électrique impossible : {exc}"
            self._record(message)
        finally:
            with self._lock:
                self._active = False
                self._message = message
