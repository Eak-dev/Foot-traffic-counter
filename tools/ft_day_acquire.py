"""Bounded readonly SD inventory for one selected completed Bangkok day."""
import hashlib
import time

from tools import ft_cloud_probe as cloud, ft_sd_probe as sd
from tools.ft_day_summary import digest

MAX_PAGES=200
MAX_REQUESTS=410
LIST_SECONDS=900


class DayError(Exception):
    def __init__(self,code):
        allowed={'INVALID_SOURCE','INCOMPLETE_INVENTORY','STALLED_PAGE','UNSTABLE_INVENTORY',
                 'DAY_QUOTA','DAY_TIMEOUT','MISSING_FIXED_METADATA','DATE_NOT_RECORDED',
                 'AUTH_REQUIRED','MEDIA_FAILED','WORKER_FAILED','UNSUPPORTED_SOURCE',
                 'CHECKPOINT_MISMATCH','STORAGE','LENS_OR_CLOCK_UNVERIFIED',
                 'LENS_UNVERIFIED','CLOCK_UNVERIFIED','COUNT_VALIDATION_FAILED'}
        self.code=code if code in allowed else 'INVALID_SOURCE';super().__init__(self.code)


class DayBudget:
    def __init__(self,guard,clock=time.monotonic):
        self.guard=guard;self.clock=clock;self.started=clock();self.start=self.started;self.requests=0
    def check_time(self):
        self.guard()
        if self.clock()-self.started>LIST_SECONDS:raise DayError('DAY_TIMEOUT')
    def use_request(self):
        self.check_time();self.requests+=1
        if self.requests>MAX_REQUESTS:raise DayError('DAY_QUOTA')
        self.start=self.clock()  # reused transport gets a fresh bounded per-request timeout


def parse_page(result,date):
    sd._validate_day_date(date)
    if not isinstance(result,dict) or not isinstance(result.get('playback'),dict):raise DayError('INVALID_SOURCE')
    rows=result['playback'].get('search_video_results')
    if not isinstance(rows,list) or len(rows)>20:raise DayError('INVALID_SOURCE')
    day,end_day=sd._day_bounds_utc(date,'+07:00');fixed={};labels=set();canonical=[]
    for row in rows:
        label,item=sd._single_index_entry(row)
        if label in labels or not isinstance(item,dict):raise DayError('INVALID_SOURCE')
        labels.add(label);a,b,kind=item.get('startTime'),item.get('endTime'),item.get('vedio_type')
        if (type(a) is not int or type(b) is not int or not day-180<=a<b<=end_day+180
                or a>=end_day or b<=day):raise DayError('INVALID_SOURCE')
        if not ((type(kind) is int and kind in (1,2)) or (type(kind) is str and kind in ('1','2'))):raise DayError('INVALID_SOURCE')
        channels=item.get('chn_times')
        if not isinstance(channels,dict) or not channels or not set(channels)<={'1','2'}:raise DayError('MISSING_FIXED_METADATA')
        timing={}
        for lens,value in channels.items():
            start=value.get('event_start_time') if isinstance(value,dict) else None
            if type(start) is not int or not a<=start<b:raise DayError('INVALID_SOURCE')
            timing[lens]=start
        canonical.append(dict(start=a,end=b,kind=int(kind),lens_starts=timing))
        if '1' in timing:
            start=timing['1'];ref=digest(dict(date=date,start=start,end=b,lens='1'))
            if start<end_day and b>day:
                fixed[ref]=dict(ref=ref,start=max(0,start-day),end=min(86400,b-day),
                                capture_start=start-day,capture_end=b-day)
    return dict(raw_count=len(rows),clips=list(fixed.values()),
                fingerprint=digest(sorted(canonical,key=lambda x:(x['start'],x['end'],x['kind']))))


def collect_sweep(fetch_page,check=lambda:None):
    clips={};pages=[];seen=set()
    for index in range(MAX_PAGES):
        check();page=fetch_page(index);check()
        count=page['raw_count']
        # The device may merge lens events within a requested index window,
        # returning fewer than20 rows even though subsequent pages still exist.
        # Only an explicitly empty page terminates this bounded sweep.
        if count and page['fingerprint'] in seen:raise DayError('STALLED_PAGE')
        if count:seen.add(page['fingerprint'])
        pages.append(page['fingerprint'])
        for clip in page['clips']:
            if clip['ref'] in clips and clips[clip['ref']]!=clip:raise DayError('INVALID_SOURCE')
            clips[clip['ref']]=clip
        if len(clips)>4000:raise DayError('DAY_QUOTA')
        if count==0:
            ordered=sorted(clips.values(),key=lambda c:(c['start'],c['end'],c['ref']))
            return ordered,digest(dict(pages=pages,clips=ordered))
    raise DayError('INCOMPLETE_INVENTORY')


def groups(clips):
    result=[]
    for clip in sorted(clips,key=lambda c:(c['start'],c['end'],c['ref'])):
        if not result or clip['start']>result[-1]['end']:
            result.append(dict(start=clip['start'],end=clip['end'],clips=[clip]))
        else:
            result[-1]['end']=max(result[-1]['end'],clip['end']);result[-1]['clips'].append(clip)
    for group in result:group['ref']=digest(group)
    return result


def inventory(token,terminal,selected,guard,date=sd.FIXED_DATE):
    sd._validate_day_date(date)
    if (not isinstance(selected,dict) or selected.get('model_kind') not in ('EXACT','VARIANT')
            or not cloud._validate_canonical_app_server(selected.get('app_server'))):raise DayError('INVALID_SOURCE')
    device=sd._validate_device_id(selected.get('thing_name'));budget=DayBudget(guard)
    def send(batch,uid=None,page=None):
        reqs=sd._expected_requests(batch,date,uid,page)
        raw=sd._device_request(budget,token,terminal,device,reqs,batch,date,uid,page_index=page)
        return sd._parse_responses(raw,{r['method'] for r in reqs})
    meta=send('day-metadata');sd._read_device_model(meta['getDeviceInfo'],selected['model_kind'])
    if sd._read_timezone_offset(meta['getTimezone'])!='+07:00' or sd._read_sd_status(meta['getSdCardStatus'])!='NORMAL':
        raise DayError('LENS_OR_CLOCK_UNVERIFIED')
    calendar=send('day-calendar');uid=sd._read_user_id(calendar['getUserID'])
    recorded=sd._read_calendar(calendar['searchDateWithVideo'],date)
    if uid is None or not recorded:raise DayError('DATE_NOT_RECORDED')
    def fetch(index):return parse_page(send('clip-day-page',uid,index)['searchVideoWithUTC'],date)
    first,proof=collect_sweep(fetch,budget.check_time)
    second,proof2=collect_sweep(fetch,budget.check_time)
    if proof!=proof2 or first!=second:raise DayError('UNSTABLE_INVENTORY')
    if not first:raise DayError('INCOMPLETE_INVENTORY')  # do not call an unexplained empty search a zero day
    return dict(clips=first,inventory_digest=proof,requests=budget.requests),device,uid
