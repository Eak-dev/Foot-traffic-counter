"""Evaluate a private, manually labelled window; never extrapolate to a day."""
import math


def evaluate(predicted, truth, window, tolerance=2.0):
    """Ordered one-to-one temporal matching per direction, maximum TP then error.

    Callers bind labels and predictions to the same input/config hashes. Relative
    clip seconds only. Direction errors produce one FP and one FN, not a TP.
    """
    if (len(window) != 2 or not all(type(x) in (int,float) and math.isfinite(x) for x in window)
            or not 0 <= window[0] < window[1] or not 0 < tolerance <= 5):
        raise ValueError('invalid evaluation window')
    groups=[]
    for events in (predicted, truth):
        if len(events)>500: raise ValueError('too many events')
        for e in events:
            if e.get('direction') not in ('forward','backward') or type(e.get('time_seconds')) not in (int,float) or not math.isfinite(e['time_seconds']):
                raise ValueError('invalid event')
        groups.append([e for e in events if window[0] <= e['time_seconds'] < window[1]])
    matches=[]
    for direction in ('forward','backward'):
        p=sorted([(i,e['time_seconds']) for i,e in enumerate(groups[0]) if e['direction']==direction],key=lambda x:x[1])
        g=sorted([(i,e['time_seconds']) for i,e in enumerate(groups[1]) if e['direction']==direction],key=lambda x:x[1])
        # score tuple: count, negative summed time error. Backtrack separately.
        dp=[[(0,0.0)]*(len(g)+1) for _ in range(len(p)+1)]
        action={}
        for i in range(1,len(p)+1):
            for j in range(1,len(g)+1):
                options=[(dp[i-1][j],'p'),(dp[i][j-1],'g')]
                delta=abs(p[i-1][1]-g[j-1][1])
                if delta<=tolerance: options.append(((dp[i-1][j-1][0]+1,dp[i-1][j-1][1]-delta),'m'))
                score,step=max(options,key=lambda x:x[0]);dp[i][j]=score;action[i,j]=step
        i,j=len(p),len(g)
        while i and j:
            step=action[i,j]
            if step=='m': matches.append((p[i-1][0],g[j-1][0]));i-=1;j-=1
            elif step=='p': i-=1
            else:j-=1
    pm,gm={x[0] for x in matches},{x[1] for x in matches}
    tp=len(matches);np,ng=map(len,groups);fp=np-tp;fn=ng-tp
    return {'window_seconds':list(window),'tolerance_seconds':tolerance,'predicted_count':np,'manual_count':ng,
            'true_positive':tp,'false_positive':fp,'false_negative':fn,
            'precision':tp/np if np else None,'recall':tp/ng if ng else None,
            'f1':2*tp/(np+ng) if np+ng else None,
            'aggregate_count_agreement':max(0,1-abs(np-ng)/ng) if ng else (1.0 if not np else 0.0),
            'false_positive_events':[e for i,e in enumerate(groups[0]) if i not in pm],
            'false_negative_events':[e for i,e in enumerate(groups[1]) if i not in gm],
            'whole_clip_accuracy_verified':False,'full_day_complete':False}


def evaluate_report(report, labels):
    """Fail closed if manual labels refer to another clip or counting geometry."""
    import re
    for key in ('input_sha256','config_sha256'):
        value=report.get(key)
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value) or labels.get(key)!=value:
            raise ValueError('label binding mismatch')
    return evaluate(report['events'],labels['events'],labels['window_seconds'],labels.get('tolerance_seconds',2.0))
