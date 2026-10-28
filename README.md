# TCG Meta Lab v0.7

Streamlit app for Limitless Play public matchups and card inclusion comparisons.

## Automatic sync

`.github/workflows/sync-limitless.yml` is scheduled for 06:20 JST and can be triggered manually in GitHub Actions. It downloads recent public PTCG Standard tournaments, exports `matches_snapshot.csv`, and commits the snapshot to the repository. The Streamlit app reads the snapshot and otherwise shows a clearly marked synthetic demo.

**Limitations:** This is an initial integration. The API and decklist normalization have not been live-tested here. GitHub-hosted data is public if the repository is public. GitHub Actions scheduled runs can be delayed or disabled by GitHub. Each workflow restores the tracked CSV before collecting and merging matches. The exported CSV can grow beyond GitHub's recommended file sizes; move to external persistent storage before large-scale collection. The match list is sourced from Limitless Play, not the full limitlesstcg.com paper tournament database.

Do not publish passwords or API keys. The default public app is read-only. Matchup percentages are observational and may be biased by missing decklists, players, event sizes, and tournament selection.

### 安全なシーズン同期

`python limitless_sync.py --since 2026-09-01 --pages 2 --max-tournaments 10 --delay 2 --max-seconds 600`
を実行し、成功後に `python export_matches.py` を実行します。
同期開始時に `matches_snapshot.csv` をSQLiteへ復元します。同じ試合IDは統合し、
既存大会の取得結果が減った場合・不正な応答・通信失敗・時間切れは非ゼロ終了します。
大会更新は削除せず統合し、CSV出力では既存の全IDと件数を検査して一時ファイルから置換します。
失敗時はActionsの出力・コミット手順が実行されず、保存済みCSVを維持します。

`sync_state.json` に大会一覧・最終確認時刻・次の一覧ページを保存し、CSVと一緒にコミットします。
一覧はページ単位で進み、シーズン開始前または末尾に到達すると先頭へ戻ります。
大会は未確認・最終確認が古い順で処理するため、後日更新も巡回で確認します。
公開API一覧が日付降順であることと、既存APIのstandings/pairingsの形を前提としています。
リクエスト間隔は最低1秒、429と一時的サーバー障害は最大4回の指数バックオフ、
個別通信は最大35秒、同期全体は指定時間で打ち切ります。失敗時は状態ファイルも進めません。
`--refresh` は互換オプションとして残し、現在は常に再確認します。

デッキ名は `deck_names.py` の辞書で表示時だけ日本語にします。未登録名は英語のままです。
選択値、集計キー、保存データ、ダウンロードCSVの英語名と列形式は維持します。

検証: `python -m unittest discover -s tests -v` と
`python -m compileall -q app.py limitless_sync.py export_matches.py snapshot_store.py deck_names.py tests`。
実CSVの1,028試合保持とモックAPIでの更新・失敗保護を検証しています。
この改修時の環境ではLimitless APIがネットワーク許可対象外のため、実API通信と
Streamlitブラウザ操作は未検証です。

### 日本語デッキ名の自動組み合わせ

`deck_names.py` は既知の日本語ポケモン名や特殊デッキ名から複合デッキ名を自動構成します（例: `Alakazam Dudunsparce` → `フーディン・ノココッチ`、`Mega Excadrill` → `メガドリュウズ`）。初期1,028試合に登場した78種類のデッキ名をカバーします。新しい組み合わせは既知の構成要素だけで自動日本語化し、未知の構成要素を含む場合は誤訳を防ぐため英語のまま表示します。翻訳APIや有料AIサービスは使用しません。英語の保存データや勝率の集計キーは変更しません。
