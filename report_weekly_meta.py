"""Read-only preview of Japan top-16 share × world matchup recommendations.

The same computation is used by the mobile/web Streamlit screen. CI prints
real, current source counts and qualified picks, never fabricated win rates.
"""
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from weekly_recommendations import rank_recommendations

ROOT = Path(__file__).resolve().parent


def main():
    as_of = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    with (ROOT / "city_league_results.csv").open(
            newline="", encoding="utf-8") as city, (
            ROOT / "matches_snapshot.csv").open(
            newline="", encoding="utf-8") as world:
        report = rank_recommendations(csv.DictReader(city),
                                      csv.DictReader(world), as_of, n=5)
    jp = report["meta"]
    worldwide = report["world"]
    print(
        "Japan City League top16 only:",
        f"{jp['start']}..{jp['end']}",
        f"{jp['events']} events, {jp['total']} named placements,",
        f"{jp['unknown']} unnamed placements,",
        f"last listing {jp['last_event']}"
    )
    print(
        "Worldwide real Limitless Play matchups only:",
        f"{worldwide['first']}..{worldwide['end']}",
        f"{worldwide['matches']} matches,",
        f"last match {worldwide['latest_match']}"
    )
    print("Top Japanese threats:")
    for row in report["threats"][:8]:
        print(f" {row['label']}: {row['share']*100:.1f}% "
              f"({row['count']} placings)")
    print(f"Supported candidates: {report['eligible']}")
    for rank, item in enumerate(report["recommendations"], 1):
        print(
            f" {rank}. {item['label']}: indicative score "
            f"{item['index']*100:.1f}/100, evidence coverage "
            f"{item['coverage']*100:.1f}%, "
            f"{item['world_n']} relevant world matches, "
            f"{item['domestic_placements']} domestic placings"
        )
        for detail in item["details"][:3]:
            print(
                f"     vs {detail['opponent']}: "
                f"Japan share {detail['share']*100:.1f}%, "
                f"world observed {detail['raw']*100:.1f}% "
                f"across {detail['n']} games"
            )
    if jp["total"] and jp["events"] < 10:
        print("::warning::Japan recent seven-day results cover under 10 "
              "City League events; standings share is not national usage.")
    if len(report["recommendations"]) < 5:
        print(f"::warning::Only {len(report['recommendations'])} "
              "data-backed candidates; do not invent additional picks.")


if __name__ == "__main__":
    main()
