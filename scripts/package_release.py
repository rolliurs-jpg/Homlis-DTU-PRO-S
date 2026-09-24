"""Crée un ZIP portable en conservant les droits des lanceurs Mac."""
from pathlib import Path
import argparse
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def release_version():
    source = (ROOT / 'boite_noire_hoymiles.py').read_text(encoding='utf-8')
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if not match:
        raise ValueError('Version du logiciel introuvable')
    return match.group(1)


def executable(path):
    return path.suffix in ('.sh', '.command') or path.parent.name == 'MacOS'


def package(target, folder_name=None):
    target = Path(target).resolve()
    version = release_version()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob('*'):
            relative = path.relative_to(ROOT)
            if (not path.is_file() or path.resolve() == target or
                any(part in ('.git', '__pycache__', 'dist', '.venv', 'venv', 'outputs') for part in relative.parts)):
                continue
            if path.name in ('surveillance.json', 'surveillance.json.tmp', 'config_v5.json', 'interruptions_suivi.jsonl') or path.suffix in ('.log', '.csv'):
                continue
            data = path.read_bytes()
            if executable(path) and b'\r' in data:
                raise ValueError(f'Fins de ligne Windows interdites : {relative}')
            root_name = folder_name or f'Homlis-DTU-PRO-S-{version}'
            entry = zipfile.ZipInfo(root_name + '/' + relative.as_posix())
            entry.create_system = 3
            entry.external_attr = (0o100755 if executable(path) else 0o100644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for entry in archive.infolist():
            if executable(Path(entry.filename)):
                assert b'\r' not in archive.read(entry)
                assert (entry.external_attr >> 16) & 0o111 == 0o111
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    parser.add_argument('--folder-name')
    args = parser.parse_args()
    print(package(args.output, args.folder_name))
