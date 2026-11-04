"""The independent verifier must accept a good bundle and reject a forged one."""

import json
import subprocess
import sys
from pathlib import Path

from necromancer.cli import investigate
from necromancer.export import to_json

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_bundle.py"


def _run(report_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(report_path)],
        capture_output=True, text=True, check=False)


def test_verifier_accepts_real_report(synthetic, tmp_path):
    report = investigate(str(synthetic["a"]), ledger_path=str(tmp_path / "ledger.db"))
    path = tmp_path / "report.json"
    path.write_text(to_json(report), encoding="utf-8")
    proc = _run(path)
    assert proc.returncode == 0, proc.stdout


def test_verifier_rejects_stripped_provenance(synthetic, tmp_path):
    report = investigate(str(synthetic["a"]))
    path = tmp_path / "report.json"
    path.write_text(to_json(report), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["claims"][0]["falsifier"] = ""
    path.write_text(json.dumps(data), encoding="utf-8")
    proc = _run(path)
    assert proc.returncode == 1
    assert "falsifier" in proc.stdout
