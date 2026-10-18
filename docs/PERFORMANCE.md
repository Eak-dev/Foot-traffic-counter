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

## Additional research and backend screen (2026-10-18)

Owner requested further research after authorizing offline experiments. Three
independent read-only reviews covered execution backends, alternative person
detectors and temporal filtering. The table ranks practical work on the current
Intel Mac; it does not authorize packages or claim a production replacement.

| Approach | Practical evidence / next gate | Main limitation |
|---|---|---|
| CoreML MLProgram with the original FP32 YOLOX_s | Installed ORT supports this separate format; bounded local numeric screen succeeds. Compare full events before any integration. | Small numerical errors can change thresholds/tracks; full-day quality and throughput remain unverified. |
| Motion gating per zone, then optical flow between detector frames | Existing OpenCV can screen whether enough detector work could be omitted; begin in shadow mode. | Event recordings may contain little idle time; missed triggers, small people and drift can lose crossings. |
| NanoDet-Plus-m-1.5x416 | Official OpenCV Zoo FP32 ONNX/adapter is available; no new inference runtime is necessary in principle. Different architecture from tested YOLOX Nano/Tiny. | Not downloaded or measured here; COCO scores are not counting accuracy at this store. |
| Retail/person-specialized MobileNet SSD | retail-0013:544x320/2.30GFLOPs; person-0202:512x512/3.143GFLOPs. | Official assets are OpenVINO IR, not drop-in ONNX. Current OpenVINO no longer supports Intel macOS; older runtime setup is separate work. |
| ncnn FP32/Vulkan through MoltenVK | Possible macOS x86 build path for existing model family. | Requires new toolchain/runtime/conversion and actual GPU compatibility proof; no local experiment performed. |

### Why another CoreML test is different

The retained scripts for the earlier rejected CoreML trial explicitly selected
`ModelFormat=NeuralNetwork`, including its CPU-only diagnostic. They did not
test `MLProgram`. Apple documents that NeuralNetwork intermediate precision
depends on execution hardware, whereas MLProgram explicitly types intermediate
tensors and can execute a float32-typed model on GPU without reducing precision.
This makes MLProgram a distinct candidate; it does not prove precision caused
the earlier counting differences. See [Apple typed execution](https://apple.github.io/coremltools/docs-guides/source/typed-execution.html).

The installed ORT1.23.2 exposes the needed options without coremltools or a
package change. The screen selects `MLProgram`, `CPUAndGPU`, static shapes and
`AllowLowPrecisionAccumulationOnGPU=0`, using the original hash-verified FP32
ONNX model and a new private cache bound to the model/options. Source:
[pinned ORT options](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.23.2/include/onnxruntime/core/providers/coreml/coreml_provider_factory.h),
[pinned model builder](https://raw.githubusercontent.com/microsoft/onnxruntime/v1.23.2/onnxruntime/core/providers/coreml/builders/model_builder.cc),
[provider/cache documentation](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html).

One retained source frame, the same crop as the previous backend screen, five
repeated calls per provider, inside a deny-network subprocess with180s limit:

| Provider | Session initialization | First prediction | Warm predictions, four calls |
|---|---:|---:|---:|
| CPU,2threads |0.244s|0.298s|0.266–0.286s|
| CoreML MLProgram |4.277s|9.703s|0.090–0.105s|

The output tensors are float32, maximum absolute difference0.00002563,
mean absolute difference0.00000006083; all values satisfy `rtol=atol=1e-4`,
but are not bit-identical. ORT profiling records five CoreML-provider execution
events. This proves execution through that provider, not which CPU/GPU units
CoreML dispatches internally. No complete intermediate-dtype audit was done.
Single-frame similarity and warm latency are screening evidence only, not an
event-compatibility, sustained speed or human-accuracy result. Setup and first
prediction must be included when assessing shorter jobs.

The subsequent full retained180s source completes900sampled frames and1800
detector calls in344.033s processing, with3.235s session/engine setup.
Detection/pre/postprocessing accounts for314.241s of that processing time.
The unchanged crops,5fps, model, tracker and gates produce near14/far4,
front18accepted/5review and side27accepted/0review. All50reference events match
one-to-one with **zero timestamp difference**, zero missing and zero extra at
tolerance0. The source clock is rebased from the stored reference origin;
source/config hashes match the earlier full reference and fresh CPU prefix.

This is the first alternative in these trials to preserve every reference
event on the full retained source. It is still only one noon clip and an
algorithmic reference, not manual accuracy validation. The old CPU full-source
measurement454.595s was a separate run under variable load: no controlled
full-source speed ratio is claimed. The full-clip344.033s result supersedes
using the roughly3x warm single-frame improvement as a throughput prediction.
Processing180s of footage in344s does not meet the necessary10h/day budget.
Combining it with validated temporal savings or another detector requires a
new measured experiment; no speed factors may be multiplied without evidence.

Both bounded probe processes ended successfully. The saved full report names
the candidate `coreml_mlprogram_fp32` and explicitly records provider options,
experimental override, original runtime source digest and ineligible production
status. No production backend or checkpoint has been changed. Reuse the
measurement path only as a separate offline experiment; any future production
integration must bind provider/options into its runtime identity and resolve
state compatibility explicitly.

### Temporal filtering needs a measured savings budget

First measure per-zone retained detector-call fractions without changing any
tracking input. Keep5fps during active windows, include full warm-up and union
pre/post-roll windows, and assess necessary track history rather than merely
one retained frame near each event. Missing a reference event window rejects a
threshold; absent context evidence is UNKNOWN. The50reference events include
review and two zones; they are not50independent human-labeled people.

For illustration, if detection consumes96% of runtime, keeping one call in five
has an ideal ceiling of `1/(0.04+0.96/5)=4.31x` before filtering/flow overhead.
Exceeding5x would require retaining less than one sixth of detector cost.
Do not equate unweighted frame/call reduction with measured wall-time gain.
The actual10h target for63929recorded seconds at5fps requires more than
8.879sampled frames/s. With two detector calls per frame, the average budget
is below56.3ms per call including other processing. This is a necessary
throughput budget, not an extrapolated completion promise.

ByteTrack marks existing tracks that remain unmatched after association as
lost; deliberately skipping a detector cannot simply feed an empty result into
the existing tracker. A
separate prediction/flow path must record observed versus propagated evidence.
OpenCV optical flow requires drift checks and renewed features; MOG2 can absorb
stationary foreground into background. References: [ByteTrack source](https://github.com/FoundationVision/ByteTrack/blob/main/yolox/tracker/byte_tracker.py),
[optical flow](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html),
[MOG2](https://docs.opencv.org/4.x/d7/d7b/classcv_1_1BackgroundSubtractorMOG2.html).
[Reducto](https://www.cs.princeton.edu/~ravian/publications/reducto_sigcomm20.pdf)
and [NoScope](https://arxiv.org/abs/1703.02529) support content-specific filtering
as a research direction; their published speedups are not measurements of this
crossing counter. Blacking out pixels in a fixed-size dense CNN input does not
automatically eliminate computation.

### Alternative model and platform sources

- [NanoDet upstream](https://github.com/RangiLyu/nanodet) and
  [OpenCV Zoo ONNX/adapter](https://github.com/opencv/opencv_zoo/blob/main/models/object_detection_nanodet/README.md).
- [retail-0013](https://docs.openvino.ai/2023.3/omz_models_model_person_detection_retail_0013.html)
  assumes upright people, occlusion below50% and at least100px height on1080p;
  overhead/far/partially visible people need explicit validation.
- [person-0202](https://docs.openvino.ai/2023.3/omz_models_model_person_detection_0202.html),
  [OpenVINO2026.0 x86 macOS support removal](https://github.com/openvinotoolkit/openvino/releases/tag/2026.0.0),
  [platform requirements](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino/system-requirements.html)
  and [2024.6 Intel macOS CPU archive](https://docs.openvino.ai/2024/get-started/install-openvino/install-openvino-archive-macos.html).
- [ncnn macOS build](https://github.com/Tencent/ncnn/wiki/how-to-build) and
  [MoltenVK requirements](https://github.com/KhronosGroup/MoltenVK/blob/main/Docs/MoltenVK_Runtime_UserGuide.md).

No alternative weights, packages, camera requests or authentication were used
for this research/screen. Production sources and the stopped day17 checkpoint
remain unchanged. Research and temporary local probes are PO work;
NOT_RUN_BY_DEVELOPER. New production behavior and manual accuracy remain
NOT_VERIFIED; existing regression evidence above is not a test of a new backend.
