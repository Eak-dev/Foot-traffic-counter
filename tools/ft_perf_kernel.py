#!/usr/bin/env python3
"""Experimental, lazily-imported numpy acceleration helpers for OD70.

These are NOT a production backend: ``ft_count._decode_yolox`` and the
``_letterbox``/blob code in ``ft_count._run_pipeline`` are untouched and
remain the source of truth. Everything here exists to let a caller that
already has numpy loaded reuse cached anchor grids and avoid an extra
array copy, while staying numerically identical to the production code
for the same inputs.

No numpy import happens at module import time: every function/class here
takes the already-imported numpy module as its first argument, exactly
like the production helpers in ``ft_count`` do.

Contract: every public function/method here validates its own inputs
(shape, dtype, finiteness, numeric ranges) and raises
``KernelValidationError`` on anything outside that contract. For any
input accepted by that validation, output is byte-identical to the
corresponding production code path.
"""
from __future__ import annotations

import math

INPUT_SIZE = 640
STRIDES = (8, 16, 32)
DET_SCORE_FLOOR = 0.1


class KernelValidationError(ValueError):
    """Raised for invalid inputs to the helpers in this module."""


def _is_finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


MAX_DECODER_SIZE = 4096


def _validate_decoder_size(size):
    if type(size) is not int:
        raise KernelValidationError("size must be an int")
    if size <= 0:
        raise KernelValidationError("size must be positive")
    if size % 32 != 0:
        raise KernelValidationError("size must be a multiple of 32")
    if size > MAX_DECODER_SIZE:
        raise KernelValidationError(f"size must be <= {MAX_DECODER_SIZE}")


class YoloXDecoder:
    """Caches YOLOX anchor grids/strides and decodes raw model output.

    Numerically equivalent to ``ft_count._decode_yolox`` for the same
    ``(output, scale, conf_floor)`` inputs: same kept-row order, same
    person-score formula and `>=` threshold edge, and the same single
    float32-rounding point on the decoded coordinates (production rounds
    once by assigning a float64 intermediate into a float32 array slot;
    this class rounds once via an explicit ``.astype(np.float32)`` at the
    same place in the computation). The only behavioral difference is
    that coordinates are decoded only for rows that pass the score mask,
    since per-row decode math does not depend on any other row.
    """

    def __init__(self, np_module, size=INPUT_SIZE):
        _validate_decoder_size(size)
        self._np = np_module
        self.size = size
        self._strides = STRIDES
        self._grids = None
        self._expanded_strides = None
        self._n_anchors = None
        self._build_anchors()

    def _build_anchors(self):
        np = self._np
        grids = []
        expanded_strides = []
        hsizes = [self.size // s for s in self._strides]
        wsizes = [self.size // s for s in self._strides]
        for hsize, wsize, stride in zip(hsizes, wsizes, self._strides):
            xv, yv = np.meshgrid(np.arange(wsize), np.arange(hsize))
            grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
            grids.append(grid)
            shape = grid.shape[:2]
            expanded_strides.append(np.full((*shape, 1), stride))
        self._grids = np.concatenate(grids, 1)[0]
        self._expanded_strides = np.concatenate(expanded_strides, 1)[0]
        self._n_anchors = self._grids.shape[0]

    def decode(self, output, scale, conf_floor=DET_SCORE_FLOOR):
        np = self._np

        if not isinstance(output, np.ndarray):
            raise KernelValidationError("output must be an ndarray")
        if output.dtype != np.float32:
            raise KernelValidationError("output must be float32")
        if output.ndim != 3 or output.shape[0] != 1 or output.shape[2] != 85:
            raise KernelValidationError("output must have shape [1, N, 85]")
        if output.shape[1] != self._n_anchors:
            raise KernelValidationError(
                "output anchor count does not match this decoder's size"
            )
        if not np.isfinite(output).all():
            raise KernelValidationError("output contains non-finite values")
        if not _is_finite_number(scale) or scale <= 0:
            raise KernelValidationError("scale must be a finite positive number")
        if not _is_finite_number(conf_floor):
            raise KernelValidationError("conf_floor must be a finite number")

        preds = output[0]
        obj = preds[:, 4]
        person_cls = preds[:, 5]
        with np.errstate(over="ignore"):
            scores = obj * person_cls
        if not np.isfinite(scores).all():
            raise KernelValidationError(
                "score computation overflowed to a non-finite value"
            )
        keep = scores >= conf_floor

        if not np.any(keep):
            return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)

        raw = preds[keep, :4]
        kept_grids = self._grids[keep]
        kept_strides = self._expanded_strides[keep]
        kept_scores = scores[keep].astype(np.float32)

        cxcy = ((raw[:, :2] + kept_grids) * kept_strides).astype(np.float32)
        with np.errstate(over="ignore"):
            wh = (np.exp(raw[:, 2:4]) * kept_strides).astype(np.float32)

        cx, cy = cxcy[:, 0], cxcy[:, 1]
        w, h = wh[:, 0], wh[:, 1]
        x1 = (cx - w / 2) / scale
        y1 = (cy - h / 2) / scale
        x2 = (cx + w / 2) / scale
        y2 = (cy + h / 2) / scale
        boxes = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)

        if not np.isfinite(boxes).all():
            raise KernelValidationError(
                "decoded box coordinates overflowed to a non-finite value"
            )

        return boxes, kept_scores


def contiguous_blob(np_module, canvas):
    """Build the onnxruntime input blob from a letterboxed uint8 canvas.

    Byte-identical to
    ``canvas.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)`` from
    ``ft_count._letterbox``/``_run_pipeline``, except the result is forced
    C-contiguous. Production's ``.astype`` with the default ``order='K'``
    on the transposed HWC view does NOT produce a C-contiguous array (it
    preserves the view's own non-contiguous iteration order); this
    function instead builds the transposed view and copies it straight
    into a C-contiguous float32 array with a single allocation.
    """
    np = np_module

    if not isinstance(canvas, np.ndarray):
        raise KernelValidationError("canvas must be an ndarray")
    if canvas.dtype != np.uint8:
        raise KernelValidationError("canvas must be uint8")
    if canvas.ndim != 3 or canvas.shape[2] != 3:
        raise KernelValidationError("canvas must be HWC with 3 channels")
    if canvas.shape[0] <= 0 or canvas.shape[1] <= 0:
        raise KernelValidationError("canvas height and width must be positive")

    transposed = canvas.transpose(2, 0, 1)[np.newaxis, ...]
    return np.ascontiguousarray(transposed, dtype=np.float32)
