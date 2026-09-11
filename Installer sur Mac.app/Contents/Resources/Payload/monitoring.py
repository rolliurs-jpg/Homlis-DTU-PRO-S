"""Surveillance indépendante des mesures ; aucune commande aux appareils."""
from __future__ import annotations

import json
import sys
import math
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


def valid_ping_url(value):
    # La page des contrôles sépare visuellement le domaine et l'UUID.
    # Une sélection de texte peut copier cet espace (ou un espace insécable).
    value = "".join(char for char in value if not char.isspace() and char not in "\u200b\ufeff")
    if not value:
        return ""
    parts = urlsplit(value)
    if (parts.scheme != "https" or parts.netloc != "hc-ping.com"
            or parts.query or parts.fragment):
        raise ValueError("Utilisez l’URL https://hc-ping.com/ suivie de l’identifiant du contrôle.")
    try:
        identifier = str(uuid.UUID(parts.path.strip("/")))
    except ValueError:
        raise ValueError("L’identifiant du contrôle Healthchecks est incorrect.") from None
    return "https://hc-ping.com/" + identifier


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_ping(url):
    # Pas de mesure, de nom de machine ou de configuration dans le corps.
    request = Request(url, data=b"", method="POST")
    with build_opener(NoRedirect()).open(request, timeout=5) as response:
        if response.status != 200:
            raise OSError("Signal refusé")


def has_measure(values):
    for value in values:
        try:
            if value is not None and math.isfinite(float(value)):
                return True
        except (TypeError, ValueError):
            pass
    return False


class Monitoring:
    def __init__(self, base, *, clock=time.time, sender=send_ping):
        self.base = Path(base)
        self.clock, self.sender = clock, sender
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopped = threading.Event()
        self.threshold = 300
        self.started = clock()
        self.last_measure = None
        self.last_cycle = None
        self.recovery = None
        self.alarm = False
        self.io_error = ""
        self.url = ""
        self.remote = "Non configurée"
        self.last_ping = None
        self.pending = None
        try:
            saved = json.loads((self.base / "surveillance.json").read_text(encoding="utf-8"))
            self.url = valid_ping_url(saved.get("ping_url", ""))
            self.remote = "En attente d’une mesure" if self.url else "Non configurée"
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError):
            self.remote = "Configuration à vérifier"
        self.thread = threading.Thread(target=self._run, name="surveillance-hoymiles", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.wake.set()

    def configure(self, url):
        url = valid_ping_url(url)
        # Écrire avant d'activer. La clé reste exclusivement sur l'ordinateur.
        temporary = self.base / "surveillance.json.tmp"
        temporary.write_text(json.dumps({"ping_url": url}, indent=2), encoding="utf-8")
        temporary.replace(self.base / "surveillance.json")
        with self.lock:
            self.url = url
            self.pending = None
            self.last_ping = None
            self.remote = "En attente d’une nouvelle mesure" if url else "Non configurée"

    def seed(self, timestamp):
        # Historique utile au calcul des interruptions, jamais envoyé comme ping.
        with self.lock:
            if timestamp is not None and timestamp <= self.clock():
                self.last_measure = timestamp

    def _event(self, kind, **details):
        try:
            with (self.base / "interruptions_suivi.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": kind, "timestamp": self.clock(), **details}) + "\n")
        except OSError:
            self.io_error = "Journal des interruptions inaccessible"

    def record(self, values):
        """Appelé uniquement APRÈS fermeture réussie du CSV du cycle courant."""
        with self.lock:
            now = self.clock()
            self.last_cycle = now
            if not has_measure(values):
                return
            previous = self.last_measure
            if previous is not None and now - previous >= self.threshold:
                self.recovery = {"from": previous, "to": now, "seconds": now - previous}
                self._event("reprise", **self.recovery)
            self.last_measure = now
            self.alarm = False
            if self.url:
                self.pending = (self.url, now)
                self.wake.set()

    def snapshot(self):
        with self.lock:
            age = max(0, self.clock() - (self.last_measure if self.last_measure is not None else self.started))
            active = age >= self.threshold
            if active and not self.alarm:
                self._event("absence_mesures", last_measure=self.last_measure)
            self.alarm = active
            return {"active": active, "age_seconds": int(age), "threshold_seconds": self.threshold,
                    "last_measure": self.last_measure, "last_cycle": self.last_cycle,
                    "recovery": self.recovery, "remote": self.remote,
                    "remote_configured": bool(self.url), "last_ping": self.last_ping,
                    "io_error": self.io_error, "computer": "Mac" if sys.platform == "darwin" else "Windows" if sys.platform == "win32" else "Ordinateur"}

    def _dispatch(self):
        with self.lock:
            pending, self.pending = self.pending, None
            if not pending or pending[0] != self.url or self.clock() - pending[1] > 90:
                return
        url, timestamp = pending
        try:
            self.sender(url)
            result = "Signal de surveillance reçu par Healthchecks"
            successful = True
        except Exception:
            # Ne jamais exposer une exception réseau contenant la clé privée.
            result, successful = "Envoi impossible — vérifier Internet et le contrôle", False
        with self.lock:
            if self.url == url:
                self.remote = result
                if successful:
                    self.last_ping = self.clock()

    def _run(self):
        while not self.stopped.is_set():
            self.wake.wait(5)
            self.wake.clear()
            if self.stopped.is_set():
                break
            self.snapshot()
            self._dispatch()


def describe(state):
    if state["active"]:
        return (f"SUIVI INTERROMPU : aucune mesure enregistrée depuis {state['age_seconds'] // 60} min. "
                "Vérifiez que le logiciel collecte les mesures et que les appareils sont accessibles. "
                "La cause exacte n’est pas identifiée ; cela ne prouve pas un arrêt des panneaux.")
    if state["last_measure"] is None:
        return "Surveillance : en attente de la première mesure"
    return "SUIVI EN COURS : les mesures sont enregistrées normalement"


def open_settings(monitor, parent):
    import tkinter as tk
    from tkinter import ttk
    import webbrowser
    dialog = tk.Toplevel(parent)
    dialog.title("Alarmes du suivi — PC / Mac / mobile")
    dialog.geometry("720x530")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)
    text = tk.StringVar()
    ttk.Label(frame, textvariable=text, wraplength=660).pack(anchor="w", pady=(0, 15))
    ttk.Label(frame, text=("Alarme locale après 5 minutes sans aucune mesure enregistrée. Une mesure à 0 W est valide.\n"
        "Une panne partielle reste indiquée dans l’état des appareils.\n\n"
        "Pour être averti même ordinateur éteint : créez un contrôle sur Healthchecks.io, "
        "réglez Period à 1 minute et Grace Time à 4 minutes, puis configurez vos notifications. "
        "Utilisez un contrôle distinct pour chaque ordinateur."), wraplength=660).pack(anchor="w")
    ttk.Button(frame, text="Ouvrir Healthchecks", command=lambda: webbrowser.open("https://healthchecks.io/")).pack(anchor="w", pady=10)
    ttk.Label(frame, text="URL privée du contrôle (conservée sur cet ordinateur) :").pack(anchor="w")
    value = tk.StringVar(value=monitor.url)
    ttk.Entry(frame, textvariable=value, show="•", width=80).pack(fill="x", pady=6)
    feedback = tk.StringVar()
    feedback_label = tk.Label(frame, textvariable=feedback, wraplength=640,
                             justify="left", anchor="w", font=("Arial", 11, "bold"),
                             background="#eef2f6", padx=8, pady=8)
    feedback_label.pack(fill="x", pady=4)

    def save():
        try:
            monitor.configure(value.get())
            value.set(monitor.url)
            feedback_label.configure(foreground="#166534", background="#dcfce7")
            feedback.set("Enregistré. Le prochain relevé valide enverra le premier signal." if monitor.url
                         else "Envoi arrêté. Mettez aussi le contrôle en pause sur Healthchecks pour éviter une alerte.")
        except (ValueError, OSError) as exc:
            feedback_label.configure(foreground="#991b1b", background="#fee2e2")
            feedback.set(str(exc) if isinstance(exc, ValueError) else "Impossible d’enregistrer la configuration.")

    ttk.Button(frame, text="Enregistrer", command=save).pack(anchor="w", pady=8)
    ttk.Label(frame, text=("Pour tester la notification : après réception du premier signal, fermez le logiciel "
        "plus de 5 minutes et vérifiez l’alerte sur le téléphone, puis relancez-le. "
        "Ne faites pas ce test pendant une collecte importante.\n"
        "L’appli Solaire affiche l’alarme lorsqu’elle est ouverte. Les notifications en arrière-plan "
        "passent par le service extérieur. Celui-ci ne peut pas distinguer une coupure électrique d’une panne Internet."),
        wraplength=660).pack(anchor="w", pady=8)

    def refresh():
        if not dialog.winfo_exists():
            return
        state = monitor.snapshot()
        content = describe(state) + "\nSurveillance extérieure : " + state["remote"]
        if state["recovery"]:
            gap = state["recovery"]
            content += (f"\nInterruption passée de l’enregistrement (suivi rétabli) : {datetime.fromtimestamp(gap['from']):%d/%m %H:%M} → "
                        f"{datetime.fromtimestamp(gap['to']):%d/%m %H:%M} ({int(gap['seconds'] // 60)} min)")
        text.set(content)
        dialog.after(2000, refresh)
    refresh()
