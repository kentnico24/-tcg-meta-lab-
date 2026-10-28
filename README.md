# TCG Meta Lab v0.7

Streamlit app for Limitless Play public matchups and card inclusion comparisons.

## Automatic sync

`.github/workflows/sync-limitless.yml` is scheduled for 06:20 JST and can be triggered manually in GitHub Actions. It downloads recent public PTCG Standard tournaments, exports `matches_snapshot.csv`, and commits the snapshot to the repository. The Streamlit app reads the snapshot and otherwise shows a clearly marked synthetic demo.

**Limitations:** This is an initial integration. The API and decklist normalization have not been live-tested here. GitHub-hosted data is public if the repository is public. GitHub Actions scheduled runs can be delayed or disabled by GitHub. Current workflow starts with a fresh database each run, and is **not** a comprehensive historical archive. The exported CSV can grow beyond GitHub's recommended file sizes; move to external persistent storage before large-scale collection. The match list is sourced from Limitless Play, not the full limitlesstcg.com paper tournament database.

Do not publish passwords or API keys. The default public app is read-only. Matchup percentages are observational and may be biased by missing decklists, players, event sizes, and tournament selection.
