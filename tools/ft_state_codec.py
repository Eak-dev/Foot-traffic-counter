"""Bounded value-only checkpoint codec. No pickle, constructors or imports from data."""
import base64
from collections import OrderedDict, deque
import math


class StateError(ValueError):
    pass


MAX_NODES = 1000000
MAX_DEPTH = 24
DTYPES = frozenset(('<f4', '<f8', '<i4', '<i8', '|b1'))


def _require(condition):
    if not condition:
        raise StateError('invalid checkpoint value')


def _walk(value, np, decode):
    nodes = [0]

    def visit(v, depth=0):
        nodes[0] += 1
        _require(nodes[0] <= MAX_NODES and depth <= MAX_DEPTH)
        if v is None or type(v) is bool:
            return v
        if type(v) is int:
            _require(abs(v) <= 2**63-1)
            return v
        if type(v) is float:
            if not decode and v == -math.inf:
                return ['ninf']
            _require(math.isfinite(v))
            return v
        if type(v) is str:
            _require(len(v) <= 4096)
            return v
        if not decode:
            if np is not None and isinstance(v, (np.ndarray, np.generic)):
                a = np.asarray(v)
                _require(a.dtype.str in DTYPES and a.size <= 4096 and a.ndim <= 3 and bool(np.isfinite(a).all()))
                return ['scalar' if isinstance(v, np.generic) else 'array', a.dtype.str,
                        list(a.shape), base64.b64encode(a.tobytes(order='C')).decode('ascii')]
            if type(v) in (dict, OrderedDict):
                _require(len(v) <= 100000)
                pairs = []
                for k, item in v.items():
                    _require(type(k) in (int, str))
                    pairs.append([visit(k, depth+1), visit(item, depth+1)])
                return ['ordered' if type(v) is OrderedDict else 'dict', pairs]
            if type(v) in (list, tuple, deque):
                _require(len(v) <= 100000)
                seq = [visit(item, depth+1) for item in v]
                if type(v) is deque:
                    _require(type(v.maxlen) is int and 0 < v.maxlen <= 100000)
                    return ['deque', v.maxlen, seq]
                return ['tuple' if type(v) is tuple else 'list', seq]
            raise StateError('unsupported checkpoint type')
        _require(type(v) is list and 1 <= len(v) <= 4 and type(v[0]) is str)
        tag = v[0]
        if tag == 'ninf':
            _require(len(v) == 1)
            return -math.inf
        if tag in ('array', 'scalar'):
            _require(len(v) == 4 and np is not None and type(v[1]) is str and v[1] in DTYPES)
            shape = v[2]
            _require(type(shape) is list and len(shape) <= 3
                     and all(type(n) is int and 0 <= n <= 4096 for n in shape))
            size = math.prod(shape)
            _require(size <= 4096 and (tag != 'scalar' or shape == []))
            dtype = np.dtype(v[1]); expected = size*dtype.itemsize
            _require(type(v[3]) is str and len(v[3]) == 4*((expected+2)//3))
            try:
                raw = base64.b64decode(v[3], validate=True)
            except (ValueError, TypeError):
                raise StateError('invalid checkpoint array') from None
            _require(len(raw) == expected)
            a = np.frombuffer(raw, dtype=dtype).reshape(shape).copy()
            _require(bool(np.isfinite(a).all()))
            return a[()] if tag == 'scalar' else a
        _require(tag in ('dict', 'ordered', 'list', 'tuple', 'deque'))
        _require(len(v) == (3 if tag == 'deque' else 2))
        seq = v[-1]
        _require(type(seq) is list and len(seq) <= 100000)
        if tag in ('dict', 'ordered'):
            result = OrderedDict() if tag == 'ordered' else {}
            for pair in seq:
                _require(type(pair) is list and len(pair) == 2)
                k = visit(pair[0], depth+1)
                _require(type(k) in (int, str) and k not in result)
                result[k] = visit(pair[1], depth+1)
            return result
        result = [visit(item, depth+1) for item in seq]
        if tag == 'tuple':
            return tuple(result)
        if tag == 'deque':
            _require(type(v[1]) is int and len(result) <= v[1] <= 100000 and v[1] > 0)
            return deque(result, maxlen=v[1])
        return result

    return visit(value)


def encode_tree(value, np=None):
    return _walk(value, np, False)


def decode_tree(value, np=None):
    return _walk(value, np, True)
