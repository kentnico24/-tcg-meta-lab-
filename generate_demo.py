"""架空データを作成。実大会データとは混ぜず、画面の動作確認専用。"""
import csv,json,random,pathlib
random.seed(42)
root=pathlib.Path(__file__).parent
out=root/'demo_synthetic.csv'
decks=['Deck Alpha','Deck Beta','Deck Gamma','Deck Delta']
with out.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['id','event','played_at','deck_a','deck_b','winner','decklist_a','decklist_b','source'])
 for i in range(1200):
  a,b=random.sample(decks,2)
  def cards():
   return {'Core Card':4,'Tech Card':random.choice([0,0,1,2]),'Support Card':random.choice([2,3,4])}
  ca,cb=cards(),cards()
  strength={'Deck Alpha':.08,'Deck Beta':.04,'Deck Gamma':-.03,'Deck Delta':-.09}
  prob=max(.05,min(.95,.5+strength[a]-strength[b]+(.035 if ca['Tech Card'] else 0)-(.035 if cb['Tech Card'] else 0)))
  w.writerow([f'DEMO-{i:05d}','SYNTHETIC DEMO','2026-10-01',a,b,'a' if random.random()<prob else 'b',json.dumps(ca),json.dumps(cb),'SYNTHETIC-NOT-REAL'])
print(out)
