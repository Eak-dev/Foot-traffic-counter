# Front-shop near and far lane counting

## Current geometry revision: OD-57

The Owner moved both gates to the red oblique alignment shown on a zoomed and cropped review frame. PO registered the unchanged pink rectangle against normalized source coordinates and intersected the alignment with each unchanged near/far polygon. The small gap at the shared polygon edge comes from the existing distinct boundaries. Both gates are now red; outlines/labels retain blue and green. No detector, tracker, crop, anchor, sample rate or counter rule was changed.

Old-preset replay reproduces every one of the36previous event records before the new gates yield17near and6far passages (front23). Pink remains27 with a byte-identical report. These totals describe different gates and must not be compared as accuracy scores. Source-frame spot checks at selected far-event times and the late table interval identify three near events needing review because temporary tracking associations change around the seated occupant. They have not been manually removed or presented as confirmed passages. Full new-geometry precision/recall remains NOT_EVALUATED.

Claude could not start because its local session was not logged in (child exit1,2.1s). PO completed the two-line gate-color maintenance and independent review; final changes are NOT_RUN_BY_DEVELOPER. PO full suite759tests/14.245s:757PASS/2optional-runtimeSKIP; actual private H.264900frames/1152x648/179.998667s whole decodePASS and red alignment visually checked. The existing trial revision may be copied to the Owner personal iCloud folder under OD-56/57; this does not authorize raw clips, sidecars, other dates or public sharing. No automatic iCloud deletion is configured.

## Previous OD-55 baseline

OD-55 addresses the Owner's report that right-to-left passages on the far side of the table were intermittently missed. The front-shop measurement now has two lane polygons, blue for the near corridor and green for the far corridor. Each has a finite gate placed across its own walking path before the worst table occlusion. Pink shop-side entry counting stays separate.

## Shared tracking and passage semantics

Both lanes replay one front-shop detector/tracker stream. A second front-lane inference or independent tracker is not created. The two main zones remain front-shop and shop-side; only front-shop gains lane subtotals. Front-shop total equals the accepted near and far event subtotals. It counts passages, not unique customers, and is never added to pink as a unique-person total.

`counter_mode: lanes` requires exactly two `lanes`, each containing `id`, `name`, `color`, `roi` and `line`. The existing zone `config` supplies the shared detector crop, anchor, confidence, sampling and boundary deadband. Lane vertices must fit that crop. Geometry validation uses polygon-edge intersections and interval midpoints to reject gates that leave a concave polygon, including thin notches. Config hashes bind the lane geometries and counter rules. Existing line and entry modes remain supported.

The counter requires one stable observation before crossing and two stable observations beyond the gate. This permits a short track first detected close to a gate to contribute, while a single contrary point does not create a passage. Points within the deadband preserve prior evidence. Confirmed evidence must intersect the finite gate and span at least 0.025 normalized distance. An adjacent jump over 0.12 within 0.4 seconds or a gap over two seconds resets motion evidence. A two-second cooldown for the same temporary track is shared across lanes and survives ROI exit; different IDs are not suppressed. Genuine later returns can count again. Evidence/time uses the confirming observation.

These rules reduce boundary duplication and abrupt tracking jumps. They do not establish identity: ID changes, partial detections, occlusion and initial detections already beyond a gate can still create missed or duplicate events. The output is not a unique-person count.

## Review and actual evidence

Claude delivered the initial pure counter before the scoped launcher timed out at 360.7 seconds; no tests/final developer result were returned. PO audited stopped task processes, released the empty cooperative lock and completed code review, synthetic tests, pipeline/schema/hash integration and presentation. NOT_RUN_BY_DEVELOPER applies to final changes.

PO found that requiring two pre-crossing points lost a short far-lane track that appeared close to the gate. The final three-point rule uses one pre-crossing point and two confirmed post-crossing points, plus movement, finite-gate and discontinuity checks. Displacement is measured to the confirming point, avoiding rejection of a slow passage whose first opposite point is too close. Exact gate validation replaced sampled containment. Regressions cover those cases, seated jitter, abrupt ID-like jumps, gaps, shared-boundary duplicate suppression, simultaneous different people, finite-gate bypass, concave notches, hash/report corruption and legacy compatibility.

On the existing 180-second Fixed source, baseline replay first reproduces the prior 25 event signatures at stored millisecond precision. Final shared-track replay produces 15 near and 21 far passages, front-shop total 36; pink remains 27 entries with byte-identical report/events. Detector, tracker, model, crop, confidence and anchor are unchanged. No new inference, camera call, credentials or dependencies were needed.

The first 60 seconds were used for calibration and source-frame checks. After freezing the rules/gates, PO inspected the separate 60–100-second interval using two-second source overviews and selected one-second adjudication, including finer frames for two closely passing people. Seven predicted far-lane passages have visual support, including four right-to-left passages. The two closely timed events belong to visibly different people; proximity is not grounds to delete one. This is one reviewer's source-frame validation, not continuous ground-truth coverage or full precision/recall. No full-clip accuracy percentage is claimed. The previously problematic late table-occlusion track contributes no event under the new gates, but all seated negatives have not been audited continuously.

PO final suite: 759 tests in 18.073 seconds, 757 PASS / 2 optional-runtime skips. New combined H.264 is 1152×648, 900 frames, 179.998667 seconds, whole-file decode PASS. Blue/green lane outlines and gates, lane subtotals, front total and pink count are shown together in Thai. The offline page has one video and lane-labelled event rows. Whole-day completeness, clip-boundary handling, overlap deduplication and whole-clip manual accuracy remain outstanding.

Private presets, track logs, labels, reports and media remain outside Git and sync, owner-only, within the existing 1 GiB staging and 10 GiB reserve limits. Retention stays explicit/on-next-invocation at 24 hours; there is no scheduler or guaranteed background deletion. No media was sent to Claude or GitHub.
