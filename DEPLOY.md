# TCG Meta Lab v0.5 — Web deployment

## Tested locally

The importer tests run without network access: `python -m pytest -q tests/`.

## Publish on Streamlit Community Cloud

1. Create a **private** GitHub repository and upload this project's files (not `research.sqlite3`).
2. Connect that repository at https://share.streamlit.io/ and choose `app.py` as the entrypoint.
3. Deploy. Open the resulting `*.streamlit.app` URL from Android Chrome.
4. In Chrome's menu choose Add to Home screen for an app-like shortcut.

**Important:** No hosted URL is created by this package. You must authorize GitHub/Streamlit for publishing. The app runs in read-only mode by default: cloud users cannot trigger API sync or upload data. To enable writes for a trusted local instance, set `TCG_ALLOW_WRITES=1` before launching. Do not enable writes on a publicly accessible deployment without authentication.

SQLite on Community Cloud is ephemeral. For persistent tournament data, use a hosted database or a separately maintained database snapshot. This release does not yet implement hosted database persistence or scheduled synchronization. The Limitless API mapping has not been live-verified; sync may need adaptation to the API's actual payloads.

## Local development

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q tests/
streamlit run app.py
```
