"""Verify and preview today's domestic-meta picks from the real tracked CSV files.

Read-only; daily GitHub Actions update the two source snapshots. Streamlit
recomputes the top 5 whenever the updated snapshots are deployed.
"""
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from domestic_recommendations import recommend
from deck_names import deck_name, city_deck_name


ROOT = Path(__file__).resolve().parent


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    city = ROOT / "city_league_results.csv"
    world = ROOT / "matches_snapshot.csv"
    with city.open(newline="", encoding="utf-8") as city_file, \
            world.open(newline="", encoding="utf-8") as world_file:
        report = recommend(csv.DictReader(city_file),
                           csv.DictReader(world_file), today)
    jp = report["japan"]
    global_stats = report["world"]
    print(f"JP City League top-16 shares: {jp['start']} to {jp['end']}; "
          f"{jp['events']} events, {jp['placements']} placements")
    print(f"Worldwide Limitless Play records: {global_stats['start']} to "
          f"{global_stats['end']}; {global_stats['matches']} verified matches")
    for family, share in sorted(jp["shares"].items(),
                                key=lambda x: -x[1])[:5]:
        print(f" JP {city_deck_name(family)}: "
              f"{share * 100:.1f}% ({jp['counts'][family]} placings)")
    for i, pick in enumerate(report["recommendations"], 1):
        print(f" {i}. {deck_name(pick['deck'])}: index={pick['meta_score']:.1f} "
              f"coverage={pick['matched_share']:.1f}% "
              f"related_games={pick['matched_games']} "
              f"world_appearances={pick['world_matches']}")
        for detail in pick["evidence"][:3]:
            print(f"   vs {city_deck_name(detail['family'])}: "
                  f"JP {detail['jp_share']}%; worldwide "
                  f"{detail['world_win_rate']}% over {detail['games']} games")
    if len(report["recommendations"]) < 5:
        print(f"::warning::Only {len(report['recommendations'])} "
              "candidate(s) have sufficient documented worldwide matchup "
              "evidence for this week's domestic meta.")
    # No misleading success claim for unavailable records.
    if jp["placements"] and not report["recommendations"]:
        print("::warning::Insufficient matchup evidence; no recommendations.")


if __name__ == "__main__":
    main()
