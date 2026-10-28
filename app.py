import sqlite3, json, math, pathlib, io, os, subprocess, sys
from datetime import datetime
import pandas as pd
import streamlit as st
from deck_names import deck_name
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
def perspective(df,deck):
 a=df[df.deck_a==deck].copy();b=df[df.deck_b==deck].copy()
 a['opponent']=a.deck_b;a['result']=a.winner.map({'a':1.,'b':0.,'draw':.5});a['cards']=a.decklist_a
 b['opponent']=b.deck_a;b['result']=b.winner.map({'a':0.,'b':1.,'draw':.5});b['cards']=b.decklist_b
 return pd.concat([a,b],ignore_index=True)
def stats(g):
 n=len(g);w=float(g.result.sum());lo,hi=wilson(w,n)
 return {'試合数':n,'勝率':round(w/n*100,1) if n else 0,'95%下限':round(lo*100,1),'95%上限':round(hi*100,1),'勝ち相当':w}
st.title('🃏 TCG Meta Lab')
st.caption('Android / PC 対応 Web版 v0.7')
st.caption('デッキ・対面・採用カードを横断する独立型リサーチアプリ | 実データのみを集計')
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
with st.expander('集計条件',expanded=True):
 e=sorted(x for x in df.event.unique() if x)
 events=st.multiselect('大会',e,default=e)
 if events:df=df[df.event.isin(events)]
 dates=pd.to_datetime(df.played_at,errors='coerce')
 if dates.notna().any():
  lo=dates.min().date();hi=dates.max().date();period=st.date_input('開催期間',(lo,hi),min_value=lo,max_value=hi)
  if isinstance(period,tuple) and len(period)==2:df=df[(dates.dt.date>=period[0])&(dates.dt.date<=period[1])]
 decks=sorted(set(df.deck_a)|set(df.deck_b),key=deck_name)
 if not decks:st.warning('条件に一致する試合がありません');st.stop()
 deck=st.selectbox('分析するデッキ',decks,format_func=deck_name)
p=perspective(df,deck)
if p.empty:st.warning('対象試合がありません');st.stop()
allopp=sorted(p.opponent.unique(),key=deck_name);opp=st.selectbox('対面を選択',['すべて']+allopp,format_func=deck_name)
if opp!='すべて':p=p[p.opponent==opp]
s=stats(p);m1,m2,m3=st.columns(3);m1.metric('勝率',f"{s['勝率']}%");m2.metric('試合数',f"{s['試合数']:,}");m3.metric('95%信頼区間',f"{s['95%下限']}–{s['95%上限']}%")
st.subheader('対面別勝率')
summary=pd.DataFrame([{'対面':name,**stats(g)} for name,g in p.groupby('opponent')]).sort_values('試合数',ascending=False)
display_summary=summary.assign(対面=summary['対面'].map(deck_name))
st.dataframe(display_summary,use_container_width=True,hide_index=True)
st.bar_chart(display_summary.set_index('対面')['勝率'])
st.download_button('対面別集計CSV',summary.to_csv(index=False).encode('utf-8-sig'),file_name='matchups.csv')
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
 q=perspective(df,name)
 for other,g in q.groupby('opponent'):
  if len(g)>=min_games:
   rows.append({'自分':name,'相手':other,'勝率':stats(g)['勝率'],'試合数':len(g)})
if rows:
 matrix=pd.DataFrame(rows).pivot(index='自分',columns='相手',values='勝率')
 display_matrix=matrix.rename(index=deck_name,columns=deck_name)
 st.dataframe(display_matrix.style.format('{:.1f}%',na_rep='—').background_gradient(cmap='RdYlGn',vmin=0,vmax=100),use_container_width=True)
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
