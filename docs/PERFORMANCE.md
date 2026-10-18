# Offline throughput experiments (OD-68)

Owner authorized experiments after the proposal to test smaller detectors,
shared detection and INT8. This work uses retained local media, existing
packages and free public ONNX weights. No camera requests, new login, hosted
inference, package installation, hardware purchase or future-day scheduler.

The existing date17 result remains a separate stopped64/503-source partial
ledger. Its pinned runtime and checkpoints are preserved. The experiment tool
is not a selectable day-job backend and cannot promote a candidate into an
existing checkpoint. Every experiment report carries `experiment_only=true`,
`production_eligible=false` and `accuracy_status=NOT_VERIFIED`.

## What is measured

`tools.ft_perf` retains5fps, existing tracking, zones and quality gates. Each
candidate runs separately on the same local Fixed recording inside a macOS
deny-network worker. Timing separates initialization, total processing and
detection/preprocessing/postprocessing time. No annotated video is generated.
Only owner-only numeric/event reports are written outside Git.

The baseline uses the actual production detector implementation. Candidates:

- `nano` / `tiny`: upstream416x416 detectors, same per-zone crops.
- `joint`: one640x640 detection on the union crop, then separate zone trackers.
- `nano_tiles`: four overlapping416x416 tiles per zone, merged with NMS, to
  investigate whether larger image detail offsets the smaller detector.
- `int8` / `int8bq`: quantized variants of the current OpenCV Zoo model.

`compare_events` matches events one-to-one by zone, lane, accepted/review and
time (default tolerance0.4s). Identical totals with missing/extra or shifted
events do not pass. Agreement means compatibility with the reference
algorithm only; it does not establish manually verified counting accuracy.
One noon source cannot establish morning/night, occlusion or whole-day quality.

The loop follows half-open time ownership, including fractional source fps
whose timestamp rounds to the requested endpoint. Cached test results from the
initial101-frame20s screen are superseded by this fix; full-source validation
uses900sampled frames. The legacy-normalization trial is also invalid: the
published Nano/Tiny assets use raw BGR0–255, as in current upstream inference,
rather than the older release tag's RGB/ImageNet-normalized preprocessing.

## Reproduction

Use the installed isolated counting Python. Supply explicitly selected local
input/config/reference and a new owner-only output directory outside Git:

```text
python -m tools.ft_perf --candidate baseline --input <local-fixed.mp4> \
  --config <private-zones.json> --reference <local-fixed-reference.mp4> \
  --output <new-private-experiment-directory> --seconds 180
```

The CLI launches a deny-network subprocess before inference imports. Models
are not automatically downloaded. The tool checks the exact model SHA256 and
input/output tensor contract; only pinned candidates are accepted. A source
is at most180seconds, an experiment has a30minute deadline, and event/output
quotas remain bounded. This is a measurement tool, not a whole-day estimate
or an automatic retry of the stopped job.

## Model provenance

Weights remain ignored local files and are not redistributed in this PR.
All use Apache-2.0; see [existing full license](licenses/YOLOX-APACHE-2.0.txt).

| Candidate | SHA256 | Source |
|---|---|---|
| Nano | `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` | [YOLOX release asset](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx) |
| Tiny | `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7` | [YOLOX release asset](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx) |
| INT8 | `01a3b0f400b30bc1e45230e991b2e499ab42622485a330021947333fbaf03935` | [OpenCV Zoo pinned source](https://github.com/opencv/opencv_zoo/blob/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox/object_detection_yolox_2022nov_int8.onnx) |
| INT8bq | `dcaae0aaa2fea4167f89235ee340eb869d3707b25712218d4c7ce921ac90e2ba` | [OpenCV Zoo pinned source](https://github.com/opencv/opencv_zoo/blob/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox/object_detection_yolox_2022nov_int8bq.onnx) |

INT8 hashes and lengths match upstream Git LFS pointers. YOLOX release tag
resolves to `e1052df71842031413f6030723c3607b839c80ce`; the asset's own hash is
the binding identity. See [current preprocessing](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/yolox/data/data_augment.py)
and [ONNX Runtime quantization caveats](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).

## Findings

Full retained noon source,900sampled frames, identical source SHA256 and zone
configuration. The reference is the previously validated stored50-event CPU
result. A fresh20s baseline replay reproduces its first8events exactly after
rebasing the source clock, including lanes/status/timestamps. This was not a
new full-source baseline timing run.

| Detector | Near | Far | Front accepted | Front review | Side accepted | Processing seconds |
|---|---:|---:|---:|---:|---:|---:|
| Current CPU reference |14|4|18|5|27|454.595 (previous measurement)|
| Nano |11|7|18|3|6|60.774 (new run)|
| Tiny |12|10|22|1|14|153.691 (new run)|

Side review is0in all three. Timings exclude initialization. These are single
runs under variable machine load, not a controlled sustained-throughput
comparison or a whole-day completion estimate. For example, baseline20s
processing varied from33.98s in the initial screen to84.66s in the final replay;
a cold private font cache added47.51s of setup in that final replay. Production
already reuses the day worker/cache, so this setup observation is not a new
production speed improvement.

At0.4s event tolerance, Nano matches14reference events with36missing/13extra;
Tiny matches20with30missing/17extra. These are differences from the algorithmic
reference, not human-labeled false-negative/false-positive measurements. Nano's
matching front accepted total18conceals lane, review and event differences.
Neither candidate is accepted for production despite the lower measured time.

Joint detection and tiled Nano already change event counts/times in short
screening. The full joint trial was stopped after7m57s because that method
already failed the screen; no complete180s joint result or timing is claimed.
The queued redundant full baseline run was not started. Final half-open20s
screens are retained privately; no candidate was promoted.

Final20s/100frame screen, same source/crops/gates:

| Method | Processing seconds | Front accepted/review | Side accepted | Matched/missing/extra vs baseline |
|---|---:|---:|---:|---:|
| Baseline |84.665|4/0|4|8/0/0|
| Joint |43.358|4/0|3|5/3/2|
| Tiled Nano |32.357|2/3|5|4/4/6|

These timings also exclude cold-cache setup. Missing/extra refer to algorithmic
events within0.4s, not unique-person or manual ground-truth errors.

INT8 screening was stopped after more than3minutes on only20seconds of source,
already much slower than the float baseline; no completed count is claimed.
INT8bq fails in installed ONNX Runtime1.23.2 at a `DequantizeLinear` operator:
`block_size must be 0 for per-tensor quantization`. This is an experimental
model/runtime compatibility failure, not an authentication or camera failure.
No package was upgraded to bypass it.

The practical next gate is a representative human-labeled local validation set
(including far-lane pedestrians, occlusion and different lighting). The retained
noon source is sufficient to reject automatic substitution here, but cannot
establish a smaller model's store-wide accuracy. The under10hour daily target
has not been achieved with acceptable evidence; production stays unchanged.

PO regression:867tests in132.582s,857PASS/10optional-runtimeSKIP. New benchmark
suite in isolated runtime:11PASS/0.440s, covering its2numerical tests skipped by
system Python. Existing8counting-runtime skips concern unchanged sources with
prior pinned-runtime evidence. Python3.9 syntax and diff whitespace checks pass.
Claude scoped invocation returned NOT_LOGGED_IN (exit1/2.0s), with no changes or
retained lock; final implementation/review/tests are PO, NOT_RUN_BY_DEVELOPER.
