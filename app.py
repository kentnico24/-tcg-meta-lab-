import sqlite3, json, math, pathlib, io, os, subprocess, sys
from datetime import datetime
import pandas as pd
import streamlit as st
from deck_names import deck_name, city_deck_name
from domestic_matchups import city_final_matches, read_verified_cl_matches, player_perspectives
from zoneinfo import ZoneInfo
from region_labels import country_group, eligible_player
from weekly_view import render_weekly_recommendations
from matrix_style import matrix_cell_css
from matchup_sort import MATCHUP_SORT_OPTIONS, sort_matchup_rows
from deck_variants import classify_dragapult
ROOT=pathlib.Path(__file__).parent
DB=pathlib.Path(os.environ.get('TCG_DB_PATH', str(ROOT/'research.sqlite3')))
st.set_page_config(page_title='TCG Meta Lab',page_icon='🃏',layout='wide')
WRITES_ENABLED = os.environ.get('TCG_ALLOW_WRITES', '').lower() in ('1', 'true', 'yes')
@st.cache_resource
def connection():
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB,check_same_thread=False,timeout=30)
 c.execute('PRAGMA journal_mode=WAL')
 c.execute('''CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY,event TEXT,played_at TEXT,deck_a TEXT,deck_b TEXT,winner TEXT,decklist_a TEXT,decklist_b TEXT,source TEXT)''')
 c.commit();return c
c=connection()
def normalize_list(v):
 if isinstance(v,dict):return {str(k):int(n) for k,n in v.items() if str(n).isdigit()}
 if pd.isna(v) or not str(v).strip():return {}
 try:
  z=json.loads(v)
  if isinstance(z,dict):return normalize_list(z)
 except (ValueError,TypeError):pass
 result={}
 for line in str(v).splitlines():
  line=line.strip()
  if not line:continue
  p=line.split(',',1)
  if len(p)==2 and p[1].strip().isdigit():result[p[0].strip()]=int(p[1])
 return result
def load_csv(data):
 df=pd.read_csv(data,dtype=str).fillna('')
 required={'id','deck_a','deck_b','winner'}
 if not required.issubset(df.columns):raise ValueError('必須列: id, deck_a, deck_b, winner')
 rows=[]
 for _,r in df.iterrows():
  if not r['id'].strip() or not r['deck_a'].strip() or not r['deck_b'].strip():continue
  w=r['winner'].strip().lower()
  if w not in ('a','b','draw'):continue
  rows.append((r['id'],r.get('event',''),r.get('played_at',''),r['deck_a'],r['deck_b'],w,json.dumps(normalize_list(r.get('decklist_a','')),ensure_ascii=False),json.dumps(normalize_list(r.get('decklist_b','')),ensure_ascii=False),r.get('source','csv')))
 with c:
  c.executemany('INSERT OR IGNORE INTO games VALUES (?,?,?,?,?,?,?,?,?)',rows)
 return len(rows)
def wilson(w,n):
 if not n:return (0,0)
 z=1.96;p=w/n;d=1+z*z/n;mid=(p+z*z/(2*n))/d;err=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return max(0,mid-err),min(1,mid+err)
def perspective(df,deck,region='すべて'):
 a=df[df.deck_a==deck].copy();b=df[df.deck_b==deck].copy()
 if region!='すべて':
  a=a[a.apply(lambda r: eligible_player(r.country_a,r.country_b,'a',region),axis=1)]
  b=b[b.apply(lambda r: eligible_player(r.country_a,r.country_b,'b',region),axis=1)]
 a['opponent']=a.deck_b;a['result']=a.winner.map({'a':1.,'b':0.,'draw':.5});a['cards']=a.decklist_a
 b['opponent']=b.deck_a;b['result']=b.winner.map({'a':0.,'b':1.,'draw':.5});b['cards']=b.decklist_b
 a['player_country']=a.country_a
 b['player_country']=b.country_b
 return pd.concat([a,b],ignore_index=True)

def available_decks(df,region):
 if region=='すべて':
  return sorted(set(df.deck_a)|set(df.deck_b),key=deck_name)
 a=df[df.apply(lambda r: eligible_player(r.country_a,r.country_b,'a',region),axis=1)]
 b=df[df.apply(lambda r: eligible_player(r.country_a,r.country_b,'b',region),axis=1)]
 return sorted(set(a.deck_a)|set(b.deck_b),key=deck_name)
def stats(g):
 n=len(g);w=float(g.result.sum());lo,hi=wilson(w,n)
 return {'試合数':n,'勝率':round(w/n*100,1) if n else 0,'95%下限':round(lo*100,1),'95%上限':round(hi*100,1),'勝ち相当':w}
st.title('🃏 TCG Meta Lab')
st.caption('Android / PC 対応 Web版 v0.7')
st.caption('デッキ・対面・採用カードを横断する独立型リサーチアプリ | 実データのみを集計')

view=st.radio('分析メニュー', ['対戦勝率・採用カード', 'シティリーグ（国内大会）', '今週のおすすめ'],
              horizontal=True, help='今週のおすすめ：国内シティリーグ直近7日間の入賞内シェア × 世界公開試合の対面勝率。')
if view=='今週のおすすめ':
 render_weekly_recommendations(ROOT)
 st.stop()
if view=='シティリーグ（国内大会）':
 st.subheader('🇯🇵 シティリーグ（国内大会）')
 st.caption('参照元: Limitless TCG掲載の日本シティリーグ。順位・公開デッキだけを集計し、対戦履歴がない大会から対面勝率を推測しません。')
 st.markdown('[シティリーグ大会一覧（Limitless）](https://limitlesstcg.com/tournaments/jp)')
 city_file=ROOT/'city_league_results.csv'
 if not city_file.exists():
  st.info('シティリーグの入賞データはまだ同期されていません。取得に成功すると、この画面に大会結果とデッキ掲載数を表示します。')
  st.stop()
 try:
  city=pd.read_csv(city_file,dtype=str,keep_default_na=False)
  expected={'key','date','prefecture','shop','rank','deck','player','event_url','decklist_url'}
  if not expected.issubset(city.columns):
   raise ValueError('シティリーグCSVの列が一致しません')
  if city.empty:
   st.info('登録されたシティリーグの入賞データはまだありません。')
   st.stop()
  st.success(f'シティリーグ：{city.event_url.nunique():,}大会 / {len(city):,}入賞記録')
  st.caption(f'保存されている期間：{city.date.min()} 〜 {city.date.max()}。全シティリーグの網羅を意味するものではありません。')
  st.caption('公式のシティリーグ2027 シーズン1は2026年9月25日〜11月14日です。9月1日〜24日の掲載大会がある場合は別期間として扱います。')
  city_season=st.selectbox('シティリーグのシーズン',['2026年9月1日以降（すべて）','2027シーズン1（9/25〜11/14）','2027開始前（9/1〜9/24）'],
                           help='シティリーグだけを区分します。CL横浜などのCL・PJCSは別大会として集計し、シティリーグのシーズンで分類しません。')
  if city_season.startswith('2027シーズン1'):
   city=city[(city.date>='2026-09-25')&(city.date<='2026-11-14')]
  elif city_season.startswith('2027開始前'):
   city=city[(city.date>='2026-09-01')&(city.date<'2026-09-25')]
  prefectures=sorted(x for x in city.prefecture.unique() if x)
  selected_pref=st.selectbox('都道府県',['すべて']+prefectures)
  if selected_pref!='すべて':
   city=city[city.prefecture==selected_pref]
  try:
   cl_matches=read_verified_cl_matches(ROOT/'cl_verified_matches.csv')
  except (OSError,ValueError) as error:
   st.warning(f'CL・PJCSの確認済み試合ファイルを利用できません: {error}')
   cl_matches=[]
  if selected_pref!='すべて':
   # Verified CL matches have no structured prefecture metadata yet; never
   # silently mix a nationwide CL with an explicitly selected City prefecture.
   cl_matches=[]
   st.caption('都道府県の絞り込みはシティリーグにのみ対応しています。CLを分析するときは都道府県を「すべて」にしてください。')
  city_dates=pd.to_datetime(city.date,errors='coerce')
  all_days=list(city_dates.dropna().dt.date)
  all_days.extend(pd.to_datetime([m['date'] for m in cl_matches]).date)
  if all_days:
   start_date=min(all_days)
   end_date=max(all_days)
   city_period=st.date_input('国内大会の開催期間',(start_date,end_date),min_value=datetime(2026,9,1).date(),max_value=max(end_date,datetime(2026,9,1).date()),key='city_period',help='9月1日から指定できます。結果が未取得の期間を選んでも、勝率は推測せず確認済み試合だけを表示します。')
   if isinstance(city_period,tuple) and len(city_period)==2:
    city=city[(city_dates.dt.date>=city_period[0])&(city_dates.dt.date<=city_period[1])]
    cl_matches=[m for m in cl_matches if city_period[0]<=pd.to_datetime(m['date']).date()<=city_period[1]]
   if city.empty and not cl_matches:
    st.info('選択した開催期間には、まだ確認済みの国内大会結果がありません。追加取得後に表示されます。')
  # A City League 1st place necessarily defeated the runner-up in the final.
  # No other pairing can be reconstructed from a top-16 rankings table.
  st.subheader('国内公式大会の対面勝率（実際の勝敗）')
  st.caption('公開された優勝・準優勝から確認できる決勝戦のみを対象とします。予選や、トーナメント表がない準決勝・準々決勝は含みません。')
  source_choice=st.selectbox('勝率のデータ元',['シティリーグ','CL・PJCS','国内大会すべて'],
                            help='CL・PJCSの公開された実対戦結果を確認できた場合に追加します。掲載順位だけから勝率を推測しません。')
  city_matches=city_final_matches(city.to_dict('records'))
  if source_choice=='シティリーグ':
   domestic_matches=city_matches
  elif source_choice=='CL・PJCS':
   domestic_matches=cl_matches
  else:
   domestic_matches=city_matches+cl_matches
  if source_choice!='シティリーグ' and not cl_matches:
   st.info('この条件に一致するCL・PJCSの確認済み対戦はありません。開催期間や都道府県の絞り込みも確認してください。')
  if source_choice!='シティリーグ' and cl_matches:
   st.caption('CL2027横浜とシティリーグでは使用可能なカード・大会形式が異なる場合があります。合算するときは集計期間と環境差に注意してください。')
  mirrors=sum(m['deck_a']==m['deck_b'] for m in domestic_matches)
  nonmirrors=[m for m in domestic_matches if m['deck_a']!=m['deck_b']]
  m1,m2,m3=st.columns(3)
  m1.metric('確認済みの対戦',f'{len(domestic_matches):,}試合')
  m2.metric('対面分析に使える試合',f'{len(nonmirrors):,}試合')
  m3.metric('同型対戦（除外）',f'{mirrors:,}試合')
  if nonmirrors:
   observations=pd.DataFrame(player_perspectives(nonmirrors))
   all_decks=sorted(observations.deck.unique(),key=city_deck_name)
   chosen_deck=st.selectbox('対面勝率を調べるデッキ',['すべて']+all_decks,
                            format_func=lambda x: x if x=='すべて' else city_deck_name(x))
   st.caption('勝率＝確認できた決勝トーナメントの勝利数 ÷ 試合数。同型対戦は除外。ごく少数の決勝戦だけなので、予選を含むデッキの総合勝率ではありません。')
   if chosen_deck=='すべて':
    by_deck=[]
    for deck_id,g in observations.groupby('deck'):
     by_deck.append({'デッキ':city_deck_name(deck_id),
                     '勝利':int(g.win.sum()),'敗北':int(g.loss.sum()),
                     '引き分け':int(g.draw.sum()),**stats(g)})
    ranking=pd.DataFrame(by_deck).sort_values(['試合数','勝率'],ascending=[False,False])
    ranking=ranking[['デッキ','勝利','敗北','引き分け','試合数','勝率','95%下限','95%上限']]
    st.dataframe(ranking,use_container_width=True,hide_index=True)
    st.download_button('国内大会の確認済みデッキ別勝率CSV',
                       ranking.to_csv(index=False).encode('utf-8-sig'),
                       file_name='japan_tournament_winrates.csv',key='domestic_winrates')
   else:
    focus=observations[observations.deck==chosen_deck]
    shown=stats(focus)
    v1,v2,v3=st.columns(3)
    v1.metric('確認済み勝率',f"{shown['勝率']}%")
    v2.metric('勝敗',f"{int(focus.win.sum())}勝{int(focus.loss.sum())}敗")
    v3.metric('対戦数',f"{len(focus)}試合")
    pairs=[]
    for other,g in focus.groupby('opponent'):
     pairs.append({'相手デッキ':city_deck_name(other),'勝利':int(g.win.sum()),
                   '敗北':int(g.loss.sum()),'引き分け':int(g.draw.sum()),
                   **stats(g)})
    detail=pd.DataFrame(pairs).sort_values('試合数',ascending=False)
    st.dataframe(detail,use_container_width=True,hide_index=True)
    st.download_button('国内大会の確認済み対面勝率CSV',
                       detail.to_csv(index=False).encode('utf-8-sig'),
                       file_name='japan_matchup_winrates.csv',key='domestic_matchups')
   with st.expander('勝敗を確認した大会と対戦カード'):
    proof=pd.DataFrame(nonmirrors)
    proof['勝者デッキ']=proof.apply(
     lambda row: city_deck_name(row.deck_a if row.winner=='a' else row.deck_b),axis=1)
    proof['敗者デッキ']=proof.apply(
     lambda row: city_deck_name(row.deck_b if row.winner=='a' else row.deck_a),axis=1)
    proof=proof.rename(columns={'date':'開催日','event_type':'大会区分',
                                'stage':'ラウンド','event_name':'会場','source_url':'出典URL'})
    st.dataframe(proof[['開催日','大会区分','ラウンド','会場','勝者デッキ','敗者デッキ','出典URL']],
                 use_container_width=True,hide_index=True,
                 column_config={'出典URL':st.column_config.LinkColumn('大会結果')})
  else:
   st.info('この条件では、勝敗と相手デッキが両方判明した異なるデッキ同士の対戦がありません。')
  st.divider()
  known=city[city.deck.str.strip().ne('')].copy()
  known['デッキ']=known.deck.map(city_deck_name)
  if not known.empty:
   st.subheader('入賞デッキの掲載数')
   summary=known.groupby('デッキ').agg(入賞記録数=('key','size'),掲載大会数=('event_url','nunique')).reset_index().sort_values('入賞記録数',ascending=False)
   st.dataframe(summary,use_container_width=True,hide_index=True)
   st.caption(f'デッキ名を特定できた {len(known):,} 件のみ。全参加者の使用率や対面勝率ではありません。')
  else:
   st.warning('この条件ではデッキ名が判明した入賞情報がありません。')
  st.subheader('大会ごとの入賞結果')
  shown=city.copy()
  shown['デッキ']=shown.deck.map(lambda x: city_deck_name(x) if x else '不明')
  shown=shown.rename(columns={'date':'開催日','prefecture':'都道府県','shop':'店舗','rank':'順位','player':'プレイヤー','event_url':'大会URL','decklist_url':'デッキリストURL'})
  st.dataframe(shown[['開催日','都道府県','店舗','順位','デッキ','プレイヤー','大会URL','デッキリストURL']],use_container_width=True,hide_index=True,
               column_config={'大会URL':st.column_config.LinkColumn('大会ページ'),'デッキリストURL':st.column_config.LinkColumn('デッキリスト')})
  st.caption('シティリーグとLimitless Playのオンライン試合は別の集計源です。勝率表にシティリーグ入賞件数を混ぜません。')
 except (OSError,ValueError,KeyError,TypeError) as exc:
  st.error(f'シティリーグ結果を読み込めませんでした: {exc}')
 st.stop()
with st.sidebar:
 st.header('データ管理')
 st.info('公開Web版ではデータの保存が永続的とは限りません。Streamlit Community Cloudでは再起動時にSQLiteの内容が失われる可能性があります。')
 if not WRITES_ENABLED:
  st.info('公開閲覧モードです。データ同期・CSV取込は管理者が有効化した場合のみ利用できます。')
 st.subheader('Limitless データ同期')
 sync_count=st.number_input('同期する大会数（最大5）',min_value=1,max_value=5,value=2)
 if st.button('公開APIから大会を同期',disabled=not WRITES_ENABLED,help='実際のAPI仕様・通信状況により失敗する場合があります。'):
  with st.spinner('大会データを取得しています…'):
   try:
    result=subprocess.run([sys.executable,str(ROOT/'limitless_sync.py'),'--pages','1','--max-tournaments',str(sync_count),'--delay','1.5','--max-seconds','120'],capture_output=True,text=True,timeout=180,env=os.environ.copy())
    if result.returncode: st.error('同期に失敗しました。');st.code((result.stderr or result.stdout)[-2500:])
    else:
     st.code(result.stdout[-3000:]);st.cache_data.clear();st.rerun()
   except subprocess.TimeoutExpired:st.error('同期がタイムアウトしました。')
 upload=st.file_uploader('対戦データCSVを読み込む',type='csv')
 if upload and st.button('インポート',type='primary',disabled=not WRITES_ENABLED):
  try:st.success(f'{load_csv(upload)} 行を検査・取り込み（重複IDは無視）');st.cache_data.clear();st.rerun()
  except Exception as e:st.error(str(e))
 st.download_button('CSVひな形を取得','id,event,played_at,deck_a,deck_b,winner,decklist_a,decklist_b,source\nexample-001,Example,2026-10-01,Deck A,Deck B,a,"{""Card X"":2}","{""Card Y"":3}",manual\n',file_name='match_template.csv',mime='text/csv')
 st.caption('勝者 winner は a / b / draw。カードリストはJSON辞書（カード名:枚数）。CSVのIDは試合ごとに一意にしてください。')
 st.caption('Limitless Playの公開API同期: `python limitless_sync.py` を実行してください。取得できないデッキ・対戦は集計から除外します。')
# Hosted deployments load the latest GitHub Actions snapshot first.
snapshot=ROOT/'matches_snapshot.csv'
if snapshot.exists():
 try:
  df=pd.read_csv(snapshot,dtype=str).fillna('')
  st.success(f'Limitless実データ: {len(df):,} 試合を読み込みました（公開API由来）')
  # Show actual collection coverage rather than implying the whole season is present.
  progress_file = ROOT / 'sync_state.json'
  if progress_file.exists():
   try:
    progress = json.loads(progress_file.read_text(encoding='utf-8'))
    report = progress.get('last_sync', {})
    tournaments = progress.get('events', {})
    discovered = report.get('discovered_tournaments', len(tournaments))
    checked = report.get('checked_tournaments', sum(bool(t.get('checked')) for t in tournaments.values()))
    oldest = report.get('oldest_match_date') or str(df.played_at.min())[:10]
    boundary = '9月1日まで大会一覧を探索済み' if progress.get('season_boundary_seen') else '過去大会を探索中'
    st.caption(f'収集状況：大会 {checked:,} / {discovered:,} 件を確認済み・最古の保存試合 {oldest}・{boundary}（全試合取得完了を意味しません）')
   except (OSError, ValueError, TypeError, KeyError):
    pass
 except Exception as exc:
  st.error(f'スナップショットの読み込みに失敗: {exc}')
  df=pd.read_sql_query('SELECT * FROM games',c)
else:
 df=pd.read_sql_query('SELECT * FROM games',c)
if df.empty:
 demo_path=ROOT/'demo_synthetic.csv'
 if demo_path.exists():
  st.warning('デモモード：以下は架空の試合データです。Limitlessの実際の勝率ではありません。')
  df=pd.read_csv(demo_path,dtype=str).fillna('')
if df.empty:
 st.warning('まだ対戦データがありません。左側からCSVを読み込むと分析が始まります。')
 st.markdown('### できること\n- デッキ別の全対面勝率と95%信頼区間\n- 対面を指定した詳細分析\n- カード採用有無・採用枚数ごとの勝率比較\n- 大会名・期間による絞り込み\n- 集計結果のCSV出力')
 st.stop()
# Country annotations are a separate snapshot so the original match CSV,
# historical match keys, and exports never change.
country_file=ROOT/'match_countries.csv'
df=df.drop(columns=['country_a','country_b'],errors='ignore')
if country_file.exists():
 try:
  country_frame=pd.read_csv(country_file,dtype=str,keep_default_na=False)
  if list(country_frame.columns)!=['id','country_a','country_b']:
   raise ValueError('国情報CSVの列が一致しません')
  df=df.merge(country_frame,on='id',how='left',validate='one_to_one')
 except (OSError,ValueError,KeyError) as exc:
  st.warning(f'国別データの読み込みに失敗したため、国情報を不明として表示します: {exc}')
  df['country_a']='';df['country_b']=''
else:
 df['country_a']='';df['country_b']=''
df[['country_a','country_b']]=df[['country_a','country_b']].fillna('')
known_sides=int(df.country_a.map(lambda x: country_group(x)!='不明').sum()+df.country_b.map(lambda x: country_group(x)!='不明').sum())
st.caption(f'登録国を確認できたプレイヤー視点: {known_sides:,} / {2*len(df):,} 件。国情報の追加収集は毎日の自動同期で進みます。')
st.caption('地域分類はLimitlessに登録された各プレイヤーの国です。日本国内開催の大会を特定する機能ではありません。国未登録の参加者は「国不明」に分類します。')

with st.expander('集計条件',expanded=True):
 split_hammer=st.checkbox('ドラパルトをクラハン採用・非採用で分ける',value=True,
                          help='通常の「Dragapult」のみ、デッキリストにクラッシュハンマーが1枚以上あればクラハンドラパと判定します。リストが不明な試合は別区分として表示します。')
 if split_hammer:
  # The original match snapshot stays unchanged: classification applies
  # only to these in-memory columns and to BOTH sides of the pairing.
  df=df.copy()
  for side in ('a','b'):
   deck_column='deck_'+side
   list_column='decklist_'+side
   mask=df[deck_column].eq('Dragapult')
   if mask.any():
    df.loc[mask,deck_column]=df.loc[mask,list_column].map(
     lambda value:classify_dragapult('Dragapult',normalize_list(value)))
  st.caption('クラハンドラパ＝クラッシュハンマー1枚以上採用の通常ドラパルト。非採用・リスト不明は別表示。ドラパルト・ヨノワール等の派生型は従来の名前のままです。')
 region=st.selectbox('分析する地域（プレイヤー登録国）',['すべて','国内','海外','国内同士','国不明'],help='国内＝日本登録プレイヤー、海外＝日本以外の登録プレイヤー、国内同士＝対戦者双方が日本登録。開催地や実際の地域大会を意味しません。')
 e=sorted(x for x in df.event.unique() if x)
 events=st.multiselect('大会',e,default=e)
 if events:df=df[df.event.isin(events)]
 dates=pd.to_datetime(df.played_at,errors='coerce')
 if dates.notna().any():
  lo=dates.min().date();hi=dates.max().date();period=st.date_input('開催期間',(lo,hi),min_value=lo,max_value=hi)
  if isinstance(period,tuple) and len(period)==2:df=df[(dates.dt.date>=period[0])&(dates.dt.date<=period[1])]
 decks=available_decks(df,region)
 if not decks:st.warning('条件に一致する試合がありません');st.stop()
 deck=st.selectbox('分析するデッキ',decks,format_func=deck_name)
p=perspective(df,deck,region)
if p.empty:st.warning('この地域の条件に一致する試合がありません。地域を「すべて」に変更してみてください。');st.stop()
allopp=sorted(p.opponent.unique(),key=deck_name);opp=st.selectbox('対面を選択',['すべて']+allopp,format_func=deck_name)
if opp!='すべて':p=p[p.opponent==opp]
s=stats(p);m1,m2,m3=st.columns(3);m1.metric('勝率',f"{s['勝率']}%");m2.metric('試合数',f"{s['試合数']:,}");m3.metric('95%信頼区間',f"{s['95%下限']}–{s['95%上限']}%")
st.subheader('国内・海外の成績比較')
comparison=perspective(df,deck)
region_rows=[]
for region_name in ('国内','海外','不明'):
 subgroup=comparison[comparison.player_country.map(country_group)==region_name]
 if not subgroup.empty:
  region_rows.append({'登録国区分':region_name,**stats(subgroup)})
if region_rows:
 st.dataframe(pd.DataFrame(region_rows),use_container_width=True,hide_index=True)
else:
 st.info('このデッキで比較できる登録国データはありません。')
st.caption('同じオンライン大会に参加した国内・海外登録者を、それぞれのプレイヤー視点で集計しています。国内大会と海外大会を区別した統計ではありません。')
st.subheader('対面別勝率')
matchup_sort=st.selectbox('対面表の並び替え',MATCHUP_SORT_OPTIONS,key='matchup_sort_order',help='勝率の高い順・低い順、試合数の多い順・少ない順を選べます。')
matchup_rows=[{'対面':name,**stats(g)} for name,g in p.groupby('opponent')]
summary=pd.DataFrame(sort_matchup_rows(matchup_rows,matchup_sort))
display_summary=summary.assign(対面=summary['対面'].map(deck_name))
st.dataframe(display_summary,use_container_width=True,hide_index=True)
st.bar_chart(display_summary.set_index('対面')['勝率'])
st.download_button('対面別集計CSV',summary.to_csv(index=False).encode('utf-8-sig'),file_name='matchups.csv')
st.caption('勝率順に並び替える際は試合数も確認してください。少数試合では勝率が大きくぶれることがあります。')
st.subheader('採用カード別の分析')
p=p.copy();p['parsed_cards']=p.cards.apply(lambda x:normalize_list(x))
cardnames=sorted({k for d in p.parsed_cards for k in d})
if not cardnames:st.info('対象試合にデッキリストがありません。デッキリスト付きCSVを取り込むと利用できます。')
else:
 card=st.selectbox('比較するカード',cardnames)
 known=p[p.parsed_cards.map(bool)].copy()
 known['枚数']=known.parsed_cards.apply(lambda d:d.get(card,0))
 compare=pd.DataFrame([{'採用枚数':int(n),**stats(g)} for n,g in known.groupby('枚数')]).sort_values('採用枚数')
 st.dataframe(compare,use_container_width=True,hide_index=True)
 st.bar_chart(compare.set_index('採用枚数')['勝率'])
 yes=known[known['枚数']>0];no=known[known['枚数']==0]
 if len(yes) and len(no):st.metric('採用 vs 不採用 勝率差',f"{stats(yes)['勝率']-stats(no)['勝率']:+.1f} pt")
 st.caption(f'カードリストが判明している {len(known):,} 試合を対象。デッキリストが不明な試合は採用比較から除外。勝率差は因果効果ではありません。')
 st.download_button('採用枚数別集計CSV',compare.to_csv(index=False).encode('utf-8-sig'),file_name='card_comparison.csv')
st.caption('注意：同名デッキ同士のミラーマッチは両視点で集計されます。引き分けは0.5勝相当。Wilson区間は近似値です。')

# v0.2: デッキ間マトリクスとカード影響ランキング
st.divider()
st.subheader('全デッキ対面マトリクス')
min_games=st.slider('マトリクスの最低試合数',1,100,5)
rows=[]
for name in sorted(set(df.deck_a)|set(df.deck_b)):
 q=perspective(df,name,region)
 for other,g in q.groupby('opponent'):
  if len(g)>=min_games:
   rows.append({'自分':name,'相手':other,'勝率':stats(g)['勝率'],'試合数':len(g)})
if rows:
 matrix=pd.DataFrame(rows).pivot(index='自分',columns='相手',values='勝率')
 display_matrix=matrix.rename(index=deck_name,columns=deck_name)
 # pandas Styler.background_gradient requires optional matplotlib and
 # crashes on Streamlit Cloud where that package is not installed.
 # Styler.map uses only our pure-Python CSS colors.
 st.dataframe(display_matrix.style.format('{:.1f}%',na_rep='—').map(matrix_cell_css),use_container_width=True)
 st.download_button('マトリクスCSV',matrix.to_csv().encode('utf-8-sig'),file_name='matchup_matrix.csv')
else:st.info('条件に合うデッキ対面がありません。')
st.divider()
st.subheader('採用カード影響ランキング')
st.caption('選択中のデッキ・対面・期間に対し、採用と不採用の双方に十分な試合数があるカードを比較します。')
min_sample=st.slider('採用・不採用それぞれの最低試合数',5,200,20,5)
known=p[p.parsed_cards.map(bool)].copy() if 'parsed_cards' in p.columns else pd.DataFrame()
if not known.empty:
 allcards=sorted({k for d in known.parsed_cards for k in d})
 impacts=[]
 for cardname in allcards:
  flag=known.parsed_cards.map(lambda d:d.get(cardname,0)>0)
  yes=known[flag];no=known[~flag]
  if len(yes)>=min_sample and len(no)>=min_sample:
   impacts.append({'カード':cardname,'採用時勝率':stats(yes)['勝率'],'不採用時勝率':stats(no)['勝率'],
                   '勝率差(pt)':round(stats(yes)['勝率']-stats(no)['勝率'],1),
                   '採用試合数':len(yes),'不採用試合数':len(no)})
 if impacts:
  impact_df=pd.DataFrame(impacts).sort_values('勝率差(pt)',ascending=False)
  st.dataframe(impact_df,use_container_width=True,hide_index=True)
  st.download_button('カード影響ランキングCSV',impact_df.to_csv(index=False).encode('utf-8-sig'),file_name='card_impact.csv')
 else:st.info('採用・不採用の両方に十分な試合数があるカードはありません。')
else:st.info('カードリストがある試合が必要です。')
