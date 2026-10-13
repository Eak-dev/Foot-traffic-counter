# Local Fixed Lens counting pilot

For Owner-defined blue/pink zones and separate totals, use [ZONE_COUNTING](ZONE_COUNTING.md). The single-zone CLI remains supported.

OD49 implements actual local inference on clips retrieved from shop SD through the vendor relay. Owner specifies the period in chat; PO operates the tools. No iPhone video forwarding, cloud inference, face recognition, database, server or scheduler.

## PO runbook

1. Read PROJECT_CONTROL and reuse the valid project Keychain session. Media retrieval remains a bounded PO invocation: `LIST_WINDOW='noon'` searches 11:55–12:05 Bangkok on the approved date; `CLIP_SELECTION='nearest_noon'` selects a source interval covering noon or the nearest available interval. It does not change source interval boundaries. First20 rows are not a full-day inventory. Set a new private outside-git ROOT and enable LIVE_TRIAL_ENABLED for the reviewed process only. Limits: 3 clips/iteration, 180s/100MiB/300s each. No camera setters.
2. Verify decode, duration and visible Fixed Lens overlay. Both real pilot samples have Fixed at stream index0 and PT at index2; this is not a universal mapping for other cameras. Extract only Fixed with ffmpeg streamcopy/no audio. Input must be owner-only, outside git/sync. `fixed_lens_verified:true` records PO visual attestation, not automated lens recognition.
3. Run the installed isolated runtime:

```sh
.venv/ft-counting/bin/python -m tools.ft_count \
  --input <private-fixed.mp4> --model .venv/ft-models/yolox_s.onnx \
  --config <private-count-config.json> --output <new-private-output-directory>
```

The CLI re-execs under macOS `sandbox-exec` with `deny network*`. Before importing inference libraries or reading media, the child verifies socket operations are denied. Unsupported environments fail closed. Do not invoke the private sandbox flag manually.

4. Outputs: `report.json` with events/counts/hashes, `tracks.jsonl` with temporary tracks and detections for review, `annotated.mp4`, and an offline review page. No server/CDN/external requests. Annotation uses mp4v; PO can make an H.264 review copy with the existing ffmpeg without changing counts.
5. Manually label a separate evaluation window. `ft_count_evaluate.evaluate_report(report, labels)` rejects mismatching input/config SHA256 values. Labels contain `window_seconds`, `events` with relative `time_seconds` and `direction`, and optional `tolerance_seconds`. Matching is one-to-one, direction-aware. Aggregate count agreement does not imply every event/direction is correct.

## Counting definition and configuration

Counts directional crossings of a finite line inside a polygon. A return crossing is another passage; first sightings are not counted. This is not unique visitors, purchase conversion or identity recognition. Configured `center` anchor helps where feet are hidden by counters/signage. Temporary tracker IDs can swap during occlusion.

Config: `fixed_lens_verified:true`, normalized `line:[[x,y],[x,y]]`, `roi` polygon, `sample_fps` (0–15), `confidence` (0–1), `deadband` (0–0.2), normalized `crop:[left,top,right,bottom]`, and `anchor` (`center` or `bottom_center`). Unknown fields, bool coordinates, NaN, zero-length lines and self-intersecting polygons are rejected. Deadband is perpendicular normalized distance. Track gap2s/cooldown1s.

Generic example, **not the shop preset**:

```json
{"fixed_lens_verified":true,"line":[[0.5,0.2],[0.5,0.8]],"roi":[[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.9]],"sample_fps":5,"confidence":0.25,"deadband":0.012,"crop":[0,0,1,1],"anchor":"center"}
```

Pilot uses a cropped right aisle, vertical gate, center anchor,5fps/confidence0.05, ByteTrack matching0.99/lost buffer90. Relaxed matching accommodates sampled frames but increases ID-swap risk. The real camera preset stays private. PO chose this passage line for the pilot; Owner has not yet confirmed it covers every business-relevant route. Do not extrapolate its accuracy to other views.

## Installation and data safety

Python3.13 isolated environment; exact versions and distribution hashes in `requirements-counting.lock`. Existing uv/Python/ffmpeg remain in ignored runtime. Reproduce with `uv pip sync --require-hashes --only-binary :all: --python <isolated-python> requirements-counting.lock`. ONNX weights come from pinned OpenCV Zoo,35,858,002bytes; SHA256 is checked before every load. No automatic downloads or pickle checkpoints. ORT CPU/OpenCV/supervision ByteTrack; no appearance or face model. See THIRD_PARTY_NOTICES. OSV check of29 installed versions found no known advisory on the check date, not a security guarantee.

Private artifacts: new directory0700/files0600, outside git/sync. Input100MiB/182s including tolerance; output512MiB/job, disk reserve10GiB, cooperative processing deadline1200s. PO monitors aggregate1GiB staging. Retention24h with explicit/on-next-invocation cleanup; **no background deletion guarantee**. No passwords/OTP are stored by counting tools.

## Before daily totals

Still required: full-day pagination/completeness ledger, overlap deduplication and clip-boundary counting checks. Never sum overlapping clips blindly. Owner confirmed event-only recordings can represent a day when acquisition is complete and counting validated. This noon pilot proves neither full-day condition and starts no automatic worker.
