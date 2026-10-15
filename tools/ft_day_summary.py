"""Offline daily passage totals; incomplete recordings never become a full day."""
import csv
import datetime as dt
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
import stat

from tools.ft_count import ValidationError, _require, _outside_repo

HEX = re.compile(r'[a-f0-9]{64}\Z')
PERIODS = [('night','กลางคืน',0,21600),('morning','เช้า',21600,39600),
           ('midday','กลางวัน',39600,54000),('evening','เย็น/ค่ำ',54000,86400)]
MAX_EVENTS = 100000
MAX_BYTES = 32*1024*1024


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def number(v):
    return type(v) in (int,float) and math.isfinite(v)


def parse_time(value, end=False):
    _require(isinstance(value,str) and re.fullmatch(r'\d{2}:\d{2}',value), 'invalid time filter')
    h,m=map(int,value.split(':'))
    _require(0<=m<60 and (0<=h<24 or (end and h==24 and m==0)), 'invalid time filter')
    return h*3600+m*60


def validate_ledger(data):
    _require(isinstance(data,dict) and data.get('schema_version')==1 and type(data['schema_version']) is int,
             'invalid day ledger')
    date=data.get('date')
    _require(isinstance(date,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',date), 'invalid day')
    try: dt.date.fromisoformat(date)
    except ValueError: raise ValidationError('invalid day') from None
    _require(data.get('timezone')=='+07:00', 'Bangkok timezone required')
    _require(isinstance(data.get('config_sha256'),str) and HEX.fullmatch(data['config_sha256']), 'invalid day config hash')
    _require(type(data.get('inventory_complete')) is bool, 'inventory completeness required')
    _require(data.get('boundary_mode') in ('continuous_state','unverified'), 'invalid boundary evidence')
    if data['inventory_complete']:
        _require(isinstance(data.get('inventory_digest'),str) and HEX.fullmatch(data['inventory_digest']), 'inventory digest required')
    clips=data.get('clips')
    _require(isinstance(clips,list) and len(clips)<=4000, 'invalid day clips')
    unique={}; event_total=0
    for clip in clips:
        _require(isinstance(clip,dict) and isinstance(clip.get('ref'),str) and HEX.fullmatch(clip['ref']), 'invalid source ref')
        a,b=clip.get('start'),clip.get('end')
        _require(number(a) and number(b) and 0<=a<b<=86400, 'source outside day')
        if 'capture_start' in clip or 'capture_end' in clip:
            cs,ce=clip.get('capture_start'),clip.get('capture_end')
            _require(type(cs) is int and type(ce) is int and -180<=cs<ce<=86580
                     and a==max(0,cs) and b==min(86400,ce), 'invalid midnight source context')
        _require(clip.get('status') in ('pending','counted','covered','error','unsupported'), 'invalid source status')
        if clip['ref'] in unique:
            _require(clip==unique[clip['ref']], 'conflicting source ref')
            continue
        unique[clip['ref']]=clip
        events=clip.get('events',[])
        _require(isinstance(events,list), 'invalid source events')
        _require(clip['status'] in ('counted','covered') or not events, 'uncounted source has events')
        if clip['status'] in ('counted','covered'):
            _require(clip.get('config_sha256')==data['config_sha256'], 'mixed day configurations')
            _require(isinstance(clip.get('input_sha256'),str) and HEX.fullmatch(clip['input_sha256']), 'input hash required')
            _require(type(clip.get('clock_verified')) is bool and type(clip.get('lens_verified')) is bool,
                     'source verification flags required')
            _require(clip['status']!='covered' or not events, 'covered duplicate has events')
        seen={}
        for event in events:
            _require(isinstance(event,dict) and isinstance(event.get('ref'),str) and HEX.fullmatch(event['ref']), 'invalid event ref')
            _require(number(event.get('at')) and a<=event['at']<b, 'event outside source half-open interval')
            _require(event.get('zone') in ('front_shop','water_side') and event.get('status') in ('accepted','review'), 'invalid event kind')
            _require(event.get('lane') in ('near','far') if event['zone']=='front_shop' else event.get('lane') is None,
                     'invalid event lane')
            if event['ref'] in seen: _require(seen[event['ref']]==event,'conflicting event ref')
            else: event_total+=1
            seen[event['ref']]=event
        _require(event_total<=MAX_EVENTS, 'day event quota exceeded')
    ordered=sorted(unique.values(),key=lambda c:(c['start'],c['end'],c['ref']))
    spans=[]
    for clip in ordered:
        if clip['status']=='covered':
            _require(any(a<=clip['start'] and b>=clip['end'] for a,b in spans), 'covered source has no counted owner')
        if clip['status']=='counted':
            if spans and clip['start']<=spans[-1][1]:spans[-1]=(spans[-1][0],max(spans[-1][1],clip['end']))
            else:spans.append((clip['start'],clip['end']))
    return ordered


def owned_events(clips):
    """Earliest counted footage owns overlap; half-open ownership is deterministic."""
    covered=0; result=[]; seen={}
    for clip in clips:
        if clip['status'] not in ('counted','covered'):continue
        lo=max(clip['start'],covered)
        for event in clip.get('events',[]):
            if event['at']<lo:continue
            if event['ref'] in seen:
                _require(seen[event['ref']]==event, 'conflicting day event ref')
                continue
            seen[event['ref']]=event; result.append(event)
        covered=max(covered,clip['end'])
    return sorted(result,key=lambda e:(e['at'],e['ref']))


def query(data, start=0, end=86400):
    _require(number(start) and number(end) and 0<=start<end<=86400,'invalid day filter')
    clips=validate_ledger(data)
    events=[e for e in owned_events(clips) if start<=e['at']<end]
    totals=dict(near=0,far=0,front=0,front_review=0,shop_side=0,shop_side_review=0)
    for e in events:
        if e['zone']=='front_shop':
            if e['status']=='review':totals['front_review']+=1
            else:totals['front']+=1;totals[e['lane']]+=1
        elif e['status']=='review':totals['shop_side_review']+=1
        else:totals['shop_side']+=1
    expected=[c for c in clips if c['start']<end and c['end']>start]
    processed=[c for c in expected if c['status'] in ('counted','covered')]
    verified=all(c.get('clock_verified') and c.get('lens_verified') for c in processed)
    status=('PARTIAL_INVENTORY' if not data['inventory_complete'] else
            'PARTIAL_PROCESSING' if len(processed)!=len(expected) else
            'UNVERIFIED_SOURCE' if not verified or data['boundary_mode']!='continuous_state' else 'COMPLETE_RECORDINGS')
    return dict(date=data['date'],timezone='+07:00',start=start,end=end,totals=totals,
                data_status=status,expected_clips=len(expected),processed_clips=len(processed),
                full_day_complete=status=='COMPLETE_RECORDINGS' and start==0 and end==86400,
                accuracy_status='NOT_VERIFIED',counts_are_partial=status!='COMPLETE_RECORDINGS')


def visible(q,key):
    return str(q['totals'][key]) if q['processed_clips'] or not q['counts_are_partial'] else '—'


def status_text(q):
    return ('ประมวลผลรายการคลิปครบในช่วงนี้ · ความแม่นยำยังไม่ยืนยัน' if not q['counts_are_partial'] else
            'ข้อมูลยังไม่ครบหรือเวลา/เลนส์ยังไม่ยืนยัน · ตัวเลขนี้เป็นยอดบางส่วน ไม่ใช่ยอดครบวัน')


def read_ledger(path):
    _outside_repo(path);s=os.lstat(path)
    _require(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077 and s.st_size<=MAX_BYTES,
             'private day ledger required')
    def pairs(items):
        result={}
        for k,v in items:
            _require(k not in result,'duplicate ledger key');result[k]=v
        return result
    data=json.loads(Path(path).read_text(),object_pairs_hook=pairs,
                    parse_constant=lambda _:(_ for _ in ()).throw(ValidationError('invalid JSON number')))
    validate_ledger(data);return data


def atomic_write(path, text):
    path=Path(path);_outside_repo(path);parent=path.parent
    s=parent.lstat();_require(stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077,'private report folder required')
    _require(not any(p.is_symlink() for p in (parent,*parent.parents)), 'symlink report folder refused')
    if path.exists() or path.is_symlink():
        s=path.lstat();_require(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and s.st_nlink==1 and not s.st_mode&0o077,'unsafe existing report')
    temp=path.with_name(path.name+'.part')
    fd=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()


def write_reports(root, data):
    """Export only anonymous numeric/time data, never paths, boxes or identities."""
    clips=validate_ledger(data);whole=query(data)
    rows=[('ทั้งวัน',0,86400)]+[(name,a,b) for _,name,a,b in PERIODS]
    rows += [(f'{h:02d}:00–{h+1:02d}:00',h*3600,(h+1)*3600) for h in range(24)]
    buf=io.StringIO();writer=csv.writer(buf)
    writer.writerow(['date','period','start','end','near','far','front_auto','front_review','shop_side','shop_side_review','data_status'])
    for name,a,b in rows:
        q=query(data,a,b);t=q['totals']
        writer.writerow([data['date'],name,f'{a//3600:02d}:{a%3600//60:02d}',f'{b//3600:02d}:{b%3600//60:02d}',
                         *[visible(q,k) for k in ('near','far','front','front_review','shop_side','shop_side_review')],q['data_status']])
    atomic_write(Path(root)/'summary.csv','\ufeff'+buf.getvalue())
    public=dict(date=data['date'],inventory_complete=data['inventory_complete'],boundary_mode=data['boundary_mode'],
                clips=[{k:c.get(k) for k in ('start','end','status','clock_verified','lens_verified')} for c in clips],
                events=[{k:e.get(k) for k in ('at','zone','lane','status')} for e in owned_events(clips)])
    payload=json.dumps(public,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    page=HTML.replace('__DATE__',html.escape(data['date'])).replace('__DATA__',payload)
    initial_rows=[]
    for h in range(24):
        q=query(data,h*3600,(h+1)*3600)
        initial_rows.append('<tr><td>%02d:00–%02d:00</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %
                            (h,h+1,visible(q,'front'),visible(q,'front_review'),visible(q,'shop_side'),
                             'รายการครบ' if not q['counts_are_partial'] else 'บางส่วน/ไม่ทราบ'))
    for marker,value in [('__FRONT__',visible(whole,'front')),('__REVIEW__',visible(whole,'front_review')),
                         ('__SIDE__',visible(whole,'shop_side')),('__LANES__','ช่องใกล้ '+visible(whole,'near')+' / ช่องไกล '+visible(whole,'far')),
                         ('__STATUS__',status_text(whole)),('__HOURS__',''.join(initial_rows))]:
        page=page.replace(marker,value)
    atomic_write(Path(root)/'summary.html',page)
    atomic_write(Path(root)/'summary.json',json.dumps(whole,ensure_ascii=False,indent=2))
    return whole


HTML='''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'">
<title>นับคนรายวัน __DATE__</title><style>body{font:16px system-ui;margin:0;background:#eef3f7;color:#172b3b}main{max-width:1000px;margin:auto;padding:20px}h1{font-size:25px}section{background:white;padding:18px;border-radius:14px;margin:15px 0}label{display:inline-block;margin:8px}select,input,button{font:inherit;padding:8px;border:1px solid #9cabb8;border-radius:7px}.cards{display:flex;flex-wrap:wrap;gap:10px}.card{background:#edf4fa;border-radius:10px;padding:16px;flex:1;min-width:125px}.n{font-size:30px;font-weight:700}.warn{background:#fff2d9;padding:14px;border-radius:10px}table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #dae2e9;text-align:left}.scroll{overflow:auto}small{color:#526272}</style>
<main><h1>จำนวนคนเดินผ่าน · __DATE__</h1><p>เวลาไทย · แยกโซน · นับครั้งที่เดินผ่าน ไม่ใช่จำนวนคนไม่ซ้ำ</p>
<section><label>ช่วงเวลา <select id="preset"><option value="0,86400">ทั้งวัน</option><option value="21600,39600">เช้า 06–11 น.</option><option value="39600,54000">กลางวัน 11–15 น.</option><option value="54000,86400">เย็น/ค่ำ 15–24 น.</option><option value="0,21600">กลางคืน 00–06 น.</option><option value="custom">กำหนดเอง</option></select></label><br>
<label>เริ่ม <input id="start" type="time" value="00:00"></label><label>ถึง <input id="end" type="time" value="23:59"></label><label><input id="midnight" type="checkbox" checked>ถึงสิ้นวัน (24:00)</label><button id="apply">ดูช่วงนี้</button>
<p id="range">00:00 – 24:00 น.</p><div id="status" class="warn">__STATUS__</div></section>
<section class="cards"><div class="card">หน้าร้าน ผ่านเกณฑ์<div class="n" id="front">__FRONT__</div><small id="lanes">__LANES__</small></div><div class="card">หน้าร้าน รอตรวจ<div class="n" id="review">__REVIEW__</div></div><div class="card">ข้างร้าน<div class="n" id="side">__SIDE__</div></div></section>
<section><h2>แยกชั่วโมง</h2><div class="scroll"><table><thead><tr><th>เวลา</th><th>หน้าร้าน</th><th>รอตรวจ</th><th>ข้างร้าน</th><th>ข้อมูล</th></tr></thead><tbody id="hours">__HOURS__</tbody></table></div></section>
<section><p>รอตรวจยังไม่รวมในยอดผ่านเกณฑ์ อาจเป็นคนเดินจริงหรือการติดตามคลาดเคลื่อน ไม่รวมยอดสองโซนเป็นคนไม่ซ้ำ</p><p>“รายการครบ” หมายถึงประมวลผลคลิปที่พบครบ ไม่ใช่ยืนยันความแม่นยำของการนับ ช่องว่างที่ไม่มีคลิปใช้เงื่อนไขกล้องบันทึกเมื่อมีคนตามที่เจ้าของยืนยัน</p><small>รายงานนี้ทำงานในเครื่อง ไม่มีการเชื่อมต่อภายนอก หากแอปมือถือไม่เปิดปุ่มโต้ตอบ ตัวเลขทั้งวันและตารางยังดูได้ หรือใช้ไฟล์ CSV คู่กัน</small></section>
<noscript><section class="warn">แอปนี้ไม่เปิด JavaScript โปรดเปิด summary.csv เพื่อดูตัวเลขและช่วงเวลา</section></noscript>
<script type="application/json" id="data">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent), $=x=>document.getElementById(x);
function q(a,b){let x={near:0,far:0,front:0,review:0,side:0};for(const e of D.events){if(e.at<a||e.at>=b)continue;if(e.zone==='front_shop'){if(e.status==='review')x.review++;else{x.front++;x[e.lane]++;}}else if(e.status==='accepted')x.side++;}let clips=D.clips.filter(c=>c.start<b&&c.end>a),done=clips.filter(c=>['counted','covered'].includes(c.status));x.hasData=done.length>0;x.complete=D.inventory_complete&&clips.length===done.length&&done.every(c=>c.clock_verified&&c.lens_verified)&&D.boundary_mode==='continuous_state';return x;}
function hh(t){return String(Math.floor(t/3600)).padStart(2,'0')+':'+String(Math.floor(t%3600/60)).padStart(2,'0');}
function draw(a,b){if(!(a>=0&&a<b&&b<=86400)){$('status').textContent='ช่วงเวลาไม่ถูกต้อง กรุณาให้เวลาเริ่มน้อยกว่าเวลาสิ้นสุด';return;}let x=q(a,b),n=k=>(x.complete||x.hasData)?x[k]:'—';$('range').textContent=hh(a)+' – '+hh(b)+' น. (ไม่รวมเวลาปลายช่วง)';$('front').textContent=n('front');$('review').textContent=n('review');$('side').textContent=n('side');$('lanes').textContent='ช่องใกล้ '+n('near')+' / ช่องไกล '+n('far');$('status').textContent=x.complete?'ประมวลผลรายการคลิปครบในช่วงนี้ · ความแม่นยำยังไม่ยืนยัน':'ข้อมูลยังไม่ครบหรือเวลา/เลนส์ยังไม่ยืนยัน · ตัวเลขนี้เป็นยอดบางส่วน ไม่ใช่ยอดครบวัน';let rows='';for(let h=Math.floor(a/3600);h<Math.ceil(b/3600);h++){let lo=Math.max(a,h*3600),hi=Math.min(b,(h+1)*3600),v=q(lo,hi);let n=k=>(v.complete||v.hasData)?v[k]:'—';rows+='<tr><td>'+hh(lo)+'–'+hh(hi)+'</td><td>'+n('front')+'</td><td>'+n('review')+'</td><td>'+n('side')+'</td><td>'+(v.complete?'รายการครบ':'บางส่วน/ไม่ทราบ')+'</td></tr>';}$('hours').innerHTML=rows;}
function sec(id){let parts=$(id).value.split(':').map(Number);return parts.length===2?parts[0]*3600+parts[1]*60:NaN;}
$('preset').onchange=()=>{if($('preset').value==='custom')return;let [a,b]=$('preset').value.split(',').map(Number);$('start').value=hh(a);$('end').value=b===86400?'23:59':hh(b);$('midnight').checked=b===86400;draw(a,b);};$('apply').onclick=()=>{$('preset').value='custom';draw(sec('start'),$('midnight').checked?86400:sec('end'));};draw(0,86400);
</script></main></html>'''
