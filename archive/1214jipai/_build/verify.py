"""Integrity check: confirm raw/ copies are byte-identical to the source transcripts."""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HOME = Path.home()
# Self-locating: this script lives at <member_dir>/_build/.
LOGS = Path(__file__).resolve().parents[1]

idx = json.loads((LOGS / "sessions.json").read_text(encoding="utf-8"))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


ok = True
for s in idx["sessions"]:
    i = s["index"]
    stage = s["stage"]
    raw = LOGS / "raw" / f"{i:02d}_{stage}__{s['session_id']}.jsonl"
    src = Path(s["source_transcript"])
    if not raw.is_file():
        print(f"❌ {raw.name}: MISSING")
        ok = False
        continue
    a, b = sha(raw), sha(src)
    same = a == b
    ok &= same
    print(f"{'✅' if same else '❌'} {raw.name}")
    print(f"      raw sha256 = {a}")
    print(f"      src sha256 = {b}")

# every non-_build file in logs/ must be accounted for
print("\n--- full listing ---")
total = 0
for p in sorted(LOGS.rglob("*")):
    if p.is_file():
        total += p.stat().st_size
        print(f"{p.relative_to(LOGS)!s:<64} {p.stat().st_size:>12,} bytes")
print(f"\n{total:,} bytes total")
print("\nRAW INTEGRITY:", "ALL MATCH" if ok else "MISMATCH FOUND")
