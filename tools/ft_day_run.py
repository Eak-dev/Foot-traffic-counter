"""One foreground, resumable daily job. No scheduler, server or credential files."""
import argparse
import datetime as dt
import contextlib
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
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
from tools.ft_session import SessionManager, SessionError, load_target
from tools.ft_day_state import read_checkpoint, StateError

JOB_BYTES=350*1024**2
JOB_SECONDS=36*3600
DRIVER_SECONDS=48*3600
REFERENCE_SHA256='2fef18ff159658903c9d6b0fce96d9e62c873fb40107fb2ee8aebc5dc0785d6c'
REPO=Path(__file__).resolve().parent.parent
FAILURE_STAGES=frozenset(('CONFIG','INVENTORY','PREPARE','GUARD','WORKER_START',
    'DOWNLOAD','COUNT','CHECKPOINT','COMMIT','CLEANUP'))
MEDIA_CODES=frozenset(('TIMEOUT','QUOTA','DISK_SPACE','STORAGE','SAMPLE_EXISTS',
    'NO_ELIGIBLE_CLIP','IDENTITY','HTTP','TLS','CONNECT','PROTOCOL','INCOMPLETE',
    'VALIDATION','PUBLIC_ENDPOINT_REQUIRED','PREREQUISITE'))


def failure_diagnostic(stage,exc):
    """Only fixed enums/numbers; never exception messages, args or paths."""
    result=dict(stage=stage if stage in FAILURE_STAGES else 'UNKNOWN',
                kind='UNCLASSIFIED',code='UNCLASSIFIED')
    if isinstance(exc,(media.SampleError,sd.SdError)):
        media_error=isinstance(exc,media.SampleError)
        codes=MEDIA_CODES if media_error else sd.ERROR_CODES
        code=getattr(exc,'code',None)
        result.update(kind='MEDIA' if media_error else 'SD',
                      code=code if type(code) is str and code in codes else 'UNKNOWN')
        status=getattr(exc,'http_status',None)
        if type(status) is int and 100<=status<=599:result['http_status']=status
    elif isinstance(exc,subprocess.TimeoutExpired):result.update(kind='PROCESS',code='TIMEOUT')
    elif isinstance(exc,OSError):
        result.update(kind='IO',code='ERROR')
        if type(exc.errno) is int and 0<exc.errno<=4095:result['errno']=exc.errno
    elif isinstance(exc,f.ValidationError):result.update(kind='VALIDATION',code='REJECTED')
    return result


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


def fixed_remux_filter(videos):
    fixed=[v for v in videos if v.get('index')==0]
    if len(fixed)!=1:raise DayError('LENS_OR_CLOCK_UNVERIFIED')
    # NAL type 6 is H.264 SEI; it is picture data in other codecs.
    # The vendor's SEI-only final packet otherwise becomes a phantom MP4 frame.
    if fixed[0].get('codec_name')!='h264':raise DayError('UNSUPPORTED_SOURCE')
    return 'filter_units=remove_types=6'


def download(token,terminal,device,uid,clip,root,guard,date=sd.FIXED_DATE):
    capture_start=clip.get('capture_start',clip['start']);capture_end=clip.get('capture_end',clip['end'])
    span=capture_end-capture_start
    if not 1<=span<=180:raise DayError('UNSUPPORTED_SOURCE')
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
            media._stream(relay,terminal,track,uid,start,end,out,budget,mode='download',short_recording=span<5)
            out.flush();os.fsync(out.fileno())
        videos=media._inspect(raw,span,budget)
        bitstream_filter=fixed_remux_filter(videos)
        if fixed.exists() or fixed.is_symlink():raise DayError('STORAGE')
        ffmpeg=REPO/'.venv/ft-media-bin/ffmpeg'
        result=subprocess.run([str(ffmpeg),'-v','error','-protocol_whitelist','file','-f','mpegts','-i',str(raw),
            '-map','0:0','-an','-c:v','copy','-bsf:v',bitstream_filter,'-movflags','+faststart',str(fixed)],
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
    def __init__(self,root,config,reference,checkpoint=None):
        self.buffer=b'';self.selector=selectors.DefaultSelector()
        cmd=['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',
             str(REPO/'.venv/ft-counting/bin/python'),'-m','tools.ft_day_count','--worker',
             '--root',str(root),'--config',str(config),'--model',str(REPO/'.venv/ft-models/yolox_s.onnx'),
             '--reference',str(reference)]
        if checkpoint is not None:cmd+=['--resume-json',json.dumps(checkpoint,separators=(',',':'))]
        self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                   cwd=str(REPO),bufsize=0,env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
        self.selector.register(self.proc.stdout,selectors.EVENT_READ)
        try:
            ready=self.receive(120)
            if isinstance(ready,dict) and ready.get('reason')=='CHECKPOINT_MISMATCH':raise DayError('CHECKPOINT_MISMATCH')
            if not isinstance(ready,dict) or ready.get('status')!='ready':raise DayError('WORKER_FAILED')
        except Exception:
            self.close();raise
        self.config_hash=ready.get('config_sha256');self.runtime=ready.get('runtime')

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
        if isinstance(result,dict) and result.get('status')=='blocked' and result.get('reason') in ('LENS_UNVERIFIED','CLOCK_UNVERIFIED','COUNT_VALIDATION_FAILED'):
            raise DayError(result['reason'])
        if not isinstance(result,dict) or result.get('status')!='ok' or result.get('config_sha256')!=self.config_hash:raise DayError('WORKER_FAILED')
        if not isinstance(result.get('checkpoint'),dict) or result['checkpoint'].get('runtime')!=self.runtime:
            raise DayError('CHECKPOINT_MISMATCH')
        return result

    def close(self):
        if getattr(self,'proc',None):
            if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=5)
        self.selector.close()


def prioritize_daytime(info):
    """Whole independent groups only; never skip night or reset within a group."""
    planned=groups(info['clips'])
    planned.sort(key=lambda g:(not (g['start']<20*3600 and g['end']>6*3600),-(g['end']-g['start']),g['start']))
    return dict(info,clips=[c for g in planned for c in g['clips']])


def prefix_coverage_end(clips,cursor):
    last=clips[cursor-1]['ref']
    group=next(g for g in groups(clips) if any(c['ref']==last for c in g['clips']))
    refs={c['ref'] for c in group['clips']}
    return max(c.get('capture_end',c['end']) for c in clips[:cursor] if c['ref'] in refs)


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
        cursor=data.get('cursor');cp=data.get('checkpoint')
        if (type(cursor) is not int or not 0<=cursor<=len(data['clips'])
                or data.get('checkpoint_mode')!='exact_json_v1'):
            raise DayError('CHECKPOINT_MISMATCH')
        for index,c in enumerate(data['clips']):
            if index<cursor:
                if c['status'] not in ('counted','covered') or not c.get('clock_verified') or not c.get('lens_verified'):
                    raise DayError('CHECKPOINT_MISMATCH')
            elif c['status'] in ('counted','covered'):
                raise DayError('CHECKPOINT_MISMATCH')
        if cursor:
            last=data['clips'][cursor-1]
            if (not isinstance(cp,dict) or cp.get('source_ref')!=last['ref']
                    or cp.get('input_sha256')!=last.get('input_sha256')
                    or cp.get('coverage_end')!=prefix_coverage_end(data['clips'],cursor)):
                raise DayError('CHECKPOINT_MISMATCH')
            try:
                proof=read_checkpoint(root,cp)
                if proof['config_sha256']!=hash_ or proof['reference_sha256']!=REFERENCE_SHA256:
                    raise DayError('CHECKPOINT_MISMATCH')
            except (StateError,OSError,ValueError):raise DayError('CHECKPOINT_MISMATCH') from None
        elif cp is not None:raise DayError('CHECKPOINT_MISMATCH')
        prefix_refs={p['ref'] for p in data['clips'][:cursor]}
        expected_groups=[g['ref'] for g in groups(info['clips'])
                         if all(c['ref'] in prefix_refs for c in g['clips'])]
        if data.get('completed_groups')!=expected_groups:raise DayError('CHECKPOINT_MISMATCH')
        return data
    return dict(schema_version=1,date=iso,timezone='+07:00',config_sha256=hash_,
                inventory_complete=True,inventory_digest=info['inventory_digest'],boundary_mode='continuous_state',
                completed_groups=[],cursor=0,checkpoint=None,checkpoint_mode='exact_json_v1',
                clips=[dict(c,status='pending',events=[]) for c in info['clips']])


def save(root,data):
    atomic_write(Path(root)/'ledger.json',json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False))
    return write_reports(root,data)


def run_selected(token,terminal,selected,guard,root,config_path,reference,max_clips,date=sd.FIXED_DATE,daytime_first=False):
    started=time.monotonic();worker=None;stage='CONFIG'
    try:
        config=load_zones_config(config_path)
        f._validate_input_file(reference)
        if f._file_sha256(reference)!=REFERENCE_SHA256:raise DayError('LENS_OR_CLOCK_UNVERIFIED')
        stage='INVENTORY';info,device,uid=inventory(token,terminal,selected,guard,date)
        if daytime_first:info=prioritize_daytime(info)
        stage='PREPARE'
        data=prepare_ledger(root,info,config,date);save(root,data)
        processed=0;prune_checkpoints(root,data['checkpoint'])
        atomic_write(Path(root)/'count-config.json',json.dumps(config,ensure_ascii=False))
        planned_groups=groups(info['clips'])
        memberships={c['ref']:g['ref'] for g in planned_groups for c in g['clips']}
        prior_group=memberships[data['clips'][data['cursor']-1]['ref']] if data['cursor'] else None
        prior_end=prefix_coverage_end(data['clips'],data['cursor']) if data['cursor'] else None
        for index in range(data['cursor'],len(data['clips'])):
            stage='GUARD'
            guard();check_space(root)
            if processed>=max_clips or time.monotonic()-started>JOB_SECONDS:
                return dict(status='PARTIAL',reason='INVOCATION_BUDGET',summary=save(root,data))
            clip=data['clips'][index]
            start,end=clip.get('capture_start',clip['start']),clip.get('capture_end',clip['end'])
            if not 1<=end-start<=180:
                clip['status']='unsupported';save(root,data)
                return dict(status='PARTIAL',reason='UNSUPPORTED_SOURCE')
            current_group=memberships[clip['ref']]
            reset=current_group!=prior_group
            coverage_end=end if reset else max(end,prior_end)
            try:
                stage='CLEANUP'
                clean_work(root)
                stage='WORKER_START'
                if worker is None:worker=Worker(root,Path(root)/'count-config.json',reference,data['checkpoint'])
                stage='DOWNLOAD'
                input_hash=download(token,terminal,device,uid,clip,root,guard,date=date)
                stage='COUNT'
                result=worker.count(dict(start=start,end=end,reset=reset,source_ref=clip['ref'],input_sha256=input_hash))
                stage='CHECKPOINT'
                cp=result.get('checkpoint')
                if (not isinstance(cp,dict) or cp.get('source_ref')!=clip['ref']
                        or cp.get('input_sha256')!=input_hash or cp.get('coverage_end')!=coverage_end):
                    raise DayError('CHECKPOINT_MISMATCH')
                proof=read_checkpoint(root,cp)
                if proof['config_sha256']!=data['config_sha256'] or proof['reference_sha256']!=REFERENCE_SHA256:
                    raise DayError('CHECKPOINT_MISMATCH')
                clip.update(status='counted' if result['frames'] else 'covered',events=result['events'],
                            input_sha256=input_hash,config_sha256=result['config_sha256'],
                            clock_verified=result['clock_verified'],lens_verified=result['lens_verified'])
                data.update(cursor=index+1,checkpoint=cp)
                prefix_refs={c['ref'] for c in data['clips'][:index+1]}
                data['completed_groups']=[g['ref'] for g in planned_groups if all(c['ref'] in prefix_refs for c in g['clips'])]
                # The immutable new snapshot exists first. Atomic ledger replacement
                # commits its pointer and events together. Report failure must never
                # roll this transaction back or mark a committed source uncounted.
                stage='COMMIT';summary=save(root,data)
                prune_checkpoints(root,cp)
                prior_end=coverage_end;prior_group=current_group;processed+=1
                print(json.dumps(dict(progress='CLIP_COUNTED',processed=data['cursor'],total=len(data['clips']),
                                      front=summary['totals']['front'],review=summary['totals']['front_review'])),flush=True)
            finally:
                try:clean_work(root)
                except Exception:
                    stage='CLEANUP';raise
        stage='COMMIT'
        summary=save(root,data)
        return dict(status='SUCCESS' if summary['full_day_complete'] else 'PARTIAL',summary=summary)
    except StateError:return dict(status='BLOCKED',reason='CHECKPOINT_MISMATCH')
    except DayError as exc:return dict(status='BLOCKED',reason=exc.code)
    except SessionError:raise  # preserve the existing lease/reauth cleanup policy
    except Exception as exc:
        return dict(status='BLOCKED',reason='DAY_PROCESSING_FAILED',diagnostic=failure_diagnostic(stage,exc))
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


def prune_checkpoints(root,active):
    folder=Path(root)/'checkpoints'
    if not folder.exists():return
    s=folder.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077:raise DayError('STORAGE')
    if active is not None:read_checkpoint(root,active)
    keep=active['source_ref']+'.json' if active is not None else None
    for path in folder.iterdir():
        name=path.name
        suffix='.json.part' if name.endswith('.json.part') else '.json' if name.endswith('.json') else None
        if suffix is None:continue
        ref=name[:-len(suffix)]
        if len(ref)!=64 or any(c not in '0123456789abcdef' for c in ref):continue
        t=path.lstat()
        if not stat.S_ISREG(t.st_mode) or t.st_uid!=os.getuid() or t.st_nlink!=1 or t.st_mode&0o077:
            raise DayError('STORAGE')
        if name!=keep:path.unlink()


def deliver_reports(root,destination,date,complete):
    folder=Path(destination)
    f._outside_repo(folder)
    folder.mkdir(mode=0o700,parents=False,exist_ok=True)
    label='COMPLETE' if complete else 'PARTIAL'
    for extension in ('html','csv'):
        source=Path(root)/('summary.'+extension)
        st=source.lstat()
        f._require(stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and not st.st_mode&0o077 and st.st_nlink==1,'private numeric report required')
        atomic_write(folder/('FootTraffic-Day-'+date+'-'+label+'.'+extension),source.read_text())


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');p.add_argument('--root',required=True)
    p.add_argument('--config',required=True);p.add_argument('--reference',required=True);p.add_argument('--max-clips',type=int,default=1000)
    p.add_argument('--max-batches',type=int,default=1,help='finite cached-session batches; clips*batches<=1000')
    p.add_argument('--daytime-first',action='store_true');p.add_argument('--keep-awake',action='store_true')
    p.add_argument('--delivery-dir',default=None,help='owner-approved numeric-only report folder')
    p.add_argument('--date',default=None,help='completed Bangkok date YYYYMMDD; default yesterday')
    args=p.parse_args(argv);awake=None;root=None;lock=None;lock_held=False;result=dict(status='BLOCKED',reason='DAY_START_FAILED')
    started=time.monotonic();batch=0
    def interrupted(signum,frame):raise KeyboardInterrupt
    previous_term=signal.signal(signal.SIGTERM,interrupted)
    try:
        f._require(args.run and 1<=args.max_clips<=1000 and 1<=args.max_batches<=64
                   and args.max_clips*args.max_batches<=1000,'explicit bounded run required')
        today=dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date()
        date=args.date or (today-dt.timedelta(days=1)).strftime('%Y%m%d')
        sd._validate_day_date(date)
        f._require(dt.datetime.strptime(date,'%Y%m%d').date()<today,'completed date required')
        root=Path(args.root).resolve();f._outside_repo(root)
        root.mkdir(mode=0o700,parents=False,exist_ok=True)
        st=root.lstat();f._require(stat.S_ISDIR(st.st_mode) and st.st_uid==os.getuid() and not st.st_mode&0o077,'private job root required')
        work=root/'work';work.mkdir(mode=0o700,exist_ok=True)
        f._require(not work.is_symlink() and work.stat().st_uid==os.getuid() and not work.stat().st_mode&0o077,'private work folder required')
        lock=job_lock(root);lock.__enter__();lock_held=True
        recover_parts(root);clean_work(root)
        if (root/'ledger.json').exists():prune_checkpoints(root,read_ledger(root/'ledger.json').get('checkpoint'))
        else:prune_checkpoints(root,None)
        check_space(root)
        if args.keep_awake:
            awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid()),'-t',str(DRIVER_SECONDS)],
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        target=load_target()
        for batch in range(1,args.max_batches+1):
            if time.monotonic()-started>=DRIVER_SECONDS:
                result=dict(status='PARTIAL',reason='DRIVER_TIME_BUDGET');break
            atomic_write(root/'job-status.json',json.dumps(dict(running=True,pid=os.getpid(),batch=batch,
                date=date,updated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())))
            def run_batch(token,terminal,selected,lease_guard):
                def guarded():
                    lease_guard()
                    if time.monotonic()-started>=DRIVER_SECONDS:raise DayError('DAY_TIMEOUT')
                return run_selected(token,terminal,selected,guarded,root,args.config,args.reference,
                    args.max_clips,date=date,daytime_first=args.daytime_first)
            result=SessionManager().command('use',target,on_selected_camera=run_batch,callback_with_guard=True)
            authenticated=result.get('status')=='SUCCESS'
            callback=result.get('callback',{})
            if authenticated:result['status']=callback.get('status','BLOCKED')
            if args.delivery_dir and (root/'summary.html').exists():
                try:
                    iso=date[:4]+'-'+date[4:6]+'-'+date[6:]
                    deliver_reports(root,args.delivery_dir,iso,authenticated and callback.get('status')=='SUCCESS')
                    result['delivery']='COPIED_NUMERIC_REPORTS'
                except Exception:result['delivery']='DELIVERY_FAILED_LOCAL_REPORTS_RETAINED'
            if not authenticated or callback.get('status')!='PARTIAL' or callback.get('reason')!='INVOCATION_BUDGET':break
            print(json.dumps(dict(progress='BATCH_CHECKPOINT',batch=batch,status='PARTIAL')),flush=True)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0 if result.get('callback',{}).get('status')=='SUCCESS' and not result.get('delivery','').startswith('DELIVERY_FAILED') else 2
    except KeyboardInterrupt:
        result=dict(status='INTERRUPTED',reason='CHECKPOINT_RETAINED');print(json.dumps(result));return 130
    except Exception:
        result=dict(status='BLOCKED',reason='DAY_START_FAILED');print(json.dumps(result));return 2
    finally:
        signal.signal(signal.SIGTERM,previous_term)
        if awake:
            with contextlib.suppress(OSError):awake.terminate()
            try:awake.wait(timeout=3)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(OSError):awake.kill()
                awake.wait(timeout=3)
        if lock_held:
            with contextlib.suppress(Exception):
                atomic_write(root/'job-status.json',json.dumps(dict(running=False,pid=os.getpid(),batch=batch,
                    status=result.get('status'),reason=result.get('reason') or result.get('callback',{}).get('reason'),
                    diagnostic=result.get('diagnostic') or result.get('callback',{}).get('diagnostic'),
                    updated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())))
            lock.__exit__(None,None,None)


if __name__=='__main__':sys.exit(main())
