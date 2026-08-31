from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path("src/proofops/plugins/adversarial.py")
text = SOURCE.read_text(encoding="utf-8")

blocks = (
    ("BNB_MAIN_JUDGE", "BNB_DATA_QUALITY_JUDGE", "main"),
    ("BNB_DATA_QUALITY_JUDGE", "BNB_DIVERSITY_JUDGE", "data"),
    ("BNB_DIVERSITY_JUDGE", "TERMIX_SPONSOR_JUDGE", "diversity"),
    ("TERMIX_SPONSOR_JUDGE", "PANCAKE_DEFI_REVIEWER", "termix"),
    ("PANCAKE_DEFI_REVIEWER", "ALTANA_SESSION_REVIEWER", "pancake"),
    ("ALTANA_SESSION_REVIEWER", "SECURITY_RED_TEAM", "altana"),
    ("SYSTEM_ARCHITECT", "SOLO_BUILDER_SCHEDULE_ATTACKER", "architect"),
    ("SOLO_BUILDER_SCHEDULE_ATTACKER", "EVIDENCE_AUDITOR", "schedule"),
)

for start_role, end_role, prefix in blocks:
    start_marker = f"        if role == CouncilRole.{start_role}:"
    end_marker = f"        if role == CouncilRole.{end_role}:"
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    block = text[start:end]
    block = re.sub(r"\battacks\b", f"{prefix}_attacks", block)
    block = re.sub(r"\bchanges\b", f"{prefix}_changes", block)
    text = text[:start] + block + text[end:]

start_marker = "        if role == CouncilRole.EVIDENCE_AUDITOR:"
end_marker = "        raise AssertionError(role)"
start = text.index(start_marker)
end = text.index(end_marker, start)
block = text[start:end]
block = re.sub(r"\battacks\b", "evidence_attacks", block)
block = re.sub(r"\bchanges\b", "evidence_changes", block)
text = text[:start] + block + text[end:]

SOURCE.write_text(text, encoding="utf-8")
