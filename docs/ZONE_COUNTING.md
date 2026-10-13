# Two-zone Fixed Lens counting

Owner OD-50 defines blue as **โซนหน้าร้าน** and pink as **โซนข้างน้ำ**. Blue counts line-crossing passages; pink counts stable entries from any edge, as explicitly confirmed by Owner. A person who passes both zones can contribute to both reports; these counts must not be added as unique visitors. Initial presence, sitting or remaining inside a region is not itself a passage.

The blue preset is preserved from OD-49. PO maps the pink rectangle from the Owner's screenshot and uses its boundary for entry counting. Pink has no counting line; blue keeps its original visible line. Private camera coordinates and source media are not stored in Git.

## Run locally

```sh
.venv/ft-counting/bin/python -m tools.ft_count_zones \
  --input <private-fixed.mp4> --model .venv/ft-models/yolox_s.onnx \
  --config <private-two-zone-config.json> --output <new-private-directory>
```

The config has exactly one top-level field, `zones`, containing exactly two objects. Each has a unique safe `id`, a Thai `name`, a distinct `#RRGGBB` `color`, optional `counter_mode` (`line` by default, or `entries`) and a `config` using the existing single-zone schema in COUNTING_GUIDE. Both zones share the same sampling rate. Every zone has its own crop, detection run, tracker and counter, so adding a region does not alter the original front-shop detector/tracker. This costs two sequential inference passes on the same local clip. Entry mode deterministically replays the persisted four-decimal normalized anchors after inference: three stable outside observations followed by three stable inside observations, boundary deadband and a two-second track-gap/cooldown limit. Initial occupancy and tracks first seen inside are not counted as entries; occlusion or track loss can therefore miss entries. Return visits can count again. The mode is bound into each configuration hash.

The parent process enforces macOS network denial before opening media or importing inference dependencies. Model hashes, private files, no-symlink paths, input limits and disk reserve remain enforced. No camera calls, credentials, new dependencies, face recognition, external inference or uploads are needed. Zones use bounded private outputs with reserved presentation space; quotas are checked cooperatively, not as filesystem partitions.

Each zone retains its own events/report/tracks. Entry mode discards the superseded line-count diagnostic video; the combined video is authoritative for presentation. The combined report is written only after both complete and the presentation succeeds. Merging rejects mismatched source/model/config hashes, frame clocks, event totals or directional totals. There is no combined people total. A failure leaves diagnostic partial files privately but does not publish a successful combined report.

`counted-zones.mp4` shows the original Fixed Lens view, blue/pink regions, the blue counting line, and two Thai count labels. Rendering uses the existing local ffmpeg, installed Pillow and a macOS Thai font. It does not change inference/counts. `review.html` is an offline Thai page with one video, separate zone cards and event seek buttons. No web server, CDN or scheduler is started.

## Validation limits

OD-49's manual accuracy result applies only to its original blue configuration and evaluated interval. It is not evidence of pink-zone accuracy. Report observed results and any occlusion/identity-switch limitations separately. Keep full-day completeness, cross-clip duplicate handling and unique-visitor claims unverified until specifically tested. See STATUS for the actual OD-50 run and test evidence.

Private inputs and outputs remain outside Git/sync with owner-only permissions, a 1 GiB aggregate staging allowance and 10 GiB free reserve. Review artifacts have a 24-hour explicit/on-next-invocation retention policy; this is not background deletion.

## Actual noon evidence

The180s pilot yields35blue line crossings and27pink entries. The blue event list is identical toOD49; pink has no complete manual accuracy measurement. Source/model/detection settings were reused; only pink counting semantics changed after Owner clarification. Combined900-frame H.264 decoded in full and Thai labels/regions/totals were visually verified. Full739-test suite:737PASS/2runtime skips, followed by57focused passes after mode-binding hardening. Data never leaves private local staging; no camera/network calls were added.
