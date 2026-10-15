# Exact clip checkpoints and the finite daily job (OD-61)

The daily job now resumes at the next uncommitted source, including the middle of a long continuous recording group. It no longer replays a whole9hour group after a36hour invocation limit. Gates, model,640pixel inference,5fps sampling, lane/pink definitions and bbox review policy remain unchanged. This fixes completion/recovery; it does not make the older Mac realtime or establish counting accuracy.

## Transaction and compatibility

The deny-network worker exports only an explicit value schema: ByteTrack active/lost/removed objects and shared aliases, float32/float64 Kalman state and covariance, ID counters, counter pending sides/cooldowns/totals, ordered bounded box histories and frame ownership clock. Freshly created tracks may still have float32 means; later means are float64. Both retain their exact dtype/bytes. Infinity is allowed only as an explicitly tagged negative sentinel; arbitrary objects, pickle, eval and imports selected by input are absent.

1. A new immutable snapshot is written outside Git with0600permissions in a0700folder. It binds source/input/reference hashes, config/lens policy and runtime/source fingerprints.
2. Atomic ledger replacement commits the new snapshot pointer, processing cursor and that clip's events together. A report-write failure cannot roll back a committed clip.
3. Report files are derived from the committed ledger. Only then are obsolete snapshot files removed. A crash before commit leaves the previous pointer authoritative; an orphan new snapshot is discarded and at most the unfinished clip is replayed.
4. Resume validates the processing prefix, stable inventory, source/config/reference hashes and snapshot checksum. The worker validates exact field/shape/dtype/container schemas and its pinned runtime before any next media download. Missing/corrupt/incompatible state blocks; it is not silently ignored.

JSON has bounded bytes/nodes/depth/array dimensions and numeric parsing. Snapshot bodies cap at32MiB. Internal temporary IDs and boxes remain private, never in Git or the delivered numeric report. Known temp/orphan files are cleaned only under the exclusive job lock; unknown files are not deleted. Active reference/state/ledger must survive this explicit multiday job; raw/Fixed clip staging is removed after each clip. Post-job cleanup remains explicit/on-invocation, with no background deletion guarantee.

## Finite execution and delivery

PO invokes the job. Owner does not need Terminal. The intended command uses one completed Bangkok date, the private preset/reference and the approved numeric report folder:

```text
python3 -m tools.ft_day_job --run --date YYYYMMDD
  --root <PRIVATE_JOB> --config <PRIVATE_PRESET> --reference <PRIVATE_REFERENCE>
  --keep-awake
  --delivery-dir <APPROVED_NUMERIC_FOLDER>
```

This is one explicit foreground batch job, not a scheduler or startup service. A finite supervisor permits at most two driver cycles/72hours and1000new media windows across both cycles. Each driver retains64auth batches and its48hour cooperative cap; an individual callback retains its36hour cap. The supervisor requests a graceful checkpoint stop at36hours per cycle. It resumes only after a verified budget exit or its own clean checkpoint interruption, checks the child PID and status, and refuses cursor rollback, unknown shutdown, auth/source/integrity errors. A forced kill cannot trigger an automatic retry. Each batch reuses the cached Keychain session, verifies the selected target and repeats bounded stable SD inventory. Confirmed401may use the existing single refresh/inventory retry; no repeated native login or OTP prompts. It stops on an auth/source/integrity error, rather than retrying it indefinitely.

Daytime groups are processed whole, longest first, then other groups including night. This changes when partial results arrive, not which sources are counted. Tracking resets between independent groups even if processing moves backwards in day time; overlapping/adjacent sources within each group keep the same state. Report ownership and filters sort by actual timestamps.

A temporary caffeinate idle-sleep assertion is tied to this job PID and timeout. It does not modify permanent power/account/network settings. It ends with the process. SIGTERM/interrupt closes the worker and retains committed state. job-status.json is private and records PID/status; a stale running flag alone is not evidence that a process still exists.

At each batch boundary and on normal completion, only standalone numeric HTML/CSV are copied into the approved personal folder, labelled PARTIAL or COMPLETE. Raw media, snapshot, ledger, config and detector logs are excluded. COMPLETE means all inventoried recordings processed, not unique people or verified accuracy. The report still separates accepted/review and front/pink zones. Browser/iPhone interactive rendering and completed cloud sync are not attested; static tables and CSV remain available.

## Real SD marker-only tail correction

The second live adjacent180s source exposed a real media boundary issue after the first source checkpoint restored successfully. Its MP4 advertised2700frames but decoded2699images: the final38byte packet was only H.264 type6 SEI containing the vendor marker, not a picture. OpenCV correctly refused that phantom last frame. Authentication and SD download had succeeded; the strict decode failure was retained, not suppressed.

Fixed-only remux now uses codec-copy plus `filter_units=remove_types=6`, guarded by an explicit H.264 stream0 check. Never apply H.264 type numbers to HEVC (type6 is picture data there); unsupported codec/lens metadata stops. This removes side metadata without re-encoding. The failing sample decodes2699images before and after, with identical per-frame size/MD5 for all2699images and no normalized decode errors. Its final declared frame now reads successfully. Container average-rate rounding changes sampled clocks by at most25microseconds before millisecond rounding; Replaying900actual sampled frames through the normalized clip preserves11accepted front passages,1review and6pink entries; event classifications/order match and timestamp differences are at most1ms. The resulting exact state also reloads in a new Python process. This reuses actual inference outputs after full image parity, not new model inference or a production state migration.

The preprocessing policy is bound into day_stream_v4/config/runtime hashes. Start a fresh ledger; do not reinterpret the prior v3 prefix or automatically migrate its state. The active v4 checkpoint and completion evidence supersede the failed diagnostic run. Existing source-duration, static-lens, complete-decode and overlap guards remain. See the primary [FFmpeg filter_units documentation](https://ffmpeg.org/ffmpeg-bitstream-filters.html#filter_005funits) for SEI filtering semantics. No new media package is installed.

## Evidence and rejected shortcuts

- Fresh CPU inference on the original180s clip:900sampledframes/454.595s; detector calls436.115s. It still produces18accepted front,5review and27pink. This is a new timing observation, not proof of a code speedup or all-day throughput. A second real180s source took542.354s before its SEI-tail decode rejection; timing varies with load. Roughly2–3days for this recorded day is an extrapolation, not a measured completion time.
- Using those actual detections, interrupted runs at30/60/90/120/150seconds reproduce every event/ref/reason and the final state exactly. A new Python process at90seconds also matches. This checks exact resume without repeatedly running neural inference.
- Synthetic runtime regressions include pending line/entry transitions, occlusion/reassociation/removal, new-track float32 means, ID counters, ordered evidence, overlap with no new frames, corruption/runtime mismatch and safe codec failure.
- Parent tests inject crashes before ledger commit and after commit/report failure, plus missing snapshot, orphan cleanup, exclusive job status, daytime-first order and bounded auth batches. Completed clips are not duplicated.
- CPU thread profiles1/2/4, two parallel2thread sessions, no-spinning options, denormal options and OpenCV DNN were measured with existing packages. None provided a worthwhile confirmed improvement over the chosen CPU backend; parallel speedup was only1.025x. No candidate was deployed.
- Reducing cached analysis to2.5fps loses accepted front passages18to12 and pink entries27to11 on the same sample;1.67fps loses more. Rejected. Existing CoreML output also changed counts and remains rejected.
- ONNX Runtime documents [thread controls](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) and warns of accuracy risks for [denormal handling](https://github.com/microsoft/onnxruntime/blob/main/include/onnxruntime/core/session/onnxruntime_session_options_config_keys.h). Measurements and output checks, rather than a presumed speedup, determined rejection.

Full regression:839tests/30.551s,831PASS/8optional-runtimeSKIP. The isolated runtime suite passes11tests/5.503s and covers those8skips. The final real-detection cross-process resume check passes in36.939s. The first live source committed successfully and the adjacent source restored; its strict terminal-frame failure led to the verified SEI correction above. A fresh v4 full-day job is now actually running; there is no full-day total yet. Full coverage and accuracy remain separate, unverified outcomes.

Claude scoped launch failed NOT_LOGGED_IN,exit1/2.2s, no changes/no retained lock. PO implemented, reviewed and tested; final NOT_RUN_BY_DEVELOPER. Existing checkout/branch, no new packages/weights, setters, external inference, face recognition, database/server/Docker, main push or merge.
