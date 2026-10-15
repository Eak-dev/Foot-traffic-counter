"""One explicit completed-day job, at most two finite driver cycles; no scheduler."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from tools.ft_day_summary import read_ledger

SECONDS = 72*3600
CYCLE_SECONDS = 36*3600
NEW_CLIPS = 1000
REPO = Path(__file__).resolve().parent.parent


def cursor(root):
    path=Path(root)/'ledger.json'
    if not path.exists():return 0
    data=read_ledger(path);value=data.get('cursor')
    if type(value) is not int or not 0<=value<=len(data['clips']):raise ValueError('invalid cursor')
    return value


def stop(child):
    if child is None:return None
    code=child.poll()
    if code is not None:return code
    with contextlib.suppress(OSError):child.terminate()
    try:return child.wait(timeout=30)
    except subprocess.TimeoutExpired:
        # Only the session created for this one child and its counting worker.
        with contextlib.suppress(ProcessLookupError):os.killpg(child.pid,signal.SIGKILL)
        return child.wait(timeout=5)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='store_true')
    for name in ('date','root','config','reference'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--delivery-dir',default=None)
    parser.add_argument('--keep-awake',action='store_true')
    args=parser.parse_args(argv)
    child=None;started=time.monotonic()
    def interrupted(signum,frame):raise KeyboardInterrupt
    previous_term=signal.signal(signal.SIGTERM,interrupted)
    try:
        if not args.run:raise ValueError('explicit run required')
        initial=cursor(args.root)
        for cycle in range(2):
            current=cursor(args.root)
            if current<initial:raise ValueError('cursor moved backwards')
            remaining=NEW_CLIPS-(current-initial)
            seconds=SECONDS-(time.monotonic()-started)
            if remaining<=0 or seconds<=0:break
            clips=min(12,remaining);batches=min(64,remaining//clips)
            command=[sys.executable,'-m','tools.ft_day_run','--run','--date',args.date,'--root',args.root,
                '--config',args.config,'--reference',args.reference,'--max-clips',str(clips),
                '--max-batches',str(batches),'--daytime-first']
            if args.delivery_dir:command+=['--delivery-dir',args.delivery_dir]
            if args.keep_awake:command+=['--keep-awake']
            child=subprocess.Popen(command,cwd=str(REPO),start_new_session=True,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            timed_out=False
            try:code=child.wait(timeout=min(CYCLE_SECONDS,seconds))
            except subprocess.TimeoutExpired:
                timed_out=True;code=stop(child)
            if code==0:return 0
            # Retry only budget exits or this supervisor's own verified clean stop.
            status_path=Path(args.root)/'job-status.json'
            if not status_path.exists():return code
            status=json.loads(status_path.read_text())
            budget_exit=(status.get('status')=='PARTIAL' and status.get('reason') in
                ('DRIVER_TIME_BUDGET','INVOCATION_BUDGET'))
            clean_owned_stop=(timed_out and code==130 and status.get('status')=='INTERRUPTED'
                and status.get('reason')=='CHECKPOINT_RETAINED')
            if (status.get('running') is not False or status.get('pid')!=child.pid
                    or not (budget_exit or clean_owned_stop)):
                return code or 2
            if cycle==0:print('{"progress":"CONTINUE_COMMITTED_DAY_CHECKPOINT"}',flush=True)
        print('{"status":"PARTIAL","reason":"WHOLE_JOB_BUDGET"}',flush=True)
        return 2
    except KeyboardInterrupt:
        stop(child);print('{"status":"INTERRUPTED","reason":"CHECKPOINT_RETAINED"}',flush=True)
        return 130
    except Exception:
        stop(child);print('{"status":"BLOCKED","reason":"WHOLE_JOB_START_FAILED"}',flush=True)
        return 2
    finally:signal.signal(signal.SIGTERM,previous_term)


if __name__=='__main__':sys.exit(main())
