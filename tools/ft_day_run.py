"""One foreground, resumable daily job. No scheduler, server or credential files."""
import argparse
import datetime as dt
import contextlib
import fcntl
import json
import os
from pathlib import Path
import selectors
import shutil
import stat
import subprocess
import sys
import time

from tools import ft_count as f, ft_media_probe as media, ft_sd_probe as sd
from tools.ft_count_zones import load_zones_config
from tools.ft_day_acquire import inventory, groups, DayError
from tools.ft_day_count import config_digest
from tools.ft_day_summary import atomic_write, read_ledger, write_reports, digest
from tools.ft_session import SessionManager, load_target

JOB_BYTES=350*1024**2
JOB_SECONDS=36*3600
REFERENCE_SHA256='2fef18ff159658903c9d6b0fce96d9e62c873fb40107fb2ee8aebc5dc0785d6c'
REPO=Path(__file__).resolve().parent.parent


def check_space(root):
    if shutil.disk_usage(root).free<10*1024**3:raise DayError('STORAGE')
    size=sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file() and not p.is_symlink())
    if size>JOB_BYTES:raise DayError('DAY_QUOTA')
    # Existing reviewed project stages plus this bounded job remain under1GiB.
    aggregate=size
    for pattern in ('ft-zones-*-501','ft-noon-*-501','ft-day-*-501'):
        for directory in Path('/private/tmp').glob(pattern):
            if not directory.is_dir() or directory.is_symlink() or directory.resolve()==Path(root).resolve():continue
            aggregate+=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and not p.is_symlink())
    if aggregate>1024**3:raise DayError('DAY_QUOTA')


def download(token,terminal,device,uid,clip,root,guard,date=sd.FIXED_DATE):
    capture_start=clip.get('capture_start',clip['start']);capture_end=clip.get('capture_end',clip['end'])
    span=capture_end-capture_start
    if not 5<=span<=180:raise DayError('UNSUPPORTED_SOURCE')
    work=Path(root)/'work';raw=work/'sample.part';fixed=work/'fixed.mp4'
    previous=media.ROOT;media.ROOT=work
    try:
        check_space(root);media._private_root();budget=media.Budget(guard)
        sd._validate_day_date(date)
        start_day,_=sd._day_bounds_utc(date,'+07:00')
        start,end=start_day+capture_start,start_day+capture_end
        # Native recorded-download protocol obtains a fresh playback UID after search.
        reqs=sd._expected_requests('day-calendar',date,None)
        db=sd._DeviceBudget(session_guard=budget.check_time)
        raw_uid=sd._device_request(db,token,terminal,device,reqs,'day-calendar',date)
        replies=sd._parse_responses(raw_uid,{r['method'] for r in reqs})
        uid=sd._read_user_id(replies['getUserID'])
        if uid is None or not sd._read_calendar(replies['searchDateWithVideo'],date):
            raise DayError('INVALID_SOURCE')
        track='backup-'+device+'-'+str(start)
        relay=media._negotiate(token,terminal,device,track,budget)
        fd=os.open(str(raw),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as out:
            media._stream(relay,terminal,track,uid,start,end,out,budget,mode='download')
            out.flush();os.fsync(out.fileno())
        videos=media._inspect(raw,span,budget)
        if not any(v.get('index')==0 for v in videos):raise DayError('LENS_OR_CLOCK_UNVERIFIED')
        if fixed.exists() or fixed.is_symlink():raise DayError('STORAGE')
        ffmpeg=REPO/'.venv/ft-media-bin/ffmpeg'
        result=subprocess.run([str(ffmpeg),'-v','error','-protocol_whitelist','file','-f','mpegts','-i',str(raw),
            '-map','0:0','-an','-c:v','copy','-movflags','+faststart',str(fixed)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            timeout=min(60,max(.001,budget.start+media.SECONDS-time.monotonic())))
        budget.check_time()
        if result.returncode:raise DayError('MEDIA_FAILED')
        fixed.chmod(0o600);f._validate_input_file(fixed);check_space(root)
        return f._file_sha256(fixed)
    finally:media.ROOT=previous


def clean_work(root):
    for name in ('sample.part','sample.ts','fixed.mp4'):
        path=Path(root)/'work'/name
        if path.exists() or path.is_symlink():
            st=path.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_nlink!=1:raise DayError('STORAGE')
            path.unlink()


class Worker:
    def __init__(self,root,config,reference):
        self.buffer=b'';self.selector=selectors.DefaultSelector()
        cmd=['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',
             str(REPO/'.venv/ft-counting/bin/python'),'-m','tools.ft_day_count','--worker',
             '--root',str(root),'--config',str(config),'--model',str(REPO/'.venv/ft-models/yolox_s.onnx'),
             '--reference',str(reference)]
        self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                   cwd=str(REPO),bufsize=0,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.selector.register(self.proc.stdout,selectors.EVENT_READ)
        try:
            ready=self.receive(120)
            if not isinstance(ready,dict) or ready.get('status')!='ready':raise DayError('WORKER_FAILED')
        except Exception:
            self.close();raise
        self.config_hash=ready.get('config_sha256')

    def receive(self,timeout):
        deadline=time.monotonic()+timeout
        while b'\n' not in self.buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise DayError('WORKER_FAILED')
            if not self.selector.select(min(1,remaining)):continue
            chunk=os.read(self.proc.stdout.fileno(),65536)
            if not chunk:raise DayError('WORKER_FAILED')
            self.buffer+=chunk
            if len(self.buffer)>2*1024*1024:raise DayError('WORKER_FAILED')
        line,self.buffer=self.buffer.split(b'\n',1)
        try:return json.loads(line)
        except (ValueError,UnicodeError):raise DayError('WORKER_FAILED') from None

    def count(self,message):
        self.proc.stdin.write((json.dumps(message)+'\n').encode());self.proc.stdin.flush()
        result=self.receive(2450)
        if not isinstance(result,dict) or result.get('status')!='ok' or result.get('config_sha256')!=self.config_hash:raise DayError('WORKER_FAILED')
        return result

    def close(self):
        if getattr(self,'proc',None):
            if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=5)
        self.selector.close()


def prepare_ledger(root,info,config,date):
    iso=date[:4]+'-'+date[4:6]+'-'+date[6:]
    existing=Path(root)/'ledger.json';hash_=config_digest(config)
    if existing.exists():
        data=read_ledger(existing)
        if data['config_sha256']!=hash_ or data['inventory_digest']!=info['inventory_digest'] or data['date']!=iso:
            raise DayError('CHECKPOINT_MISMATCH')
        keys=('ref','start','end','capture_start','capture_end')
        if [{k:c.get(k) for k in keys} for c in data['clips']]!=[{k:c.get(k) for k in keys} for c in info['clips']]:
            raise DayError('CHECKPOINT_MISMATCH')
        completed=data.get('completed_groups');planned={g['ref']:g for g in groups(info['clips'])}
        if (not isinstance(completed,list) or any(not isinstance(ref,str) or ref not in planned for ref in completed)
                or len(completed)!=len(set(completed))):
            raise DayError('CHECKPOINT_MISMATCH')
        by_ref={c['ref']:c for c in data['clips']}
        for ref in completed:
            if any(by_ref[c['ref']]['status'] not in ('counted','covered')
                   or not by_ref[c['ref']].get('clock_verified') or not by_ref[c['ref']].get('lens_verified')
                   for c in planned[ref]['clips']):raise DayError('CHECKPOINT_MISMATCH')
        return data
    return dict(schema_version=1,date=iso,timezone='+07:00',config_sha256=hash_,
                inventory_complete=True,inventory_digest=info['inventory_digest'],boundary_mode='continuous_state',
                completed_groups=[],clips=[dict(c,status='pending',events=[]) for c in info['clips']])


def save(root,data):
    atomic_write(Path(root)/'ledger.json',json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False))
    return write_reports(root,data)


def run_selected(token,terminal,selected,guard,root,config_path,reference,max_clips,date=sd.FIXED_DATE):
    started=time.monotonic();worker=None
    try:
        config=load_zones_config(config_path)
        f._validate_input_file(reference)
        if f._file_sha256(reference)!=REFERENCE_SHA256:raise DayError('LENS_OR_CLOCK_UNVERIFIED')
        info,device,uid=inventory(token,terminal,selected,guard,date)
        data=prepare_ledger(root,info,config,date);save(root,data)
        items={c['ref']:c for c in data['clips']};processed=0
        atomic_write(Path(root)/'count-config.json',json.dumps(config,ensure_ascii=False))
        for group in groups(info['clips']):
            if group['ref'] in data['completed_groups']:continue
            # State is not pickled. Restart an unfinished continuous group fully.
            for source in group['clips']:items[source['ref']]=dict(source,status='pending',events=[])
            data['clips']=[items[c['ref']] for c in info['clips']];save(root,data)
            reset=True;complete=True
            for source in group['clips']:
                guard();check_space(root)
                if processed>=max_clips or time.monotonic()-started>JOB_SECONDS:
                    return dict(status='PARTIAL',reason='INVOCATION_BUDGET',summary=save(root,data))
                clip=items[source['ref']]
                if not 5<=clip.get('capture_end',clip['end'])-clip.get('capture_start',clip['start'])<=180:
                    clip['status']='unsupported';complete=False;reset=True;save(root,data);continue
                try:
                    clean_work(root)
                    input_hash=download(token,terminal,device,uid,clip,root,guard,date=date)
                    if worker is None:worker=Worker(root,Path(root)/'count-config.json',reference)
                    result=worker.count(dict(start=clip.get('capture_start',clip['start']),end=clip.get('capture_end',clip['end']),reset=reset,
                                             source_ref=clip['ref'],input_sha256=input_hash))
                    clip.update(status='counted' if result['frames'] else 'covered',events=result['events'],
                                input_sha256=input_hash,config_sha256=result['config_sha256'],
                                clock_verified=result['clock_verified'],lens_verified=result['lens_verified'])
                    reset=False;processed+=1
                    summary=save(root,data)
                    print(json.dumps(dict(progress='CLIP_COUNTED',processed=processed,total=len(data['clips']),
                                          front=summary['totals']['front'],review=summary['totals']['front_review'])),flush=True)
                except Exception:
                    clip.update(status='error',events=[]);save(root,data)
                    raise
                finally:clean_work(root)
            if complete:data['completed_groups'].append(group['ref'])
            save(root,data)
        summary=save(root,data)
        return dict(status='SUCCESS' if summary['full_day_complete'] else 'PARTIAL',summary=summary)
    except DayError as exc:return dict(status='BLOCKED',reason=exc.code)
    except Exception:return dict(status='BLOCKED',reason='DAY_PROCESSING_FAILED')
    finally:
        if worker:worker.close()


@contextlib.contextmanager
def job_lock(root):
    fd=os.open(str(Path(root)/'run.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        s=os.fstat(fd)
        f._require(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077 and s.st_nlink==1,'unsafe job lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
    finally:os.close(fd)


def recover_parts(root):
    """Only after the exclusive job lock; retain the previous atomic checkpoint."""
    for name in ('ledger.json','summary.html','summary.csv','summary.json','count-config.json'):
        path=Path(root)/(name+'.part')
        if path.exists() or path.is_symlink():
            s=path.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1 or s.st_mode&0o077:
                raise DayError('STORAGE')
            path.unlink()


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');p.add_argument('--root',required=True)
    p.add_argument('--config',required=True);p.add_argument('--reference',required=True);p.add_argument('--max-clips',type=int,default=1000)
    p.add_argument('--date',default=None,help='completed Bangkok date YYYYMMDD; default yesterday')
    args=p.parse_args(argv)
    try:
        f._require(args.run and 1<=args.max_clips<=1000,'explicit bounded run required')
        today=dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date()
        date=args.date or (today-dt.timedelta(days=1)).strftime('%Y%m%d')
        sd._validate_day_date(date)
        f._require(dt.datetime.strptime(date,'%Y%m%d').date()<today,'completed date required')
        root=Path(args.root).resolve();f._outside_repo(root)
        root.mkdir(mode=0o700,parents=False,exist_ok=True)
        s=root.lstat();f._require(stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077,'private job root required')
        work=root/'work';work.mkdir(mode=0o700,exist_ok=True)
        f._require(not work.is_symlink() and work.stat().st_uid==os.getuid() and not work.stat().st_mode&0o077,'private work folder required')
        check_space(root)
        with job_lock(root):
            recover_parts(root)
            result=SessionManager().command('use',load_target(),
                on_selected_camera=lambda token,terminal,selected,guard:run_selected(token,terminal,selected,guard,
                    root,args.config,args.reference,args.max_clips,date=date),callback_with_guard=True)
        if result.get('status')=='SUCCESS':result['status']=result.get('callback',{}).get('status','BLOCKED')
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0 if result.get('callback',{}).get('status')=='SUCCESS' else 2
    except Exception:
        print('{"status":"BLOCKED","reason":"DAY_START_FAILED"}');return 2


if __name__=='__main__':sys.exit(main())
