# © 2026 LShinox — PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). Ver LICENCIA.txt.
import json, glob, os
for f in glob.glob(os.path.join(os.path.expanduser("~"), "AppData", "Local", "Claude-Data", "claude_pzs8sxrjxfjjc", "claude-code-sessions", "*", "*", "local_*.json")):
    j = json.load(open(f, encoding="utf-8"))
    if j.get("isArchived"):
        continue
    s = j.get("postTurnSummary") or {}
    t = j.get("title", "")
    print(f"{t[:34]:34} | {s.get('status_category')} | foco>{'si' if (j.get('lastFocusedAt') or 0) > (j.get('lastTurnEdgeAt') or 0) else 'NO'} | {str(s.get('status_detail', ''))[:60]}")
