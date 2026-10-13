# OD49 real-data counting validation

This is a supervised local pilot, not production/full-day acceptance.

| Evidence | Result |
| --- | --- |
| Real acquisition | Two new samples,38s and180s, native SD download over vendor recorded relay1 |
| Source selection | Exact reviewed noon window,5Fixed-bearing candidates; full180s clip covering noon |
| Lens | Stream0 visible Fixed Lens overlay, wide shop view; PT excluded |
| Held-out source SHA256 | `2fef18ff159658903c9d6b0fce96d9e62c873fb40107fb2ee8aebc5dc0785d6c` (Fixed-only MP4) |
| Configuration SHA256 | `468875e0091677b09f2db9d710e6931cd9a3a01f13c49a77e4f93ef9a007688c` |
| Whole clip | 180s /900sampled frames /35automatic passages,13forward/22backward |
| Manually evaluated interval | Relative0–50s; onePOreviewer,13passages |
| Direction-aware matches | TP12,FP1,FN1; precision/recall/F1=92.3% |
| Aggregate agreement | 13vs13,100% only in evaluatedwindow; not systemaccuracy |
| Seated negative | Front/back table occupants checked50s,zero falsepassages |
| Full-day / whole180s accuracy | NOT_VERIFIED |

Model/config were frozen before held-out inference. The38s sample was used for calibration, including replay of cached detections to tune sampled-frame tracking; its tuning results are not held-out accuracy. Manual labels were first made from2s source-frame sequences before inspecting predictions, then adjudicated against1s original-frame sequences: an additional passerby and two turn timestamps were corrected. This is single-reviewer evidence, not independent Owner groundtruth. Private labels retain the earlier version and adjudication record.

The one direction mismatch is around43s where two walkers cross. Direction-aware matching records oneFP and oneFN even though aggregate count is unchanged. No causal claim that counter geometry alone explains the tracker confusion. Events, tracks, images, video and rawpaths remain private outsidegit; shared evidence uses hashes/counts.

PO corrected draft defects: OpenCV NMS needed xywh, annotation fps needed sourcefps/stride, deadband crossings needed a retained stable-side anchor, NumPy coordinates needed conversion, privatefile/output/network/quotas needed enforcement. ONNXRuntimeCPU improves inference speed without new model weights. A cropped aisle and centeranchor reduce foot-occlusion errors. Relaxed tracking can swap IDs; no identity recognition was added. Do not sum overlapping clips or interpret temporaryIDs as unique visitors.

Code review: Claude draft timedout360.5s; broadadvisory timedout180.6s; focusedadvisory completedexit0/40.0s. PO checked full source, rejected two excerpt-only falsepositives with tests, retained the ID-continuity limitation and added hash-bound evaluation. Finaltests are PO-run; NOT_RUN_BY_DEVELOPER. Finalresults are recorded in STATUS after completion.

Runtime: hash-locked29packages; officialONNX35,858,002bytes, exactSHA256 enforced. Package versions checked againstOSV with no knownadvisories returned at that time. This is not a security guarantee. Actual inference and dependency-contract tests ran under deny-network sandbox; no modelcloud service. Private reviewvideo is H.264/1152x648/900frames/180s, with eventseek HTML and contextual caveats.
