"""Crée deux livraisons séparées sans mélanger Windows et macOS."""
from pathlib import Path
import io
import re
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


def version():
    source = (ROOT / "boite_noire_hoymiles.py").read_text(encoding="utf-8")
    return re.search(r'^VERSION\s*=\s*["\']([^"\']+)', source, re.MULTILINE).group(1)


def executable(path):
    return path.suffix in (".sh", ".command") or path.parent.name == "MacOS"


def mac_archive():
    """Archive Unix principale : conserve les autorisations d'exécution Mac."""
    release = version()
    target = OUTPUTS / f"Hoymiles-{release}-MAC-INSTALLATEUR-AUTONOME.tar.gz"
    app = ROOT / "macOS-AppleSilicon" / "Installer Boîte noire Hoymiles.app"
    root_name = f"Hoymiles-{release}-Mac"
    app_name = "1 - INSTALLER BOITE NOIRE HOYMILES.app"
    help_text = (
        f"BOITE NOIRE HOYMILES {release} - INSTALLATION MAC\n\n"
        "Cette archive TAR.GZ conserve les autorisations d'exécution de macOS.\n\n"
        "1. Décompressez cette archive directement sur le Mac.\n"
        "2. Faites un clic droit sur « 1 - INSTALLER BOITE NOIRE HOYMILES.app ».\n"
        "3. Choisissez Ouvrir, puis confirmez Ouvrir.\n"
        "4. Les réglages et historiques existants seront conservés.\n\n"
        "Ne décompressez pas l'archive sur Windows avant de la transférer.\n"
    ).encode("utf-8")
    OUTPUTS.mkdir(exist_ok=True)
    with tarfile.open(target, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo(f"{root_name}/2 - LIRE-MOI-MAC.txt")
        info.size = len(help_text)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(help_text))
        for path in sorted(app.rglob("*")):
            relative = path.relative_to(app).as_posix()
            info = archive.gettarinfo(str(path), f"{root_name}/{app_name}/{relative}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if path.is_dir() or executable(path) else 0o644
            if path.is_file():
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
            else:
                archive.addfile(info)
    with tarfile.open(target, "r:gz") as archive:
        members = archive.getmembers()
        launchers = [m for m in members if "/MacOS/" in m.name and m.isfile()]
        if not launchers or any(not (m.mode & 0o111) for m in launchers):
            raise RuntimeError("Les droits d'exécution Mac n'ont pas été conservés")
        expected = f"{root_name}/{app_name}/Contents/Resources/Payload/macOS-AppleSilicon/installer_mac.sh"
        if expected not in {m.name for m in members}:
            raise RuntimeError("L'installateur Mac interne est absent")
        if any("\\" in m.name for m in members):
            raise RuntimeError("Chemin Windows détecté dans l'archive Mac")
        visible = {
            member.name.split("/", 2)[1]
            for member in members
            if member.name.startswith(root_name + "/") and len(member.name.split("/", 2)) > 1
        }
        if visible != {app_name, "2 - LIRE-MOI-MAC.txt"}:
            raise RuntimeError("Le dossier Mac doit contenir seulement l'installateur et le mode d'emploi")
    return target


def windows_archive():
    release = version()
    target = OUTPUTS / f"Hoymiles-{release}-WINDOWS-SEULEMENT.zip"
    root_name = f"Hoymiles-{release}-Windows"
    required = [
        "boite_noire_hoymiles.py", "mobile_dashboard.py", "dashboard_data.py",
        "dashboard_ui.html", "autostart.py", "monitoring.py", "energy_analysis.py",
        "battery_monitor.py", "requirements.txt", "fond_solaire.png",
        "icone_panneau_solaire.ico", "config.example.json", "CHOISIR_RESEAU.ps1",
        "INSTALLER_WINDOWS.vbs", "LANCER.vbs", "LANCER_INTERFACE_WEB.vbs",
        "CHOISIR_INTERFACE.vbs",
        f"RELEASE_NOTES_{release}.md",
    ]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in required:
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(path)
            entry = zipfile.ZipInfo(f"{root_name}/{name}")
            entry.create_system = 0
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive Windows endommagée")
        if any("Mac.app" in n or "macOS-" in n for n in archive.namelist()):
            raise RuntimeError("Élément Mac détecté dans l'archive Windows")
    return target


def mac_full_archive():
    """Dossier Mac traditionnel : sources au niveau supérieur, apps en dessous."""
    release = version()
    target = OUTPUTS / f"Hoymiles-{release}-MAC-DOSSIER-COMPLET.tar.gz"
    root_name = f"Homlis-DTU-PRO-S-{release}-Mac"
    root_files = [
        "boite_noire_hoymiles.py", "mobile_dashboard.py", "dashboard_data.py",
        "dashboard_ui.html", "autostart.py", "monitoring.py", "energy_analysis.py",
        "battery_monitor.py", "requirements.txt", "fond_solaire.png",
        "icone_panneau_solaire.ico", "config.example.json", "README.md",
        f"RELEASE_NOTES_{release}.md",
    ]
    mac_root = ROOT / "macOS-AppleSilicon"
    mac_items = [
        mac_root / "installer_mac.sh",
        mac_root / "LANCER_INTERFACE_WEB.command",
        mac_root / "README_MAC.md",
    ]
    for app_name in ("Installer Boîte noire Hoymiles.app", "Boîte noire Hoymiles.app"):
        mac_items.extend(p for p in (mac_root / app_name).rglob("*") if p.is_file())
    with tarfile.open(target, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name in root_files:
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(path)
            info = archive.gettarinfo(str(path), f"{root_name}/{name}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            with path.open("rb") as handle:
                archive.addfile(info, handle)
        for path in sorted(mac_items):
            relative = path.relative_to(ROOT).as_posix()
            info = archive.gettarinfo(str(path), f"{root_name}/{relative}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if executable(path) else 0o644
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    with tarfile.open(target, "r:gz") as archive:
        members = {m.name: m for m in archive.getmembers()}
        required = {
            f"{root_name}/{name}" for name in root_files
        } | {
            f"{root_name}/macOS-AppleSilicon/installer_mac.sh",
            f"{root_name}/macOS-AppleSilicon/LANCER_INTERFACE_WEB.command",
            f"{root_name}/macOS-AppleSilicon/Installer Boîte noire Hoymiles.app/Contents/MacOS/InstallerBoiteNoireHoymiles",
            f"{root_name}/macOS-AppleSilicon/Boîte noire Hoymiles.app/Contents/MacOS/BoiteNoireHoymiles",
        }
        missing = required - members.keys()
        if missing:
            raise RuntimeError("Fichiers absents du dossier Mac : " + ", ".join(sorted(missing)))
        launchers = [m for m in members.values() if "/MacOS/" in m.name]
        if any(not (m.mode & 0o111) for m in launchers):
            raise RuntimeError("Droit d'exécution absent du dossier Mac")
    return target


def mac_full_zip():
    """ZIP Mac simple : un installateur autonome et un mode d'emploi visible."""
    release = version()
    OUTPUTS.mkdir(exist_ok=True)
    target = OUTPUTS / f"Hoymiles-{release}-MAC-INSTALLATEUR-AUTONOME.zip"
    root_name = f"Hoymiles-{release}-Mac"
    app = ROOT / "macOS-AppleSilicon" / "Installer Boîte noire Hoymiles.app"
    app_name = "1 - INSTALLER BOITE NOIRE HOYMILES.app"
    help_name = f"{root_name}/2 - LIRE-MOI-MAC.txt"
    help_text = (
        f"BOITE NOIRE HOYMILES {release} - INSTALLATION MAC\n\n"
        "Le dossier contient volontairement un seul installateur.\n\n"
        "1. Sur le Mac, faites un clic droit sur « 1 - INSTALLER BOITE NOIRE "
        "HOYMILES.app ».\n"
        "2. Choisissez Ouvrir, puis confirmez Ouvrir.\n"
        "3. Cliquez sur Continuer et laissez l'installation se terminer.\n\n"
        "Les réglages et historiques existants sont conservés.\n"
        "Ne sortez aucun fichier du contenu de l'application.\n"
    ).encode("utf-8")
    files = [p for p in app.rglob("*") if p.is_file()]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        readme = zipfile.ZipInfo(help_name)
        readme.create_system = 3
        readme.flag_bits |= 0x800
        readme.external_attr = 0o100644 << 16
        readme.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(readme, help_text)
        for path in sorted(files):
            if not path.is_file():
                raise FileNotFoundError(path)
            relative = path.relative_to(app).as_posix()
            entry = zipfile.ZipInfo(f"{root_name}/{app_name}/{relative}")
            entry.create_system = 3
            entry.flag_bits |= 0x800
            entry.external_attr = (0o100755 if executable(path) else 0o100644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive ZIP Mac endommagée")
        launchers = [i for i in archive.infolist() if "/MacOS/" in i.filename]
        if not launchers or any(not ((i.external_attr >> 16) & 0o111) for i in launchers):
            raise RuntimeError("Droits d'exécution absents du ZIP Mac")
        if any(b"\r\n" in archive.read(i) for i in launchers):
            raise RuntimeError("Fins de ligne Windows détectées dans un lanceur Mac")
        visible = {
            name.split("/", 2)[1]
            for name in archive.namelist()
            if name.startswith(root_name + "/") and len(name.split("/", 2)) > 1
        }
        expected = {app_name, "2 - LIRE-MOI-MAC.txt"}
        if visible != expected:
            raise RuntimeError("Le dossier Mac doit contenir seulement l'installateur et le mode d'emploi")
    return target


if __name__ == "__main__":
    print(mac_archive())
    print(windows_archive())
