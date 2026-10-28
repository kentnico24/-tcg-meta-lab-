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

### 日次自動更新とバックフィル

GitHub Actionsは毎朝6:20 JSTに実行されます。初回のワークフロー更新を`main`にマージした際も、一度だけ自動検証を開始します。
毎回最新1ページを見直し、保存済みカーソルから過去3ページを巡回して新しい大会を検出。1回最大30大会・最大15分で公開APIを取得します。未取得大会を優先しつつ、取得済み大会の再確認枠も確保します。
個別大会で一時的な失敗・不完全な結果が発生した場合、既存試合は保持して警告を表示。失敗大会には6時間〜7日の再試行間隔を設定し、他の大会の取得を止めません。無効・衝突する試合IDの大会は更新せず警告を出します。大会一覧そのものの取得エラーでは処理を中断し、CSVは更新しません。
Limitless Play公開APIはレート制限があります。大規模化するとCSVがGitHubのファイルサイズ制限に近づくため、クラウドDB・圧縮スナップショットへの移行が必要です。未検証の非公開大会を取得するものではありません。

### 9月1日までのバックフィル強化

毎朝6:20 JSTの同期は、直近の大会一覧1ページを再確認し、前回のカーソルから最大30ページを遡ります。各実行で最大90大会、最大20分を使って、新規・未取得大会を優先して追加します。対象は2026-09-01以降にLimitless Play公開APIが返すStandard形式の大会です。日本大会を含む場合もそのAPI上で公開されているデータに限ります。

一覧がシーズン開始前まで到達したかどうかは `sync_state.json` の `season_boundary_seen` で確認できます。**一覧到達だけでは全試合取得完了ではありません**。未確認の大会がなくなった場合は、通常の再確認処理を1日最大25大会へ自動的に抑えてAPI負荷を減らします。

`sync_state.json.last_sync` に保存済み試合数、最古の日付、発見済み・確認済み大会数を記録し、Streamlitのトップに収集状況を表示します。試合データは元の `matches_snapshot.csv` に継続して蓄積され、既存試合IDの欠落を拒否します。

CSVがGitHubの推奨サイズに近づく前に圧縮ファイルや外部ストレージへ移行してください。この変更では保存形式を変更していません。

### 国内・海外の地域別分析（プレイヤー登録国による分類）

分析条件で「すべて」「国内」「海外」「国内同士」「国不明」を切り替えられます。対面勝率、勝率マトリクス、採用カード分析に共通で適用されます。「国内」は登録国JPのプレイヤーが使ったデッキ・成績、「海外」はJP以外の有効な国コードを登録したプレイヤーのデッキ・成績です。「国内同士」は対戦者双方の登録国が日本の試合です。国が未登録または無効な場合は「国不明」として集計し、勝手に海外扱いしません。

**重要：これは国内大会・海外大会の開催地域による区分ではありません。** Limitless Playの公開APIに大会の開催国フィールドがなく、参加者のcountryは本人の登録情報です。同じオンライン大会から国内・海外双方のプレイヤー視点を抽出することがあります。日本のシティリーグ等、別の大会プラットフォームで開催された大会を自動収集するものではありません。

データ取得処理は元のmatches_snapshot.csvを変更せず、参加者登録国をmatch_countries.csv（試合ID、プレイヤーA国コード、プレイヤーB国コード）に別途保存します。毎日の収集・既存大会再確認で国情報を追加します。既存試合の国が未取得の場合は「国不明」のままで、誤分類しません。既存のデッキID・カード分析・CSVダウンロード形式は維持されます。

### シティリーグ（国内公式大会）

「分析メニュー」→「シティリーグ（国内大会）」で、別の公式大会データを閲覧できます。こちらは[Limitlessの日本シティリーグ結果](https://limitlesstcg.com/tournaments/jp)から取得した**公開入賞記録**で、オンライン対戦勝率の試合CSVとは混ぜません。毎日7:10 JSTに別のGitHub Actionsで一覧を探索し、最多12大会の順位・掲載デッキ名・大会/デッキリストのURLを更新します。日付・都道府県別の絞り込み、デッキ名が判明した入賞数のランキング、個別大会の入賞一覧を表示します。取得先のHTML構造変更やアクセス制限で収集できないときは、古いデータを残し、勝手に架空の結果を生成しません。

**大切な注意**：シティリーグの掲載順位・入賞デッキ数から、全参加者の使用率や対戦相性の勝率は算出できません。対面勝率は引き続きLimitless Playのペアリング実データだけで計算します。シティリーグの掲載結果は完全とは限らず、デッキ画像などから識別できない場合は「不明」として残します。

### 国内公式大会の確認済み対面勝率（シティリーグ決勝・CL/PJCS）

シティリーグのデータビューで「国内公式大会の対面勝率（実際の勝敗）」を追加しました。Limitless TCGの大会別**1位と2位**が両方公開されているシティリーグのみ、決勝戦1試合の勝敗を確定できます（1位のデッキが勝ち、2位のデッキが負け）。上位16名の**順位のみでは、予選・準決勝・準々決勝の組み合わせは判明しない**ので、これらの勝率は推測しません。同型対戦はデッキ間の対面勝率から除外し、取得済み大会数・対象試合数を明示します。

「シティリーグ」「CL・PJCS」「国内大会すべて」の集計元を選択できます。**2026年10月時点の今シーズンCL・PJCSは、検証済み試合が未登録です。** 今後、信頼できる公開の対戦記録が確認できた場合のみ、cl_verified_matches.csv で大会名・日付・ラウンド・両方のデッキ名・勝敗・出典URLをセットで保存し、同じ国内勝率画面から集計できます。データがなければ「未登録」と表示し、勝率を作りません。

シティリーグ決勝だけの勝率は**決勝進出者に偏った標本**であり、予選を含む全国の全対戦勝率ではありません。大会の入賞デッキの分布と実対戦勝率は別の指標です。対面ごとの勝利数・敗北数・試合数・Wilson信頼区間も表示し、CSVと出典大会へ遡れるようにしています。

City League公開順位の自動同期は毎朝7:10 JSTに上限35大会を取得し、少しずつ実決勝サンプルを増やします。既存のLimitless Play対戦CSVと勝率集計には手を加えません。
