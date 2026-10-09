"""Build the ArtifactData batch that copies prices into the Morning Wire page.

Usage: python3 scripts/page_batch.py LISTING_TXT [DATA_DIR]
LISTING_TXT: a text file holding the result of ArtifactData "list" on collection "stocks"
(lines like: - "NVDA"  26312 bytes  version 2  ...). Missing or empty file = no documents yet.
Prints JSON: {"batches": [[write, ...], ...]} with at most 50 writes per batch, summary last.
"""
import json, re, sys
from pathlib import Path

listing = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 and Path(sys.argv[1]).exists() else ""
data = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/mw/data/stocks")
versions = {m.group(1): int(m.group(2)) for m in re.finditer(r'"([^"]+)"\s+\d+\s+bytes\s+version\s+(\d+)', listing)}

def write(doc_id, path):
    w = {"op": "set", "collection": "stocks", "doc_id": doc_id, "file_path": str(path.resolve())}
    if doc_id in versions:
        w["if_version"] = versions[doc_id]
    return w

writes = [write(p.stem, p) for p in sorted((data / "docs").glob("*.json"))]
writes.append(write("summary", data / "summary.json"))
batches = [writes[i:i + 50] for i in range(0, len(writes), 50)]
print(json.dumps({"batches": batches}))
