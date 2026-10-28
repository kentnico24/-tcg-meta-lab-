# TCG Meta Lab v0.4 — Android対応Web版

## ローカル起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud への公開

1. このフォルダの内容をGitHubリポジトリのルートに配置する（SQLiteデータベースは公開しない）。
2. https://share.streamlit.io/ からGitHubリポジトリを選択。
3. Main file path に `app.py` を指定して Deploy。
4. 発行された `*.streamlit.app` のURLをAndroidのChromeで開く。
5. Chromeのメニューから「ホーム画面に追加」でショートカットを作れる。

## 制約・注意

- 公開URLは**まだ発行されていません**。GitHub認証とホスティングへのデプロイが必要です。
- 無料のStreamlit Community CloudではローカルSQLiteが再起動・再デプロイで消える可能性があり、永続DBではありません。
- サイドバーの同期ボタンはLimitless Play APIにアクセスしますが、API仕様との実通信検証は未実施です。
- Web公開したアプリのCSV取込・同期ボタンは誰でも利用できるため、一般公開前に認証・アクセス制御が必要です。
- 本番運用はPostgreSQL等の永続データベース、バックグラウンド同期、API負荷制限を推奨します。
- デッキリストが公開されない試合は採用カード比較から除外します。

## ファイル

- `app.py`: Web画面と分析
- `limitless_sync.py`: 大会データ同期
- `requirements.txt`: Python依存関係
- `.streamlit/config.toml`: Web画面設定
