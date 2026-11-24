import json,time,secrets,threading,random
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
rooms={}; lock=threading.RLock()
def finish_turn(r,hit,now):
 i=r['turn'];r['hits'][i]=hit
 if i==r['first']:
  r['turn']=1-i;r['deadline']=now+60;return
 if all(r['hits']):
  r.update(phase='rps',choices=[None,None],rps_round=1,rps_last=None,deadline=0)
 elif any(r['hits']):
  r.update(phase='end',winner=r['hits'].index(True),deadline=0)
 else:
  r.update(turn=r['first'],hits=[False,False],deadline=now+60)
def tick(r):
 while r['phase']=='play' and time.time()>=r['deadline']:
  r['history'].append([r['turn'],None,None]);finish_turn(r,False,r['deadline'])
class H(BaseHTTPRequestHandler):
 def send(self,x,status=200):
  b=json.dumps(x,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path.split('?')[0]=='/':
   b=Path(__file__).with_name('index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(b)
  else:self.send({'error':'Not found'},404)
 def do_POST(self):
  try:
   d=json.loads(self.rfile.read(int(self.headers['Content-Length'])));a=d['action']
   with lock:
    if a in ('create','join'):
     name=str(d['name']).strip()[:20];assert name,'请输入昵称'
     if a=='create':
      code=str(secrets.randbelow(900000)+100000)
      while code in rooms:code=str(secrets.randbelow(900000)+100000)
      rooms[code]={'players':[],'phase':'size','history':[],'turn':0,'deadline':0,'winner':None}
     else:code=str(d['code'])
     assert code in rooms,'房间不存在';r=rooms[code];assert len(r['players'])<2,'房间已满'
     token=secrets.token_urlsafe(24);r['players'].append({'name':name,'token':token,'size':None,'secret':None,'again':False});return self.send({'code':code,'token':token})
    r=rooms.get(str(d['code']));assert r,'房间不存在';i=next((i for i,p in enumerate(r['players']) if p['token']==d.get('token')),None);assert i is not None,'身份无效';p=r['players'][i];tick(r)
    if a=='size':
     assert r['phase']=='size','阶段已结束';n=int(d['value']);assert 1<=n<=12,'请选择1至12位';p['size']=n
     if len(r['players'])==2 and all(q['size']==n for q in r['players']):r['phase']='secret'
    elif a=='secret':
     assert r['phase']=='secret' and p['secret'] is None,'不能修改谜底';v=str(d['value']);assert len(v)==p['size'] and v.isascii() and v.isdigit(),'数字格式错误';p['secret']=v
     if all(q['secret'] is not None for q in r['players']):r['phase']='play';r['turn']=random.randrange(2);r['first']=r['turn'];r['hits']=[False,False];r['deadline']=time.time()+60
    elif a=='guess':
     assert r['phase']=='play' and r['turn']==i,'当前不是你的回合';v=str(d['value']);assert len(v)==p['size'] and v.isascii() and v.isdigit(),'数字格式错误';c=sum(x==y for x,y in zip(v,r['players'][1-i]['secret']));r['history'].append([i,v,c])
     finish_turn(r,c==p['size'],time.time())
    elif a=='rps':
     assert r['phase']=='rps' and r['choices'][i] is None,'已出拳或阶段结束';v=d['value'];assert v in ('rock','paper','scissors'),'无效出拳';r['choices'][i]=v
     if all(r['choices']):
      x,y=r['choices'];r['rps_last']=r['choices'][:]
      if x==y:r['choices']=[None,None];r['rps_round']+=1
      else:r.update(phase='end',winner=0 if (x,y) in [('rock','scissors'),('scissors','paper'),('paper','rock')] else 1)
    elif a=='again':
     assert r['phase']=='end','游戏尚未结束';p['again']=True
     if all(q['again'] for q in r['players']):
      for q in r['players']:q.update(size=None,secret=None,again=False)
      r.update(phase='size',history=[],winner=None,deadline=0,choices=[None,None],rps_last=None,rps_round=0,hits=[False,False])
    elif a!='state':raise ValueError('未知操作')
    self.send({'phase':r['phase'],'players':[{k:v for k,v in q.items() if k!='token' and (k!='secret' or j==i or r['phase']=='end')}|{'ready':q['secret'] is not None} for j,q in enumerate(r['players'])],'me':i,'history':r['history'],'turn':r['turn'],'remaining':max(0,r['deadline']-time.time()),'winner':r['winner'],'rps_round':r.get('rps_round',0),'rps_last':r.get('rps_last') if r['phase'] in ('rps','end') else None,'rps_ready':r.get('choices',[None,None])[i] is not None,'pending_hit':r['phase']=='play' and any(r.get('hits',[]))})
  except Exception as e:self.send({'error':str(e) or '操作失败'},400)
if __name__=='__main__':
 import os
 ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT',8000))),H).serve_forever()
