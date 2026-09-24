"""Activation facultative du suivi invisible à l'ouverture de session."""
import os
import plistlib
import sys
from pathlib import Path


WINDOWS_STARTUP_FILE = "Boite noire Hoymiles.vbs"
MAC_PLIST_FILE = "fr.boitenoirehoymiles.web.plist"


def _system_name(platform=None):
    value = (platform or sys.platform).lower()
    if value.startswith("win"):
        return "Windows"
    if value == "darwin" or value.startswith("mac"):
        return "Mac"
    return "Autre"


def _target(base, platform=None, home=None, appdata=None):
    system = _system_name(platform)
    if system == "Windows":
        roaming_value = appdata or os.environ.get("APPDATA")
        if not roaming_value:
            raise OSError("Le dossier de démarrage Windows est introuvable.")
        roaming = Path(roaming_value)
        path = roaming / "Microsoft/Windows/Start Menu/Programs/Startup" / WINDOWS_STARTUP_FILE
    elif system == "Mac":
        path = Path(home or Path.home()) / "Library/LaunchAgents" / MAC_PLIST_FILE
    else:
        raise OSError("Le démarrage automatique est disponible uniquement sur Windows et Mac.")
    return system, Path(base), path


def status(base, platform=None, home=None, appdata=None):
    system, _base, path = _target(base, platform, home, appdata)
    return {"enabled": path.is_file(), "computer": system,
            "applies_next_start": True}


def set_enabled(enabled, base, platform=None, home=None, appdata=None):
    system, base, path = _target(base, platform, home, appdata)
    if not enabled:
        path.unlink(missing_ok=True)
        return status(base, platform, home, appdata)

    path.parent.mkdir(parents=True, exist_ok=True)
    if system == "Windows":
        launcher = base / "LANCER_INTERFACE_WEB.vbs"
        if not launcher.is_file():
            raise OSError("Le lanceur invisible Windows est introuvable.")
        quoted = str(launcher).replace('"', '""')
        content = (
            'Option Explicit\r\n'
            'Dim shell\r\n'
            'Set shell = CreateObject("WScript.Shell")\r\n'
            f'shell.Run "wscript.exe " & Chr(34) & "{quoted}" & Chr(34), 0, False\r\n'
        )
        # Windows Script Host lit de façon fiable les chemins accentués en UTF-16.
        path.write_text(content, encoding="utf-16", newline="")
    else:
        launcher = base / "LANCER_INTERFACE_WEB.command"
        if not launcher.is_file():
            raise OSError("Le lanceur invisible Mac est introuvable.")
        payload = {
            "Label": "fr.boitenoirehoymiles.web",
            "ProgramArguments": [str(launcher)],
            "RunAtLoad": True,
            "KeepAlive": True,
            "StandardOutPath": str(base / "service_web.log"),
            "StandardErrorPath": str(base / "service_web_erreur.log"),
        }
        with path.open("wb") as handle:
            plistlib.dump(payload, handle, sort_keys=False)
    return status(base, platform, home, appdata)
