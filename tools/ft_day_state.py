"""Exact, version-bound value snapshots of the pinned local counting runtime."""
from collections import OrderedDict, deque
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys

from tools.ft_state_codec import encode_tree, decode_tree, StateError
from tools.ft_day_summary import atomic_write, digest, HEX

MAX_BYTES = 32*1024**2
TRACK_FIELDS = frozenset(('state', 'is_activated', 'start_frame', 'frame_id',
    '_tlwh', 'kalman_filter', 'shared_kalman', 'mean', 'covariance', 'score',
    'tracklet_len', 'minimum_consecutive_frames', 'internal_id_counter',
    'external_id_counter', 'internal_track_id', 'external_track_id'))
LISTS = ('tracked_tracks', 'lost_tracks', 'removed_tracks')


def require(condition):
    if not condition:
        raise StateError('invalid counting checkpoint')


def integer(v, lo=0, hi=10000000):
    return type(v) is int and lo <= v <= hi


def finite(v, lo=-1e12, hi=1e12):
    return type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi


def time_value(v, sentinel=False):
    return finite(v, 0, 90000) or sentinel and v == -math.inf and type(v) is float


def point(v):
    return type(v) is tuple and len(v) == 2 and all(finite(x, 0, 1) for x in v)


def runtime_digest():
    import numpy
    import supervision
    import onnxruntime
    import scipy
    import cv2
    from supervision.tracker.byte_tracker import core, single_object_track, kalman_filter, utils, matching
    return digest(dict(python=list(sys.version_info[:3]), numpy=numpy.__version__,
        supervision=supervision.__version__, ort=onnxruntime.__version__, scipy=scipy.__version__,
        cv2=cv2.__version__, engine_sources=[hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
          for name in ('ft_day_count.py','ft_day_state.py','ft_state_codec.py','ft_count.py',
                       'ft_count_zones.py','ft_lane_counter.py','ft_track_quality.py','ft_zone_entries.py',
                       'ft_day_run.py','ft_day_acquire.py')],
        tracker_sources=[hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
          for m in (core, single_object_track, kalman_filter, utils, matching)]))


def tracker_dump(tracker):
    config = {k:getattr(tracker, k) for k in ('track_activation_threshold',
        'minimum_matching_threshold', 'det_thresh', 'max_time_lost', 'minimum_consecutive_frames')}
    pool, indices, lists = [], {}, {}
    for name in LISTS:
        lists[name] = []
        for track in getattr(tracker, name):
            key = id(track)
            if key not in indices:
                require(set(vars(track)) == TRACK_FIELDS)
                require(track.shared_kalman is tracker.shared_kalman
                    and track.internal_id_counter is tracker.internal_id_counter
                    and track.external_id_counter is tracker.external_id_counter
                    and (track.kalman_filter is None or track.kalman_filter is tracker.kalman_filter))
                fields = {k:getattr(track, k) for k in sorted(TRACK_FIELDS - {
                    'state', 'kalman_filter', 'shared_kalman', 'internal_id_counter', 'external_id_counter'})}
                fields.update(state=track.state.value, has_kalman=track.kalman_filter is not None)
                indices[key] = len(pool); pool.append(fields)
            lists[name].append(indices[key])
    require(len(pool) <= 1500)
    return dict(config=config, frame=tracker.frame_id, internal=tracker.internal_id_counter._id,
                external=tracker.external_id_counter._id, pool=pool, lists=lists)


def tracker_restore(tracker, saved, np):
    from supervision.tracker.byte_tracker.single_object_track import STrack, TrackState
    require(type(saved) is dict and set(saved) == {'config','frame','internal','external','pool','lists'})
    config = tracker_dump(tracker)['config']
    require(saved['config'] == config and integer(saved['frame'])
        and integer(saved['internal']) and integer(saved['external'], 1))
    require(type(saved['pool']) is list and len(saved['pool']) <= 1500
        and type(saved['lists']) is dict and set(saved['lists']) == set(LISTS))
    tracker.frame_id = saved['frame'];tracker.internal_id_counter._id = saved['internal']
    tracker.external_id_counter._id = saved['external']
    pool = []; internal_ids = set()
    fields = (TRACK_FIELDS - {'kalman_filter','shared_kalman','internal_id_counter','external_id_counter'}) | {'has_kalman'}
    for item in saved['pool']:
        require(type(item) is dict and set(item) == fields)
        require(integer(item['state'], 0, 3) and type(item['is_activated']) is bool
            and type(item['has_kalman']) is bool)
        require(all(integer(item[k], 0, saved['frame']) for k in ('start_frame','frame_id','tracklet_len')))
        require(item['minimum_consecutive_frames'] == config['minimum_consecutive_frames'])
        require(integer(item['internal_track_id'], 0, saved['internal']-1)
            and integer(item['external_track_id'], -1, saved['external']-1)
            and item['internal_track_id'] not in internal_ids)
        internal_ids.add(item['internal_track_id'])
        require(isinstance(item['_tlwh'], np.ndarray) and item['_tlwh'].shape == (4,)
            and item['_tlwh'].dtype == np.float32 and bool(np.isfinite(item['_tlwh']).all()))
        require(type(item['score']) in (float, np.float32, np.float64)
            and math.isfinite(float(item['score'])) and 0 <= item['score'] <= 1)
        if item['has_kalman']:
            for key, shape in (('mean',(8,)), ('covariance',(8,8))):
                require(isinstance(item[key], np.ndarray) and item[key].shape == shape
                    and item[key].dtype in ((np.float32,np.float64) if key=='mean' else (np.float64,))
                    and bool(np.isfinite(item[key]).all()))
        else:
            require(item['mean'] is None and item['covariance'] is None)
        track = STrack(item['_tlwh'], item['score'], config['minimum_consecutive_frames'],
            tracker.shared_kalman, tracker.internal_id_counter, tracker.external_id_counter)
        for k, value in item.items():
            if k not in ('state','has_kalman'):
                setattr(track, k, value)
        track.state = TrackState(item['state'])
        track.kalman_filter = tracker.kalman_filter if item['has_kalman'] else None
        pool.append(track)
    for name in LISTS:
        seq = saved['lists'][name]
        require(type(seq) is list and len(seq) <= 1500 and all(integer(i, 0, len(pool)-1) for i in seq)
            and len(seq) == len(set(seq)))
        setattr(tracker, name, [pool[i] for i in seq])


def validate_counter(counter, saved, mode):
    require(type(saved) is dict and set(saved) == ({'tracks','count','lane_counts'} if mode == 'lanes' else {'tracks','count'}))
    require(integer(saved['count']) and type(saved['tracks']) is dict and len(saved['tracks']) <= 500)
    lane_ids = set(counter.lane_counts) if mode == 'lanes' else set()
    if mode == 'lanes':
        require(type(saved['lane_counts']) is dict and set(saved['lane_counts']) == lane_ids
            and all(integer(n) for n in saved['lane_counts'].values())
            and sum(saved['lane_counts'].values()) == saved['count'])
    for tid, row in saved['tracks'].items():
        require(type(tid) in (int, str) and (integer(tid) if type(tid) is int else 0 < len(tid) <= 128)
            and type(row) is dict)
        if mode == 'lanes':
            require(set(row) == {'last_time','last_point','last_cross_time','lanes'}
                and time_value(row['last_time']) and time_value(row['last_cross_time'], True)
                and point(row['last_point']) and type(row['lanes']) is dict and set(row['lanes']) == lane_ids)
            for lane in row['lanes'].values():
                require(type(lane) is dict and set(lane) == {'armed_side','anchor','run_side','run_count','pending_side','pending_count'})
                require(all(v is None or type(v) is int and v in (-1,1)
                    for v in (lane['armed_side'],lane['run_side'],lane['pending_side'])))
                require((lane['anchor'] is None or point(lane['anchor']))
                    and integer(lane['run_count']) and integer(lane['pending_count']))
        elif mode == 'entries':
            require(type(tid) is int and set(row) == {'time','stable','pending','samples','outside','last_entry'}
                and time_value(row['time']) and time_value(row['last_entry'], True)
                and all(v is None or type(v) is bool for v in (row['stable'],row['pending']))
                and integer(row['samples']) and (row['outside'] is None or point(row['outside'])))
        else:
            require(set(row) == {'last_time','anchor','side','updates','last_cross_time'}
                and time_value(row['last_time']) and time_value(row['last_cross_time'], True)
                and point(row['anchor']) and type(row['side']) is int and row['side'] in (-1,0,1)
                and integer(row['updates'], 1))


def dump_engine(engine):
    counters = {}
    for zid, counter in engine.stream.counters.items():
        require(counter.events == [])
        row = dict(tracks=counter._tracks, count=counter.count)
        if hasattr(counter, 'lane_counts'):
            row['lane_counts'] = counter.lane_counts
        validate_counter(counter, row, engine.stream.zones[zid].get('counter_mode','line'))
        counters[zid] = row
    state = dict(clock=vars(engine.clock), origin=engine.stream.origin, counters=counters,
        quality={zid:q.histories for zid,q in engine.stream.quality.items()},
        trackers={zid:tracker_dump(tr) for zid,tr in engine.trackers.items()})
    return encode_tree(state, engine.np)


def restore_engine(engine, encoded):
    state = decode_tree(encoded, engine.np)
    require(type(state) is dict and set(state) == {'clock','origin','counters','quality','trackers'})
    require(finite(state['origin'], -180, 86580))
    clock = state['clock']
    require(type(clock) is dict and set(clock) == {'last','end','owned_begin'}
        and all(finite(v, -180, 86580) for v in clock.values())
        and state['origin'] <= clock['last'] < clock['end']
        and state['origin'] <= clock['owned_begin'] <= clock['end'])
    engine.reset(state['origin'])
    require(type(state['counters']) is dict and set(state['counters']) == set(engine.stream.counters)
        and type(state['trackers']) is dict and set(state['trackers']) == set(engine.trackers)
        and type(state['quality']) is dict and set(state['quality']) == set(engine.stream.quality))
    for key, value in clock.items():setattr(engine.clock, key, value)
    for zid, counter in engine.stream.counters.items():
        row = state['counters'][zid]
        validate_counter(counter, row, engine.stream.zones[zid].get('counter_mode','line'))
        counter._tracks, counter.count = row['tracks'], row['count']
        if hasattr(counter,'lane_counts'):counter.lane_counts = row['lane_counts']
    for zid, quality in engine.stream.quality.items():
        histories = state['quality'][zid]
        require(type(histories) is OrderedDict and len(histories) <= 500)
        for tid, history in histories.items():
            require(type(history) is deque and history.maxlen == 96 and 0 < len(history) <= 96)
            for obs in history:
                require(type(obs) is tuple and len(obs) == 3)
                quality.observe(tid, obs[1], obs[0], obs[2])
        require(quality.histories == histories)
        quality.histories = histories
    for zid, tracker in engine.trackers.items():tracker_restore(tracker, state['trackers'][zid], engine.np)


def checkpoint_path(root, source_ref):
    require(type(source_ref) is str and HEX.fullmatch(source_ref))
    folder = Path(root)/'checkpoints'
    folder.mkdir(mode=0o700, exist_ok=True)
    s = folder.lstat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077)
    return folder/(source_ref+'.json')


def write_checkpoint(engine, source_ref, input_sha256):
    from tools.ft_day_count import config_digest
    data = dict(schema=1, config_sha256=config_digest(engine.config), runtime=engine.runtime_digest,
        reference_sha256=engine.reference_sha256, source_ref=source_ref,
        input_sha256=input_sha256, state=dump_engine(engine))
    text = json.dumps(data, ensure_ascii=True, separators=(',',':'), allow_nan=False)
    require(len(text.encode()) <= MAX_BYTES)
    path = checkpoint_path(engine.root, source_ref)
    atomic_write(path, text)
    return dict(source_ref=source_ref, sha256=hashlib.sha256(text.encode()).hexdigest(),
                runtime=engine.runtime_digest, coverage_end=engine.clock.end, input_sha256=input_sha256)


def read_checkpoint(root, checkpoint):
    require(type(checkpoint) is dict and set(checkpoint) == {'source_ref','sha256','runtime','coverage_end','input_sha256'})
    require(all(type(checkpoint[k]) is str and HEX.fullmatch(checkpoint[k]) for k in ('source_ref','sha256','runtime','input_sha256'))
        and finite(checkpoint['coverage_end'], -180, 86580))
    path = checkpoint_path(root, checkpoint['source_ref']);s=path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o077
        and s.st_nlink == 1 and s.st_size <= MAX_BYTES)
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == checkpoint['sha256'])
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result);result[key]=value
        return result
    def small_int(text):
        require(len(text)<=20)
        return int(text)
    def small_float(text):
        require(len(text)<=64)
        value=float(text);require(math.isfinite(value));return value
    data = json.loads(raw,object_pairs_hook=pairs,parse_int=small_int,parse_float=small_float,
        parse_constant=lambda _:(_ for _ in ()).throw(StateError('nonfinite checkpoint JSON')))
    require(type(data) is dict and set(data) == {'schema','config_sha256','runtime','reference_sha256','source_ref','input_sha256','state'}
        and type(data['schema']) is int and data['schema'] == 1
        and data['source_ref'] == checkpoint['source_ref'] and data['runtime'] == checkpoint['runtime']
        and data['input_sha256'] == checkpoint['input_sha256'])
    return data


def load_checkpoint(engine, checkpoint):
    from tools.ft_day_count import config_digest
    data = read_checkpoint(engine.root, checkpoint)
    require(data['config_sha256'] == config_digest(engine.config) and data['runtime'] == engine.runtime_digest
        and data['reference_sha256'] == engine.reference_sha256)
    restore_engine(engine, data['state'])
    require(engine.clock.end == checkpoint['coverage_end'])
