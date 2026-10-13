# OD-52 Front-Shop ROI: Rectangle to Diagonal Polygon — Review

Scope: offline geometry review only; no media/code/tests run (NOT_RUN_BY_DEVELOPER).

## Checklist for PO before accepting
- [ ] Confirm target polygon's bounding box stays fully inside the existing
      detection crop; outside that crop there is no inference to count, not
      just a geometry change.
- [ ] Confirm anchor point (center, feet occluded) is same semantic point used
      for the old rectangle — do not re-derive from a single frame; one frame
      is not a calibration/homography.
- [ ] Verify old-rectangle replay reproduces the same 35 events with identical
      timestamps/directions before trusting any comparison baseline.
- [ ] Explicitly test seated/sitting persons in the green zone against the new
      gate: confirm they do not cross it in practice, not just that ROI shape
      alone implies exclusion — green zone still includes seated area.
- [ ] Check ROI-exit state reset: polygon edges near line ends must have
      enough track history before/after to avoid spurious resets or missed
      re-entries right at the corridor's narrow tips.
- [ ] State precision/rounding limits of polygon-edge clipping in normalized
      coordinates (0–1 float arithmetic), since the corridor is narrow and
      small rounding can flip a near-edge point's side.

## Count-difference interpretation
- 35 (old rectangle) vs 20 (proposed polygon) is NOT evidence of relative
  accuracy by itself — a narrower corridor can legitimately drop both true
  crossings (false negatives from geometry) and false positives (seated people
  previously miscounted). Do not report either number as "more correct"
  without the seated-person check above.

## No new inference required, if:
- Detector crop and anchors are unchanged, and
- Target polygon is fully within the existing detection crop.
If both hold, this is a pure counting-geometry change reusing existing
tracks; otherwise, a new inference run is unavoidable before any claim.

## Geometry-induced risks to evaluate before go-live
- Misses near corridor tips: the diagonal shape narrows faster than the old
  rectangle at the top/bottom; verify tracks that clip corners still get at
  least one inside-sample before/after crossing (deadband + sample rate).
- ROI-reset correctness: `CrossingCounterResetOnExit`-style logic must clear
  state exactly at polygon boundary, not the old rectangle's bounds — confirm
  this uses the new polygon, not a stale rectangle reference.
- Stable-side deadband near a finite line clipped to polygon edges: check the
  deadband band doesn't straddle both polygon edges in the narrowest part of
  the corridor, which would suppress legitimate crossings.

## Unknowns PO must resolve with real media
- Whether seated people near the gate ever enter the deadband/corridor.
- Whether corridor tips have sufficient track support (frames) given sample
  fps, or crossings there risk false negatives purely from geometry.
- Actual precision/rounding behavior at normalized-coordinate scale for this
  specific polygon, not a general claim.

## PO disposition / actual checks
- Proposed polygon is fully inside the unchanged detector crop. Model, crop, sampling, confidence and center anchors unchanged. Pink config/events unchanged.
- Original rectangle replay reproduces all35 track-ID/direction/timestamp signatures at the persisted millisecond precision. Anchors are rounded to4decimals; no stronger subpixel/time identity claim.
- New polygon with the old vertical gate clipped to its edges yields20 automatic crossings. This changes the measurement area; it is not evidence that15 original crossings were errors.
- Source-frame spot checks at0,5,10,15,20,30,40,49s and50–57s show seated foreground occupant not physically crossing the gate. The52.2s event with a reused temporary ID corresponds to a moving passerby; temporary IDs must not be interpreted as person identity. This is a spot check, not a full180s manual negative audit.
- Reviewed examples near21–22,32–35,42–43s; some crossings at the upper boundary now fall outside the polygon. Missed crossings near polygon tips/ROI resets remain possible; no full accuracy PASS is claimed. Existing CrossingCounter handles polygon state reset; no new class was introduced.
- Keep the requested diagonal shape rather than trim it further: an extra foreground trim would remove additional possible passages. Seated area overlaps the polygon; finite line-crossing semantics remain necessary.
- Claude advisory completed exit0/44.4s; NOT_RUN_BY_DEVELOPER. PO performs actual checks and acceptance.

## OD-53 wider corridor — PO follow-up

No new Claude review is claimed. The same crop/anchor/baseline prerequisites apply and were verified: all new corners fit the detector crop, old20event signatures reproduce at stored precision, and pink config/report/events are unchanged. The latest four-corner outline extends farther-aisle coverage; its foreground edge also follows the newly drawn boundary, so it is not a strict superset of the prior polygon. New automatic count34 is not an accuracy metric. PO source-frame spot checks cover the widened upper gate and seated foreground area, with full manual scoring still outstanding. Private media and exact camera coordinates are not included here.
