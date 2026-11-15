"""Bounded, geometry-only evidence checks for anonymous passage candidates."""
from collections import OrderedDict, deque
import math

from tools.ft_count import ValidationError, _is_finite_point, MAX_TRACK_GAP_S

VERSION = 'bbox_continuity_v1'
HEIGHT_RATIO = 1.8
AREA_RATIO = 2.5
JUMP_DISTANCE = .12
JUMP_WINDOW_S = .4
TIME_EPSILON = 1e-6
HISTORY_SECONDS = 6.0
HISTORY_UPDATES = 96
MAX_TRACKS = 500
MAX_REVIEW_EVENTS = 1000
REASONS = frozenset(('missing_anchor', 'observation_gap', 'box_shape_change', 'center_jump'))


def policy():
    return dict(version=VERSION, height_ratio=HEIGHT_RATIO, area_ratio=AREA_RATIO,
                jump_distance=JUMP_DISTANCE, jump_window_seconds=JUMP_WINDOW_S,
                time_epsilon=TIME_EPSILON, history_seconds=HISTORY_SECONDS,
                history_updates=HISTORY_UPDATES, max_tracks=MAX_TRACKS,
                max_gap_seconds=MAX_TRACK_GAP_S, max_review_events=MAX_REVIEW_EVENTS)


class TrackEvidence:
    """Assess candidates without changing IDs, cooldowns or candidate generation.

    Boxes are required in this opt-in mode. A review result is uncertainty,
    not evidence that the candidate was a false passage.
    """
    def __init__(self):
        self.histories = OrderedDict()

    def observe(self, track_id, point, t, box):
        if not isinstance(track_id, (int, str)) or isinstance(track_id, bool):
            raise ValidationError('invalid track id')
        if type(t) not in (int, float) or not math.isfinite(t) or t < 0:
            raise ValidationError('invalid evidence time')
        if not _is_finite_point(point) or any(not 0 <= v <= 1 for v in point):
            raise ValidationError('invalid evidence point')
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
                or box[2] - box[0] <= 1e-6 or box[3] - box[1] <= 1e-6):
            raise ValidationError('valid detection box required for track quality')
        if not (box[0] - .0002 <= point[0] <= box[2] + .0002
                and box[1] - .0002 <= point[1] <= box[3] + .0002):
            raise ValidationError('evidence point outside box')
        history = self.histories.pop(track_id, deque(maxlen=HISTORY_UPDATES))
        if history and t <= history[-1][0]:
            raise ValidationError('evidence times must increase')
        while history and t - history[0][0] > HISTORY_SECONDS + TIME_EPSILON:
            history.popleft()
        history.append((t, tuple(point), tuple(box)))
        self.histories[track_id] = history
        while len(self.histories) > MAX_TRACKS:
            self.histories.popitem(last=False)

    def assess(self, event):
        history = list(self.histories.get(event['track_id'], ()))
        start = tuple(event['evidence']['from'])
        end = tuple(event['evidence']['to'])
        if (not history or abs(history[-1][0] - event['time_seconds']) > TIME_EPSILON
                or history[-1][1] != end):
            raise ValidationError('candidate confirmation does not match evidence')
        anchors = [i for i, (_, p, _) in enumerate(history[:-1]) if p == start]
        if not anchors:
            return dict(reasons=['missing_anchor'], observations=len(history))
        samples = history[anchors[-1]:]
        reasons = set()
        for (ta, pa, ba), (tb, pb, bb) in zip(samples, samples[1:]):
            ha, hb = ba[3] - ba[1], bb[3] - bb[1]
            aa, ab = (ba[2] - ba[0]) * ha, (bb[2] - bb[0]) * hb
            if max(ha / hb, hb / ha) > HEIGHT_RATIO or max(aa / ab, ab / aa) > AREA_RATIO:
                reasons.add('box_shape_change')
            gap = tb - ta
            if gap > MAX_TRACK_GAP_S + TIME_EPSILON:
                reasons.add('observation_gap')
            if gap <= JUMP_WINDOW_S + TIME_EPSILON and math.dist(pa, pb) > JUMP_DISTANCE:
                reasons.add('center_jump')
        return dict(reasons=sorted(reasons), observations=len(samples))
