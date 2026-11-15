"""Count stable outside-to-inside visits, without counting initial occupancy."""
import math
from tools.ft_count import (CrossingCounter, ValidationError, _is_finite_point,
                            _point_in_polygon, MAX_RETAINED_TRACKS)


def distance_to_boundary(point, polygon):
    x,y = point
    result = math.inf
    for (ax,ay),(bx,by) in zip(polygon,polygon[1:]+polygon[:1]):
        dx,dy = bx-ax,by-ay
        alpha = max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
        result = min(result,math.hypot(x-ax-alpha*dx,y-ay-alpha*dy))
    return result


class ZoneEntryCounter:
    """Only count a tracked person seen stably outside and then stably inside.

    Three observations on each side, boundary deadband and a two-second gap
    limit suppress boundary jitter. Starting inside or reappearing inside is
    not a proven entry. No identity embedding or cross-zone deduplication.
    """
    def __init__(self, roi, deadband=.012):
        CrossingCounter([[0,0],[1,1]],roi,deadband)  # shared geometry checks
        self.roi = [tuple(p) for p in roi]
        self.deadband = deadband
        self._tracks = {}
        self.events = []
        self.count = 0

    def update(self, track_id, point, t):
        if not _is_finite_point(point) or any(not 0<=c<=1 for c in point):
            raise ValidationError('invalid entry point')
        if type(track_id) is not int or type(t) not in (int,float) or not math.isfinite(t) or t<0:
            raise ValidationError('invalid entry observation')
        for key in list(self._tracks):
            if t-self._tracks[key]['time']>10:self._tracks.pop(key)
        st=self._tracks.get(track_id)
        if st and t<=st['time']:raise ValidationError('track times must increase')
        if st is None or t-st['time']>2:
            st={'time':t,'stable':None,'pending':None,'samples':0,'outside':None,'last_entry':-math.inf}
            self._tracks[track_id]=st
        st['time']=t
        if distance_to_boundary(point,self.roi)<self.deadband:
            st['pending'],st['samples']=None,0
        else:
            inside=_point_in_polygon(point,self.roi)
            if st['pending']==inside:st['samples']+=1
            else:st['pending'],st['samples']=inside,1
            if st['samples']>=3:
                if inside and st['stable'] is False and t-st['last_entry']>=2:
                    self.events.append({'track_id':track_id,'time_seconds':t,'direction':'forward',
                                        'event_type':'zone_entry','evidence':{'from':list(st['outside']),'to':list(point)}})
                    self.count+=1;st['last_entry']=t
                st['stable']=inside
                if not inside:st['outside']=tuple(point)
        if len(self._tracks)>MAX_RETAINED_TRACKS:
            oldest=min(self._tracks,key=lambda key:self._tracks[key]['time'])
            self._tracks.pop(oldest)
