"""Print each cached route's shade / lit / active scores across times of day."""
import pathlib
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.scoring import Scorer, load_routes  # noqa: E402

MIAMI = ZoneInfo("America/New_York")
DAYS = [(2026, 10, 10), (2026, 8, 15)]
HOURS = [9, 13, 16, 21]

scorer = Scorer()
routes = load_routes()
for day in DAYS:
    print(f"\n=== {datetime(*day):%b %d}")
    print(f"{'route':14} {'m':>5} " + " ".join(f"{h:>2}h sun m (shade%)" for h in HOURS[:3]) + "  21h lit*/active/dark")
    for name, r in routes.items():
        cells = []
        for h in HOURS:
            s = scorer.score(r["geometry"]["coordinates"], datetime(*day, h, tzinfo=MIAMI))
            if s["daylight"]:
                cells.append(f"{s['sun_exposed_m']:>5}m sun ({s['shade']:.0%})")
            else:
                cells.append(f"{s['lit']:.0%}/{s['active']:.0%}/{s['longest_dark_m']}m")
        print(f"{name:14} {s['distance_m']:>5} " + "  ".join(f"{c:>18}" for c in cells))
