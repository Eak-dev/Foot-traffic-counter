# Offline throughput experiments (OD-68 / OD-69 / OD-70)

## OD-71: actual day-driver integration, 2026-10-20

Owner approved the FP32 batch2 worker for one fresh date17 full-day trial.
The actual day CLI now selects the isolated backend explicitly and binds its
reference/config/runtime/checkpoint. Default offline mode still rejects day
ledgers. No CPU fallback or checkpoint migration is implemented; changing the
day driver intentionally invalidates the old CPU source fingerprint while
preserving that stopped ledger and snapshot as historical evidence.

A private local integration test ran four actual driver invocations: first10s,
wrong backend, wrong reference, and new-process resume for the adjacent10s.
Only session/inventory/acquisition were synthetic; the real deny-network worker,
counting, atomic ledger commit, snapshot restore, CLI and reporting ran unchanged.
The two positive invocations used one CoreML worker at a time, committed cursors1
and2, and retained all5semantic events plus exact encoded active tracker/counter
state from the earlier native CPU/CoreML controls. Both negative invocations
stopped before session/target/inventory/download/worker and preserved ledger,
checkpoint and staged-work bytes. No camera request was made by this test.
Positive invocation times16.838s and14.120s include startup/fixture-copy/reporting;
these are integration checks, not a new throughput benchmark.

PO final regression1067tests in13.711s:931PASS/136optionalSKIP. Dependency suite
201tests in18.918s:201PASS/0SKIP covers all skipped modules. Python3.9AST,
diff checks and independent static driver/worker reviews pass. Claude's scoped
edit task ended exit3/RESULT_PERMISSION_DENIALS despite child0; PO completed
integration/guards/tests and independently verified the final implementation.

Two current readonly date17 inventory sweeps still return503clips/63929seconds,
166groups,00:04:05–23:51:53Bangkok. Existing session reused without login or
explicit refresh. Original CPU64/503ledger bytes remain unchanged. Before launch,
free disk was32GiB; a native CoreML case used about103MiB cache. Keep existing
350MiB/job,1GiB approved job-root aggregate and10GiB free-space checks. Numeric
CoreML report filenames remain distinct from historical CPU reports.

This is READY_TO_START after a reviewed publication checkpoint. The OD70
six-clip25.931% processing reduction remains the measured comparative evidence;
whole-day timing/completion, whole-machine energy, human accuracy and a daily
runtime below10hours are not established. Runtime sources stay frozen once
started; completion follow-up monitors this one job only.


## OD-70 continuation: real-video validation, 2026-10-20

Owner subsequently approved the bounded sample request. Six date17 Fixed clips
were downloaded using the existing session: 858seconds total, 131877042bytes.
The earlier source/reference hashes could not be recovered identically; the
new noon source is a separately hash-bound reference. Original-reference
continuity remains UNVERIFIED. All six pass the existing static-lens check
relative to that reference; local OSD recognition supports Fixed Lens, but
does not verify every date/time. No image, video, config or state was uploaded.

The isolated video experiment now supports same-frame two-zone batch2. Both
results are validated before either tracker advances; original5fps clocks,
zone order, separate trackers and counting gates are preserved. The report
and identity include the reference SHA. Production sources/checkpoints stay
frozen. The completed full-source comparison below supersedes short-screen
and synthetic speed estimates.

Claude delivered partial source before a600second timeout. A second test-only
call delivered tests but reported FAILED/RESULT_PERMISSION_DENIALS for shell
commands outside its approved command list. PO corrected test doubles and
expanded timing/anchor/empty-zone/atomic-failure coverage. Independent static
review finds no remaining blocker. Numerical tests pass after those corrections;
final regression and media evidence will be recorded below.

### Completed 20second screen on newly acquired source

Four sequential100sampled-frame runs retained the same5 events exactly,
including lane/status/time/review reasons. A later FP16 run also matched those
5 events, but was slower and used more CPU than FP32 CoreML. These short runs
are screening evidence, not whole-day throughput or manually labeled accuracy.

| Variant | Processing seconds | Whole-worker CPU core-seconds | Peak worker MiB |
|---|---:|---:|---:|
| CPU4 / legacy |32.775566|132.138398|383.766|
| CPU4 / cached kernel |35.340016|143.868109|384.871|
| CoreML / person6 / batch1 |20.218651|10.058597|405.770|
| CoreML / person6 / batch2 / FP32 |18.728128|8.800403|424.156|
| CoreML / person6 / batch2 / FP16 |28.239077|108.620323|540.785|

FP32 batch2 reduced processing time42.859% relative to the CPU screen. Timing
varies with system load; worker CPU excludes GPU/system-service work and does
not establish reduced whole-machine energy. The six full-source paired runs below used alternating order and60second rests.
Their aggregate gain is smaller; the short-screen42.859% is not the selected
performance claim.

FP16 is separately opt-in (`--precision fp16`, CoreML MLProgram only). The
original weights are immutable; a hashed derivative retains FP32 I/O. The
helper rejects unsupported/external/sparse/nonfinite graphs, preserves exact
I/O names/shapes, sorts converter-added Cast nodes and uses full ONNX type
checking. ORT1.23.2 requires minimum nonzero clamp5.96e-08;23 source values are
below this threshold, no source value exceeds65504, and no source weight is
nonfinite. This is approximate conversion, not natural underflow or exact
weights. Finite activations and real-event compatibility require separate
checks. Low-precision accumulation remains disabled. No new package was
needed. The FP16 candidate is not selected for the full comparison because
its screen was worse than FP32 on both wall time and measured worker CPU.
After the full comparison was frozen and independently verified, final hardening
of this unselected helper added explicit unsupported tensor-type rejection and
finite scalar/list attribute checks before and after conversion. That source
change creates a new experiment fingerprint; historical timing reports retain
their original identities. It does not change the selected FP32 computation.
The native worker validation below uses the final source identity.

References: [pinned ORT converter](https://github.com/microsoft/onnxruntime/blob/v1.23.2/onnxruntime/python/tools/transformers/float16.py),
[CoreML typed execution](https://apple.github.io/coremltools/docs-guides/source/typed-execution.html),
[ONNX checker](https://github.com/onnx/onnx/blob/v1.19.1/onnx/checker.py).

### Completed full-source comparison

Six distinct local sources total857.861decoded seconds (858inventory seconds),
4290sampled frames per backend. Twelve runs completed in alternating order,
one inference worker at a time, with60second rests. Exact one-to-one comparison
preserves all143events, their zone/lane/status/time and review reasons, with
zero missing, extra or shifted events. Input/config/reference/model/source/
package/environment identities agree across each pair. Opaque event reference
hashes are excluded from the semantic comparison. These are isolated clips
with fresh trackers, not an uninterrupted daily run or human-labeled accuracy.

| Source sample | CPU seconds | CoreML FP32 batch2 seconds | Exact events |
|---|---:|---:|---:|
| Noon |457.324|431.322|29|
| Morning |471.334|391.821|39|
| Late morning |545.099|460.780|35|
| Afternoon |855.016|485.408|30|
| Evening |267.055|140.742|8|
| Night |139.687|116.083|2|
| Total |2735.515|2026.157|143|

Observed summed processing time falls25.931% (1.350x), from45m35.515s to33m46.157s.
Including worker setup/cleanup gives25.527% reduction. Per-pair reductions range
5.686–47.299%; system load was not controlled or constant, so these are measured
sample results, not a guaranteed sustained speedup or an under10hour daily SLA.
The afternoon CPU run's load average rose substantially; this does not establish
which process or thermal condition caused its timing. No whole-day extrapolation
is accepted from this experiment.

Summed worker CPU time falls from10380.292 to719.858core-seconds (93.065% less).
This measures the worker's user+system CPU, excluding GPU and system-service work;
whole-machine energy, temperature and GPU operator coverage remain NOT_MEASURED.
Peak worker RSS rises from387.484 to419.285MiB (+31.801MiB,8.207%). Model calls
halve from8580 to4290 while images inferred stay8580; batch2 does not halve image
compute. Sample observations are near40/far36/front76accepted/10review and
side57accepted/0review. They are passage events, not unique people or a day total.

### Opt-in offline worker

`tools.ft_day_count_accel` reuses the original streaming process, frame clock,
trackers, counters and checkpoint codec. Only inference is replaced by
CoreML FP32 person6 batch2. Both zone results must validate before either
tracker advances. The per-frame cache is consumed in zone order and timing
samples are bounded per clip, not accumulated for a whole day.

This worker requires a fresh private offline root with no day ledger. Existing
snapshots require explicit resume; a repeated source reference is rejected
before counting can change state or overwrite its snapshot. Its runtime
identity binds the original CPU runtime, reference, backend options, derived
model, source, packages and platform. CPU checkpoints cannot be migrated into
this lineage. Network denial and original file/lens/clock checks remain active.

Claude delivered the initial worker and tests. Its launcher ended
`FAILED / RESULT_PERMISSION_DENIALS` after an unapproved compile command;
developer tests are `NOT_RUN_BY_DEVELOPER`. PO reviewed and corrected identity
binding, test doubles, clip timing quotas, strict result validation and root
reuse guards. Independent static review passes. Native resume and continuity validation passes on the final source identity.

The new module is an offline worker, not a selectable backend in the existing
daily downloader/driver. No day job, scheduler or old checkpoint is switched.

Native validation uses the first20seconds of the morning source:300decoded
frames, losslessly re-encoded as one20second file and two10second files. All
300BGR frame hashes match the original, and every sampled timestamp matches
at the existing3decimal precision despite the source's fractional average fps.
The original5fps stride is retained. The larger40second lossless fixture hit
the100MiB file cap and was discarded; the accepted fixtures and original six
sources together occupy277833748bytes, below350MiB.

Four actual deny-network runs cover A=one file, B=two files in one process,
C=two files with clean process exit/restart and explicit resume, D=CPU two-file
control. Each processes100sampled frames and emits5matching event semantics.
An independent comparison also matches all 5 events to the original full-clip
CPU result over [0,20), at zero timestamp tolerance and with identical review reasons.
B and C match every raw event field and both checkpoint files byte-for-byte,
including encoded tracker/counter/quality state. The midpoint contains active
tracker state, so this is not an empty-scene resume test. A/B final state is
identical after normalizing only the expected clip-boundary `clock.owned_begin`;
outer source references and their event hashes intentionally differ. CPU and
accelerated checkpoints are rejected by the opposite worker with exit2 and
`CHECKPOINT_MISMATCH`, before ready/counting, with snapshot bytes unchanged.
This validates the tested20second sequence, not all future gaps/overlaps or a
complete day's accuracy.

Final PO regression:1047tests in12.691s (911PASS/136optional-runtimeSKIP);
196dependency-backed tests in19.479s PASS with no skips, covering every skipped
module. Python3.9 syntax, diff hygiene and independent static reviews pass.
The original counting runtime, model, stopped64/503day ledger and all six source
hashes remain unchanged. No new package installation was required in this
continuation. Whole-day completion below10hours remains NOT_ACHIEVED and
human-labeled accuracy remains NOT_VERIFIED.


Use the isolated environment and an explicitly selected local clip:

```text
python -m tools.ft_perf_accel --backend coreml --kernel cached \
  --person-output --batch-size 2 --precision fp32 --threads 4 \
  --input <local-fixed.mp4> --config <private-zones.json> \
  --reference <selected-fixed-reference.mp4> \
  --seconds <up-to-180> --output <new-private-output>
```

The streaming worker is a separate opt-in process:

```text
sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  python -m tools.ft_day_count_accel --worker \
  --root <fresh-private-offline-root> --config <private-zones.json> \
  --model <pinned-original-model.onnx> --reference <selected-fixed-reference.mp4>
```

Its controller uses the existing JSON-lines protocol: stage a private local
input at `work/fixed.mp4`, provide its hash and a unique source reference with
integer start/end seconds and the correct reset flag, and wait for a completed
checkpoint before replacing the input. EOF closes the worker. Resume requires
the exact saved `--resume-json` descriptor in the same private root, and must
not mix CPU or old-day snapshots. One worker owns a root at a time.

## Earlier OD-70 synthetic checkpoint, 2026-10-20

Owner authorizes necessary free libraries and development with Claude. The
verified machine is an Intel i7-4870HQ MacBookPro11,5, 16 GiB RAM, macOS14.8.9,
not Apple Silicon. The new scope supersedes the old package restriction below.
This checkpoint implements and screens acceleration; it does **not** deliver
a validated faster production counter or an under10hour day.

Real Claude sessions implemented and revised the pure kernel and ONNX graph
helpers. PO reviewed them, corrected test assumptions, integrated the isolated
runner and independently ran dependency-backed tests. Two scoped sessions
completed cleanly. Two others delivered allowed files but their launcher status
was `FAILED / RESULT_PERMISSION_DENIALS` because unnecessary exploratory shell
commands or a temporary test path were denied. No broader permissions were
granted and no lock remains. Do not describe all four launcher results as PASS.

### Implemented changes

- `ft_perf_kernel`: cached YOLOX grids and person-score filtering before box
  decoding; preserved float32 rounding, row order and threshold semantics.
  Blob preparation makes one contiguous allocation.
- `ft_perf_accel`: explicit CPU ORT, CoreML MLProgram/NeuralNetwork and OpenVINO
  CPU backends in fresh workers with network access denied. Six detector-stage
  timers distinguish preprocessing, blob, model, decoding, NMS and output
  construction. Residual time includes video decode, lens verification,
  tracking, counters and loop overhead; it is not attributed solely to decode.
- `ft_perf_projection`: a separately hashed derivative exposes only coordinates,
  objectness and person score (6 of85 columns). An adapter restores unused
  columns as zero for the existing decoder. Original weights remain unchanged.
- A separate batch2 derivative processes two independent640x640 inputs together.
  Three validated head Reshapes copy the input batch dimension. This reduces
  calls, not image compute. At that earlier checkpoint batch2 was synthetic-only.
  The continuation above adds isolated video integration; the day job remains unchanged.
- Experiment identities bind backend options, derived/original model hashes,
  package versions, machine/OS and source hashes. Source changes during a run
  reject the report. Derived files are atomically published in a private cache.
- Exact event comparison checks multiplicity, zone, lane, status, timestamp and
  review reasons. Matching counts alone cannot pass.

Production sources, original counting environment, stopped date17 ledger and
checkpoints remain unchanged. Every new report is experimental, not checkpoint
compatible, not eligible for production and has human accuracy `NOT_VERIFIED`.
The date17 ledger hash and original runtime digest still match their recorded
values. No new camera/authentication request or counting job was started.

### Dependency isolation

The original package set was copied into a separate ignored experiment
environment; its files do not link back to the counting environment. Added
hash-pinned public wheels: OpenVINO2025.4.1, openvino-telemetry2025.2.0,
ONNX1.19.1, ml_dtypes0.5.4 and typing_extensions4.15.0. All34 installed packages
pass dependency checks. Wheel provenance and hashes remain in ignored local
records; no package, model or media binary is committed.

OpenVINO imports can initialize OVC telemetry. Before importing it, the
deny-network worker sets process-local `CI=true`, which this pinned OVC
integration treats as declined consent. It verifies declined consent and an
empty sender queue. No persistent consent or account setting is changed.
OpenVINO runs explicit CPU/FP32/ACCURACY with one stream. This fourth-generation
CPU is outside its documented validated CPU list; successful execution here
does not establish vendor-supported hardware compatibility.

Sources: [OpenVINO system requirements](https://docs.openvino.ai/2024/about-openvino/release-notes-openvino/system-requirements.html),
[pinned OVC telemetry integration](https://github.com/openvinotoolkit/openvino/blob/2025.4.1/tools/ovc/openvino/tools/ovc/telemetry_utils.py),
[CoreML provider](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html).

### Measured screening, not video throughput

Three deterministic synthetic inputs (padding114, checkerboard and seeded
noise), three warmup calls, then30 measured calls per candidate. One worker at
a time; independent short runs under variable system load. Batch1 measures30
images and batch2 measures60. Times below exclude session initialization and
warmup. CPU means this worker's user+system CPU time, not whole-machine work.

| Backend / method | Model ms per image | Processing ms per image | Worker CPU core-s per image |
|---|---:|---:|---:|
| ORT CPU4, legacy |104.403|106.334|0.424305|
| ORT CPU4, cached kernel |104.899|106.311|0.424095|
| CoreML MLProgram, cached kernel |90.973|93.429|0.017314|
| CoreML MLProgram, person6 |88.668|91.119|0.012732|
| CoreML MLProgram, person6/batch2 |84.666|88.124|0.009608|
| OpenVINO CPU4, cached kernel |113.400|114.570|0.450491|
| OpenVINO CPU2, cached kernel |197.472|198.594|0.393435|
| CoreML NeuralNetwork, cached kernel |118.365|120.147|0.052939|

The cached decoder falls from about1.19ms to0.28–0.33ms in this screen, while
total CPU processing remains essentially unchanged: model inference dominates.
The best synthetic batch2 model latency is18.9% below the original CPU screen;
including measured loop work, amortized time is17.1% lower. These are observed
short-run differences, not sustained gains or a daily completion estimate.
Batch2's total processing is5.287434s for60 images, not for30 images.
Its peak worker RSS is312.555MiB versus186.734MiB for the original CPU screen.
GPU/system-service energy, temperature and total computer load are unmeasured.

All synthetic inputs produce **zero retained person detections**. Original ORT
and cached ORT outputs match exactly. CoreML differs from CPU by up to
0.00006038 in used output columns; OpenVINO by0.00019008 and NeuralNetwork by
0.4943275. Threshold masks are unchanged on these empty synthetic detections,
which gives no evidence of actual counting compatibility.

All six batch2 items match the corresponding single-image CoreML person6 used
columns bit-for-bit in this screen. The mapping checked is `(2*batch+i)%3`;
it detects cross-image mixups but does not establish real-video accuracy.
Reports must be keyed by batch size and experiment identity as well as
`candidate`, whose label alone does not distinguish batch1 from batch2.

### Historical reproduction and gate at the synthetic checkpoint

Use the isolated experiment Python with the pinned original local model:

```text
python -m tools.ft_perf_accel --backend ort --kernel legacy --threads 4 \
  --synthetic --iterations 30 --output <new-private-output>
python -m tools.ft_perf_accel --backend coreml --kernel cached \
  --person-output --batch-size 2 --threads 4 \
  --synthetic --iterations 30 --output <different-new-private-output>
```

For an explicitly selected existing clip, batch1 supports the unchanged5fps
video pipeline with input/config/reference arguments and a180second maximum:

```text
python -m tools.ft_perf_accel --backend coreml --kernel cached --person-output \
  --input <local-fixed.mp4> --config <private-zones.json> \
  --reference <local-fixed-reference.mp4> \
  --seconds 180 --output <new-private-output>
```

At that checkpoint, the old temporary180second source and reference video were absent from their
recorded locations and the task-owned temporary folders checked. Retained
numeric reports and the private configuration are not substitutes for footage.
The pending request for up to6 date17 Fixed clips, total18minutes, was subsequently
approved and fulfilled by the continuation above. It is no longer an open Owner
question.

The next step at that checkpoint was repeatable real-clip comparison including far-lane pedestrians,
crowds/occlusion and different light; compare all events and review reasons at
zero tolerance, then obtain human-labeled evidence. The current continuation
implements batch2 in the isolated video experiment and validates it above.
Keep all trackers and event clocks separate. Only representative evidence can
justify a new production backend and fresh state lineage.

PO validation for this checkpoint: system-Python regression956tests in12.931s,
875PASS/81optional-runtimeSKIP. Isolated dependency-backed105tests pass in17.309s
with zero skips, covering all81 skipped cases. Independent static integration
and batch reviews find no blocking issue. Python3.9 syntax and diff checks
pass. Under10h/day remains NOT_ACHIEVED; human accuracy NOT_VERIFIED.

## Historical OD-68 / OD-69 scope and results

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

## Same-clip resource comparison (OD-69,2026-10-19)

Owner requests an actual comparison for counting, speed and lighter computer
load. The existing downloaded180s Fixed source is reused for all candidates;
its source/config hashes and the production runtime are held constant. No new
camera download, login or session change is needed for this one selected clip.

`tools.ft_perf_compare` is a separate opt-in experiment runner. It creates one
fresh deny-network process per candidate, reuses the5fps half-open loop and
original tracker/counters/quality gates, and never loads a day checkpoint.
The scoped constructor adapter creates only the chosen model session; smaller
models are not charged for an unused baseline session. Actual pinned weights
are checked before inference. Candidate output labels and preprocessing are
recorded from their actual execution path, not the underlying baseline loop.

```text
python -m tools.ft_perf_compare --candidate coreml --input <local-fixed.mp4> \
  --config <private-zones.json> --reference <local-fixed-reference.mp4> \
  --output <fresh-private-output> --seconds 180
```

The comparison order is CPU baseline, CoreML MLProgram, YOLOX Nano, YOLOX Tiny,
NanoDet, with60s rest before each. All use4ORT threads/one inter-op thread and
the same preseeded private font cache; CoreML's compiled model cache is prepared
during the short preflight. No OS cache purge, priority/power changes or
concurrent inference/test jobs. Setup, processing and parent launch-to-exit
times are reported separately. This is one sequential screening pass; machine
load/order/thermal variation and long-term throughput are not controlled away.

Worker CPU user+system deltas use the same interval as wall time, starting
before inference-library imports. Average CPU100% means one logical CPU;
CPU core-seconds measure accumulated processor work, not elapsed time.
Darwin `ru_maxrss` is bytes and is reported as the fresh worker's lifetime
peak MiB, never a subtraction of high-water marks. It excludes GPU/shared
system-service memory. Parent launch-to-exit includes interpreter/sandbox/exit
overhead; worker CPU interval excludes interpreter bootstrap. System load is
recorded before/after. GPU activity, energy and temperature are NOT_MEASURED;
CPU reductions alone cannot prove lower total machine power or heat.

NanoDet uses [this pinned public asset](https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_nanodet/object_detection_nanodet_2022nov.onnx),
SHA256`4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186`,
3,800,954bytes, [Apache2.0](https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_nanodet/LICENSE).
Name it **OpenCV Zoo NanoDet416 FP32**: upstream labels/metric tables are not
sufficient to bind an exact architecture/GFLOP claim to this binary. The actual
ORT graph has six outputs at strides8/16/32: class widths80 and regression32,
not four live scales. The independent adapter uses upstream RGB/centered black
letterbox/mean-std and distance-distribution decoding, then person-only scores
with the common0.1floor/0.5NMS and existing tracker thresholds. This intentionally
differs from upstream all-class/top1000/default0.35/0.6 postprocessing. NanoDet
unletterboxing clips to its source crop; YOLOX preserves its production
full-image clipping. Confidence calibration differs between models. These are
explicit experimental variants, not proof of network-only causal differences
or identical confidence semantics. Sources: [input mapping](https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_nanodet/demo.py),
[distance decoder](https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_nanodet/nanodet.py).

CoreML session availability/registration are checked and automatic runtime
fallback is disabled. This still does not identify the CPU/GPU partition or
prove every operator uses GPU. No candidate may be promoted automatically.
All counting comparisons are against a fresh CPU algorithmic reference;
matching it does not establish human-labeled accuracy.

### Full-source results from the new resource comparison

All six variants process900frames/1800detector calls from the same180s source.
The first five have identical experimental recipe hashes as well as identical
source/config/production-runtime/clock identities. After those processes end,
the runner is explicitly extended for upstream NanoDet policy and a processing
thread option; their later reports preserve their actual new recipe hashes.
Default4thread processing behavior is unchanged by that extension.

| Variant | Processing s | Launch-to-exit s | Worker CPU core-s | Average CPU % | Peak worker MiB | Matched / missing / extra |
|---|---:|---:|---:|---:|---:|---:|
| CPU baseline |367.904|370.710|1445.147|390.317|385.230|50 /0 /0|
| CoreML MLProgram |345.883|351.072|157.947|45.149|439.469|50 /0 /0|
| YOLOX Nano |47.295|50.407|209.950|420.126|293.246|14 /36 /13|
| YOLOX Tiny |97.357|100.618|406.964|406.249|321.859|20 /30 /17|
| NanoDet person-only0.1/0.5 |104.339|106.774|280.085|263.262|306.762|30 /20 /261|
| NanoDet upstream0.35/0.6 |67.884|71.244|242.337|342.036|305.887|2 /48 /5|

Matching uses0.4s tolerance, zone, lane and accepted/review status; the CoreML
result also matches all50events at tolerance0with zero timestamp difference.
CPU/CoreML both produce near14/far4/front18accepted/5review and side27accepted/
0review. These50events include both zones and review, not50unique people.
Nano's equal front total18does not establish compatibility: its lanes/status/
timestamps and side entries differ substantially. Extra/missing here mean
differences from the algorithmic reference, not human-labeled errors.

The observed CoreML processing reduction is5.99%; total launch reduction5.30%.
Measured worker CPU core-seconds fall89.07%, while peak RSS increases54.24MiB
(14.08%). System load varies substantially: the CPU baseline's1/5/15minute
load is8.01/10.92/11.96before and7.45/10.13/11.34after; CoreML's is8.62/9.88/
11.15before and9.94/16.31/14.98after. This supports an observed one-pass timing
comparison, not a stable6% speed advantage. It does show preservation of this
reference with much less measured worker CPU and somewhat more worker RAM.
External CoreML/GPU cost is unmeasured; do not call it the lowest-energy or
lightest-whole-computer method. The faster small models do not pass the chosen
reference-compatibility requirement, including NanoDet's upstream-policy
confirmation, so speed does not justify substituting them.

For NanoDet's upstream-policy confirmation, top1000perlevel and all-class
maxscore/NMS0.35/0.6 are applied in416-space, then personclass0 is selected.
There is no second NMS. Geometry stays float during unletterboxing rather than
the demo visualization's integer cast; this explicit variant is not claimed
bit-identical to the upstream visualization. Its actual graph and model hash
are unchanged. Both threshold policies remain experimental; no human quality
claim or model-family-wide verdict follows from this one overhead-camera clip.

`--threads` accepts1/2/4 and controls ORT intra-op and OpenCV processing in the
fresh experiment. Inter-op stays1; initial reference/ORB setup retains the
production4thread setting. This is not an OS-wide CPU cap or power change.
The supplemental1-versus4thread test uses only the same20s prefix and is
reported separately, never as a full180s/day quality result.

| Same20s prefix | Processing s | Worker CPU core-s | Average CPU % | Peak worker MiB | Exact reference matches |
|---|---:|---:|---:|---:|---:|
| CPU1thread |103.210|96.906|91.806|386.191|8 /8, zero missing/extra/time delta|
| CPU4threads |32.298|128.980|371.600|386.328|8 /8, zero missing/extra/time delta|

One-thread processing is3.20x slower on this matched prefix, with24.9% less
worker CPU core-seconds and almost identical peak RSS. It lowers CPU occupancy,
but does not support the requested faster daily turnaround. The20s screen
does not prove full-source compatibility or provide a whole-day estimate.

For the requested balance, CoreML is the preferred **experimental** choice
among these runs that preserve the full reference and reduce measured worker
CPU. It is not a stable overall speed/energy winner; the observed timing gain
is modest, RAM increases, and GPU/system-service cost is unmeasured. No
alternative is promoted to production. Processing the full180s source in346s
still does not meet the under10h/day target.

All benchmark processes ended. Production runtime and stopped64/503day17
ledger hashes are rechecked unchanged, and follow-up10 remains PAUSED. No new
camera/auth request, package or hardware; only one public3.8MBmodel was fetched.
PO final regression875tests/17.561s:861PASS/14optionalSKIP. Isolated benchmark
tests19PASS/0.332s cover all6numerical skips relevant to these tools; the other8
skips concern unchanged production sources with earlier pinned-runtime evidence.
Python3.9 parsing and diff checks pass. Independent read-only reviews covered
resource units/lifecycle/provenance, native decoder mathematics and the final
interpretation. Claude scoped task returned NOT_LOGGED_IN/childexit1/1.9s/no
retained lock; PO audited processes and took over. NOT_RUN_BY_DEVELOPER.
