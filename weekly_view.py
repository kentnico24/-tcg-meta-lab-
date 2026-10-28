"""Streamlit view for domestic 7-day meta shares x worldwide matchup evidence."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from weekly_recommendations import rank_recommendations, family_label


@st.cache_data(ttl=1800, show_spinner=False)
def calculate_weekly(local_path, world_path, local_mtime, world_mtime, as_of):
    """Cache by both snapshot mtimes and Japan-local current date."""
    city = pd.read_csv(
        local_path, dtype=str, keep_default_na=False,
        usecols=["key", "date", "deck", "event_url"],
    )
    world = pd.read_csv(
        world_path, dtype=str, keep_default_na=False,
        usecols=["id", "played_at", "deck_a", "deck_b", "winner", "source"],
    )
    return rank_recommendations(city.to_dict("records"),
                                world.to_dict("records"), as_of, n=5)


def render_weekly_recommendations(root):
    """Only the *share* is Japanese; the win/loss evidence is worldwide."""
    st.subheader("🇯🇵 国内環境向け・今週のおすすめ5デッキ")
    st.caption(
        "国内シェア：日本のシティリーグ直近7日間の上位入賞デッキのみ。"
        "対面相性：Limitless Play世界公開試合の直近30日間。"
        "海外のシェア率や大会順位を国内シェアには混ぜません。"
    )
    root = Path(root)
    city_path = root / "city_league_results.csv"
    world_path = root / "matches_snapshot.csv"
    if not city_path.exists() or not world_path.exists():
        st.warning("国内シティリーグ結果または世界の対戦CSVが未取得のため、おすすめを計算できません。")
        return
    try:
        japan_today = datetime.now(timezone(timedelta(hours=9))).date()
        result = calculate_weekly(
            str(city_path), str(world_path),
            city_path.stat().st_mtime_ns,
            world_path.stat().st_mtime_ns,
            japan_today,
        )
        meta = result["meta"]
        world = result["world"]
        st.caption(
            f"国内シェア：{meta['start'].isoformat()}〜{meta['end'].isoformat()}（日本時間）"
            f" ／ 世界対面：{world['first'].isoformat()}〜{world['end'].isoformat()}"
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("国内の入賞記録", f"{meta['total']:,}件")
        c2.metric("国内の掲載大会", f"{meta['events']:,}大会")
        c3.metric("世界の公開対戦", f"{world['matches']:,}試合")
        st.caption(
            f"国内の最終掲載日：{meta['last_event'] or 'なし'}"
            f" ／ 世界の最終対戦日：{world['latest_match'] or 'なし'}"
            f" ／ デッキ名不明の国内入賞：{meta['unknown']}件"
        )
        if not meta["total"]:
            st.info("直近7日間に確認できた国内シティリーグの入賞データがありません。収集後に自動表示されます。")
            return
        if meta["events"] < 10:
            st.warning(
                "直近7日間に掲載されている国内大会が少なく、"
                "入賞内シェアが全国の環境を代表していない可能性があります。"
            )
        if not world["matches"]:
            st.info("直近30日間に使える世界の公開対戦データがありません。推測によるランキングは作りません。")
            return
        if (world["latest_match"] and world["latest_match"] <
                (japan_today-timedelta(days=7)).isoformat()):
            st.warning("世界の対戦記録が7日以上更新されていません。最新環境での相性とは限りません。")

        st.subheader("国内の直近7日間・入賞内シェア")
        share_rows = [
            {"デッキタイプ": item["label"],
             "入賞内シェア": f"{item['share']*100:.1f}%",
             "入賞件数": item["count"]}
            for item in result["threats"]
        ]
        st.dataframe(pd.DataFrame(share_rows),
                     use_container_width=True, hide_index=True)
        st.caption(
            "入賞内シェア＝日本のシティリーグ上位入賞デッキの構成比。"
            "全参加者の使用率ではありません。複合デッキは主軸のデッキタイプで集約します。"
        )

        st.subheader("国内環境への相性で選ぶおすすめ")
        st.caption(
            "環境適性スコア（0〜100点）は国内の入賞内シェアを重みとして、"
            "世界の実対面勝率を試合数で補正した参考指標です。"
            "国内での実測勝率ではありません。対戦不明の相性は50%として扱い、"
            "証拠が少ない候補は表示しません。"
        )
        if not result["recommendations"]:
            st.warning(
                "国内の入賞実績と世界の対面試合数が不足しているため、"
                "根拠を示せるおすすめはまだありません。"
                "両方のデータが増えると自動的に追加されます。"
            )
        for index, item in enumerate(result["recommendations"], 1):
            st.markdown(f"#### {index}位　{item['label']}")
            k1, k2, k3 = st.columns(3)
            k1.metric("環境適性", f"{item['index']*100:.1f}点")
            k2.metric("世界の対象対面", f"{item['world_n']:,}試合")
            k3.metric("検証済み相手のシェア", f"{item['coverage']*100:.0f}%")
            st.caption(
                f"根拠の信頼度：{item['confidence']} ／ "
                f"国内シティリーグの直近60日以内の入賞掲載：{item['domestic_placements']}件"
            )
            if item["strengths"]:
                best = item["strengths"][0]
                st.write(
                    f"主な評価材料：**{family_label(best['opponent'])}**"
                    f"（国内入賞内シェア{best['share']*100:.1f}%）に対し、"
                    f"世界の公開対戦{best['n']}試合で実測勝率{best['raw']*100:.1f}%。"
                )
            else:
                st.caption("明確に有利といえる個別対面は十分に確認できていません。")
            with st.expander(f"{item['label']} の世界対面データ内訳"):
                rows = [
                    {
                        "対面": family_label(row["opponent"]),
                        "国内入賞内シェア": f"{row['share']*100:.1f}%",
                        "世界の対面試合数": row["n"],
                        "世界の実測勝率": f"{row['raw']*100:.1f}%",
                        "試合数補正後の相性推定": f"{row['shrunk']*100:.1f}%",
                    }
                    for row in item["details"]
                ]
                st.dataframe(pd.DataFrame(rows),
                             use_container_width=True, hide_index=True)
            st.divider()
        st.caption(
            f"データ条件を満たす候補：{result['eligible']}タイプ。最大5タイプを表示。"
            "候補は国内シティリーグ今季の入賞実績があるタイプに限ります。"
        )
        st.caption(
            "日付が変わると直近7日間を自動で再計算します。"
            "GitHub Actionsの世界戦績6:20・国内結果7:10（日本時間）の"
            "日次同期で保存CSVも更新されます。実行時刻は遅れる場合があります。"
        )
        st.info(
            "重要：日本と海外では使用可能カード・大会形式・構築が異なる場合があります。"
            "世界の相性を国内に当てはめた参考スコアであり、"
            "国内で同じ勝率が出る保証ではありません。"
        )
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"おすすめの計算に必要な公開データを読み込めませんでした：{exc}")
