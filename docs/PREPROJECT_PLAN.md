# แผนก่อนโครงการ FT-D0: เตรียมดึงข้อมูลคลิปจากกล้องก่อนนับคน

OD-65 completed /2026-10-18 Bangkok: vendor-managed schema3 is implemented; new bootstrap has no local48h/7day/30day ceiling, and retain-7/retain-30 are rejected before Keychain/network access. Valid existing schema1/2 records migrate locally even past former caps, preserving original authentication time and credentials; missing/deleted tokens are not restored. Same explicit401-only one-refresh/one-target-replay budget and Keychain/host/target/revision/clock checks remain. Redacted success/error observations preserve session age, observation start, observed refresh count, last refresh and actual vendor verification; local status does not claim remote acceptance. Auth causes distinguish refresh rejection, post-refresh access rejection and missing refresh; transient failures retain credentials. Synthetic reuse/rotation beyond2/7/30/61days and migration past each former cap PASS; actual vendor lifetime UNKNOWN. PO50session tests PASS/0.117s; full848tests/14.822s:840PASS/8optional-runtimeSKIP (unchanged counting-runtime skips). Claude scoped launch NOT_LOGGED_IN,exit1/4.3s,no retained lock/no source changes; PO takeover/review, final NOT_RUN_BY_DEVELOPER. Actual project helper status after code change is BLOCKED/REAUTH_REQUIRED, confirming prior deletion by old48h handling; no real login/refresh/camera call in this change. Date17 remains prepared waiting for private bootstrap readiness. No active day job or new scheduler; Publication state is in the ignored delivery record.

OD-64 readiness /2026-10-18 Bangkok: Owner-selected20261017 trial prepared in a fresh private root, same unchanged reviewed v4 runtime/config/reference and job budgets. No day processes remain; reference hash, zone validation and storage preflight PASS. Actual session status through the established helper is BLOCKED/EXPIRED (the sandbox-only STORE_ERROR was not treated as an auth result). Waiting for Owner readiness to enter email/password/OTP in the existing private native dialog; no dialog, camera request, inventory or counting has started. Previous date15 result remains190/379 partial and automation10 PAUSED. Inventory coverage and counts for date17 UNKNOWN. No new packages, source edits, retention changes or credentials in chat. Tests NOT_RUN for documentation/local-readiness checks; LOCAL_ONLY pending checkpoint.

OD-61: exact per-clip JSON checkpoints and atomic ledger commits are implemented, with finite cached-auth execution and whole-group daytime priority. Final regression839tests/30.551s:831PASS/8SKIP;11isolated runtime tests/5.503s cover all8skips. Real-detection replay at5boundaries and a new process preserves every event/state (18accepted/5review/27pink).

The live second adjacent source exposed a vendor SEI-only phantom last frame, not an authentication or resume failure. H.264-only codec-copy SEI filtering preserves all2699decoded images by per-frame size/MD5 and passes strict end decode; replaying900actual sampled frames retains11accepted front/1review/6pink, and its exported state reloads exactly in a new process. These are partial-source checks, not a day total or manual accuracy score. Model/gates/5fps remain unchanged. A fresh day_stream_v4 whole-day job for20261014 is now actually running on the Mac (510intervals, CPU worker and PID-bound caffeinate observed); it does not mix v3 state. Snapshot/runtime sources remain frozen during this job. The finite supervisor permits at most2driver cycles/72h/1000new windows and stops on auth/source/integrity errors. Numeric reports copy at each batch boundary. Full-day completion and sustained daily throughput remain UNVERIFIED. Optional7/30day retention code is tested; the active lease remains48h until Owner answers the pending preference, so a later auth stop remains possible. See [EXACT_RESUME.md](EXACT_RESUME.md). Claude NOT_LOGGED_IN/2.2s/no changes; final PO work NOT_RUN_BY_DEVELOPER. Publication state is recorded in the ignored delivery record.

OD-60 final trial: actual86s Fixed night worker430sampled frames/238.531s/0automated events; processing PASS, manual counting accuracy NOT_VERIFIED. Together with the real3s/15frame trial, a new day_stream_v2 private ledger contains2of510processed sources and2completed short groups, statusPARTIAL_PROCESSING; no day total. Original diagnostic raw/Fixed and trial worker copies removed after validation; ceiling-only evidence remains private. No worker remains active. The current blocker is throughput/exact clip-boundary resume, not authentication.

OD-60 live result /2026-10-15: Owner private bootstrap SUCCESS; token/refresh cached in Keychain,48h local deadline unchanged. Session reused across daily inventory and bounded native downloads without further input. Two terminated sweeps for20261014 agree:510Fixed intervals,66370recorded seconds,179continuous groups; longest group32720s/207clips. Initial full-day run stopped safely on the first night clip because noon-only ORB ceiling matching rejected changed illumination, not auth or a failed media download. Fixed OSD and unchanged ceiling geometry independently checked from the private ceiling-only image. Static-gradient fallback passes6night times plus daylight and rejects actual PTday/PTnight, shifted/zoomed/mirrored/blank images (13/13). New policy binds day_stream_v2 hash; old checkpoints cannot mix.

Native3s recording download verified under an explicit short-recording flag. Actual file includes0.667s final-GOP overrun; short-source tolerance permits at most1s extra and0.15s missing, with frame/event ownership clipped to the original SD interval. Actual worker15sampled frames/0events, lens+SD-duration mapping PASS; no whole-day zero claim. Legacy playback/default5s minimum unchanged. Detailed worker enums distinguish lens/clock/count failures without exposing runtime text. Full regression809tests/36.880s:807PASS/2optional-runtimeSKIP; PO final NOT_RUN_BY_DEVELOPER. Long86s night trial result follows; no complete-day totals.

Full-day capacity BLOCKER:18.44hours recorded versus the prior4.58x realtime CPU benchmark projects roughly84hours compute (extrapolation, not full-day timing). Longest group alone projects41.6h, exceeding36h invocation cap; old resume restarts an incomplete group. Do not launch a known-to-exceed full-day job or request credentials repeatedly. Next PO engineering: validated exact tracker/counter checkpoints at clip boundaries and measured throughput optimization, preserving counts/review. No background daily scheduler/full-day worker. No new packages/setters/account/network changes. Claude unavailable as previously checked; writerPO. LOCAL_ONLY pending checkpoint.

OD-59 current: daily acquisition/continuous counting and offline hourly/period/custom-filter report implemented. Real whole-day run is blocked before camera calls by REAUTH_REQUIRED; no complete-day figures. CPU180s replay preserves18accepted/5review/27pink and duplicate overlap produces0new events. CoreML changed counts and was rejected; CPU remains default. See [DAY_COUNTING.md](DAY_COUNTING.md) for bounds, midnight/resume semantics and remaining capacity/accuracy limits. Claude NOT_LOGGED_IN/no changes; PO owns final code/tests, NOT_RUN_BY_DEVELOPER. Numeric partial pilot only may be delivered to personal iCloud.

OD-58 current: bbox-continuity quality mode separates unreliable ID/box changes from automatic counts without altering red gates, tracker or candidate generation. Same23candidate records conserved by digest: auto18(near14/far4), review5, pink27 byte-identical. All3known late ambiguities are in review; the other2 remain inspectable rather than silently lost. Strict ByteTrack variants were rejected for genuine-passage loss. PO770tests/15.493s:768PASS/2optional-runtimeSKIP;900-frame H.264 whole decode/Thai totals/orange review markers PASS. Claude unavailable NOT_LOGGED_IN(exit1,1.8s), final NOT_RUN_BY_DEVELOPER. Private preset active; same annotated trial revision copied/hash-verified in personal iCloud, cloud completion/iPhone playback unverified. No camera/inference/new packages. Full accuracy remains unverified; see TRACK_CONTINUITY. Publication state is in ignored delivery record.

OD-57 current result: both front-lane gates now follow the Owner red oblique alignment, individually clipped inside unchanged blue-near/green-far polygons. Screenshot zoom/crop registered against unchanged pink rectangle. Baseline replay reproduces all36old events exactly; new automatic counts near17/far6/front23, pink27 with byte-identical side report. Only gates changed; detector/crop/anchor/motion rules unchanged. Red gate display,900-frame H.264/1152x648/179.998667s complete decode and visual alignment PASS. PO759tests/14.245s:757PASS/2optional-runtimeSKIP. Claude launcher failed NOT_LOGGED_IN(exit1,2.1s), no changes; final presentation maintenance/replay by PO, NOT_RUN_BY_DEVELOPER. Source-frame checks flag three near events in the late table-occlusion interval as ambiguous temporary-track associations; these are not verified walking passages. Changed measurement geometry is delivered, not an accuracy improvement or full-day PASS. Same-source annotated trial revision copied to the Owner personal iCloud folder with SHA-256 equality; completed cloud upload/iPhone playback remain unverified. No raw media/sidecars/public link. No camera/inference/dependency changes; writer PO/no worker. LOCAL_ONLY pending checkpoint.

OD-55 current result: front-shop now has blue near and green far corridors, each with its own finite gate before table occlusion, sharing one detector/tracker. Lane-aware stable-motion replay produces near15/far21/front36 on the same180s source; pink remains27entries with identical report/events. Baseline25 event signatures verified. PO froze rules after first60s calibration, then source-frame checks in60–100s support all7predicted far passages, including4right-to-left passages; this is not complete manual ground truth or whole-clip accuracy. Shared same-track2s cooldown reduces lane-boundary duplicates; ID-switch limits remain. Exact concave-gate containment, crop bounds and mode/rule hashes checked. See FRONT_LANES.

Claude partial counter delivery timed out360.7s without tests/final report. PO audited task shutdown, released empty lock and completed counter corrections/integration/tests/media verification. Final759tests/18.073s:757PASS/2optional-runtimeSKIP. New900-frame H.264 whole-file decodePASS, Thai blue/green subtotals/front total/pink visually checked. Private preset active. No new inference/camera calls, secrets, packages or uploads. NOT_RUN_BY_DEVELOPER; writerPO/no worker/pending Owner input. LOCAL_ONLY until checkpoint push/read-back.

OD-54 current result: front-shop cyan ROI follows the latest eight-corner concave outline; its finite gate is now oblique as marked, replacing the vertical line. Gate interior and polygon/crop containment verified. Cached replay reproduces all 34 OD-53 event signatures before the new geometry yields 25 automatic crossings (8 forward / 17 backward). Pink shop-side remains 27 entries with byte-identical report and unchanged config. Model, crop, anchor, tracker and code unchanged. Private preset activated; no new camera or inference calls.

PO source-frame checks show moving people replacing temporary track IDs near the seated occupant. In a later table-occlusion interval, a stationary/sitting pair is associated with extra crossing transitions: an observed tracking limitation, not evidence of actual walking passages. Parallel gate offsets were evaluated diagnostically; count variation alone cannot establish a better line, so the Owner-marked gate is retained rather than optimizing the count. The 25 total is AUTOMATED / NOT_FULLY_MANUALLY_VERIFIED and may include duplicate/false events. Geometry delivery is complete; accuracy validation/tracker correction remains pending. Historical 34/20/35 front totals refer to different gates/regions and are not direct accuracy comparisons.

OD-53 wider-corridor result: the front-shop cyan polygon follows the latest Owner outline and includes the farther aisle. The existing vertical gate is extended to the new polygon boundaries. Same900-frame private track replay reproduces OD-52's20event signatures at millisecond precision before counting34front crossings (13forward/21backward); pink remains27entries with a byte-identical report. Model/crop/anchor/sampling/code unchanged; the polygon is fully inside the existing detector crop. Four closed corners exclude a stray stroke beyond the lower corner; screen player chrome is excluded when mapping coordinates. PO spot-checked source frames near21–22,32–35,42–43s and60,70,90,110,130,150,159.6,170s, including seated foreground occupant. These checks verify coverage/presentation only, not full accuracy. New geometry accuracy remains NOT_EVALUATED. No new Claude run; OD-52 advisory prerequisites reused and checked by PO.

OD-52 geometry result: front-shop cyan polygon now follows the Owner-marked diagonal corridor; the original vertical counting line is clipped to the polygon. Replaying900 existing sampled frames produces20front crossings; pink shop-side remains27entries with identical events. Old rectangle replay reproduces35event signatures at millisecond precision, establishing the comparison baseline. No model/crop/anchor/code changes. Counts measure the new region, not an accuracy improvement. Source-frame spot checks reviewed seated foreground occupant and edge cases; complete new-geometry manual accuracy remains NOT_EVALUATED. Claude advisory exit0/44.4s; writer PO/no worker. See ZONE_GEOMETRY_REVIEW.

OD-52: Owner requests front-shop ROI shaped as the screenshot's narrow diagonal green corridor, replacing the wide blue rectangle, and authorizes PO geometry recommendations. Preserve blue display identity and line-crossing semantics, pink shop-side entry geometry/mode/count. Reuse existing private source/tracks; no new camera calls, inference, dependencies or credentials. PO maps screenshot video bounds, compares old and new geometry on identical persisted anchors, checks seated-person negatives and visually verifies presentation. Lower counts alone are not accuracy evidence; prior manual metrics do not transfer to changed geometry. Private preset/media stay outside Git. Baseline3a724d7f80d4d052c8c3a01d78cc0039e5bdcc3c; same branch, writer PO.


OD-50 Owner clarified: pink โซนข้างร้าน counts stable entries from any edge; blue โซนหน้าร้าน retains line crossings. Initial occupancy is not an entry. PO implements entry counting from the same persisted detection/tracker anchors with boundary hysteresis; no new inference/model/network is required for this semantic change. Separate canonical hashes bind the counting mode. Pink line-counter experiment is superseded, not an accepted result.


**OD-50 / 2026-10-13 — TWO INDEPENDENT COUNTING ZONES:** Owner requests existing blue region named โซนหน้าร้าน and new pink rectangle named โซนข้างร้าน from supplied screenshot. Implement separate passage counters/reports/colored overlays on the same Fixed clip. Preserve front-shop config and independent tracking; pink region normalized from screenshot approximately x0.292–0.852/y0.381–0.611, with PO-selected vertical crossing line x0.58 inside it. This is line-passage counting, not occupancy or unique people. One person may count in both zones; never sum as unique visitors. New zone accuracy must be measured separately; OD49 metrics do not transfer. Reuse local source/runtime, no new camera/network/credentials/packages required. Private artifacts outsidegit, 1GiB total staging/10GiB reserve, same retention/privacy. One writer Claude during scoped launcher, then PO independent review and real-media test. Baseline17f87d41205e199c3740bc41b0bd132889a61919, existing branch.


**OD-49 /2026-10-13 — LOCAL_NOON_COUNTING_PILOT_WORKING:** Home Mac retrieved two additional SD samples through the established native-download/relay1 path using the cached48h session, no iPhone video forwarding or credentials. Exact11:55–12:05Bangkok search returned5Fixed candidates; selected38s calibration and180s interval covering noon. Private Fixed index0 visually confirmed;180s whole-file decodePASS. No setters or account/router changes.

Local pipeline uses pinned YOLOX_s ONNX/OpenCV/ONNXRuntimeCPU/supervisionByteTrack, isolatedPython3.13, verified model hash and macOS process-level network denial before inference. Whole held-out180s:900sampled frames,35passages (forward13/backward22); this full-clip count is AUTOMATED/NOT_FULLY_MANUALLY_VERIFIED. PO chose a right-aisle vertical line/center anchor; geometry is provisional for business coverage, not an Owner-confirmed definition of every route.

Independent-window evaluation: frozen model/config before held-out processing, first0–50s labelled from source images by onePO reviewer (2s overview then1s adjudication). Manual13/system13; strictdirection-awareTP12 FP1 FN1,precision/recall/F1=92.3%; aggregate count agreement100% only for this window, NOT100% systemaccuracy. One crossing pair causes a direction error; no seated-person false passage in the50s checked. Labels bind input/config SHA256. Existing80%aggregatebaseline passed in this small pilot window only; full-day acquisition/overlap dedup/clip-boundary counting/whole-clip accuracy remain unverified.

Claude supplied initialcode before360.5stimeout, first broadadvisory timedout180.6s; focusedcode/evaluation advisory completedexit0/40.0s. PO independently corrected/reviewed source and provided all finaltests and actual-media evidence; NOT_RUN_BY_DEVELOPER. See COUNTING_CODE_REVIEW for dispositions of excerpt-only findings. Owner has no pending credential or technical setup action for this pilot. WriterPO, no activeClaude/camera worker; no scheduler. LOCAL_ONLY until checkpoint push/read-back.

Data: media/private reports stay outsidegit/sync with0700/0600, cumulative1GiBbudget and10GiBreserve. Superseded trial annotation videos removed; artifacts expire24h with explicit/on-next-invocation cleanup, not guaranteedbackgrounddeletion. No externalAIvideo upload, face/appearance identity model or hardware purchase. Reproducible hash-locked29package runtime, OSVfoundnoknownadvisories atchecktime. See COUNTING_GUIDE and COUNTING_VALIDATION.

**OD-49 /2026-10-13 — NOON COUNTING IMPLEMENTATION AUTHORIZED:** Owner requests actual Fixed Lens clips around noon (any day), working offline people counting using libraries, data safety and code review, continuing autonomously until usable or an actual Owner dependency. This supersedes historical D0-only/no-counting-install restrictions for this scope. PO selects the already verified date20261012, bounded11:55–12:05 local(+07:00) SD search, up to20rows, native download/recorded relay1, at most3 distinct clips per iteration and100MiB/300s per clip. PO may extend the observation window around noon with an explicit recorded reason. Private outside-git staging total1GiB including raw/Fixed/annotated output; keep10GiB disk reserve, owner-only permissions. No uploads, face recognition, camera setters, new hardware, paid services, global settings, DB/server/Docker or automatic scheduler. Reuse valid48h Keychain session. Private review artifacts expire24h with explicit/on-invocation cleanup; no claimed background deletion.

PO may install pinned free inference/tracking dependencies and vetted ONNX weights into an isolated ignored runtime, verify source/licenses/hashes, and process video locally with network denied. Initial choice OpenCV DNN/YOLOX (Apache2.0) and a packaged ByteTrack implementation subject to audit, avoiding model pickle execution and cloud inference. Actual camera image stays outside Claude/GitHub; Claude receives synthetic inputs, public source contracts and redacted evidence only. Same checkout/branch, one writer; PO acquisition/control/runtime, Claude scoped implementation/review, PO independent tests and real-media evaluation. Count directional passage events across a documented shop-front line/ROI, not unique people or event-file count. Existing80% aggregate baseline plus held-out event FP/FN and seated-negative checks still required; a small noon pilot does not prove full-day completeness/accuracy. No live or counting PASS until measured. Writer PO, LOCAL_ONLY; baseline5829c0cd0481ae317965bf3a397eaae177a04e65.

OD-48 latest gate: ONE_FIXED_CLIP_VISUALLY_VERIFIED. Actual native SD download through recorded relay1 succeeded; PO extracted/decoded/visually checked one Fixed-only MP4. Local private evidence only. Next phase remains bounded batch design, dedup/completeness and counting validation; none of those pass from one clip. No iPhone video forwarding or new hardware. See STATUS for633test and real-media evidence.

OD-47 latest gate: cached-session UTC lens-selected16s playback was accepted (error_code0) but ended with stream_status finished and0video. Media acquisition remains BLOCKED/UNVERIFIED, no file retained. Control/list/lens metadata are verified independently; no conclusion of permanent hardware impossibility. Default media-check stays HOLD; no repeated live calls without a concrete protocol correction. See STATUS/SD_MEDIA_REVIEW for exact evidence and626test validation.

**OD-46 readonly follow-up /2026-10-13 — LENS_METADATA_VERIFIED / MEDIA_STILL_BLOCKED:** Added fixed-check with the source-backed searchVideoWithUTC getter, exact same day and indices0..19, session guard and three readonly device requests. Actual cached-session trial succeeded:20rows, no missing lens metadata,19bounded lens1 candidates, shortest16seconds. Lens1 is Fixed according to the model-specific public source; visual media mapping remains UNVERIFIED. No relay/media trial was repeated after this result; media-check stays HOLD before Keychain/network. Six earlier media experiments yielded no usable file; final native-download negotiation failed400 before any frame was sent. Next work is reviewed structured terminal-notification diagnostics and a lens-metadata-selected playback interval; do not claim acquisition/Fixed visuals/full-day counting PASS. Owner has no new credential/router action pending.

**OD-46 /2026-10-13 — ONE_CLIP_ATTEMPT_BLOCKED / NO_MEDIA_RETAINED:** Owner instructed the next one-clip step. Claude delivered offline protocol/tests (exit0,191.5s, reports592tests); PO independently corrected validation/query handling, built bounded relay/media/staging/session integration, and tested before live. Six finite live experiments: playback initially timed out; diagnostics proved HTTP200/ACK with0video; longer first-media wait, source-aligned returned relay IP, fresh playback UID and source track ID did not produce video. Structured stream_status finished without media now fails INCOMPLETE immediately. Native download candidate (negotiation streamType3) failed HTTP400 at RELAY before the download frame was sent. This isolates that rejection to negotiation, not to the untransmitted frame. No retained media, Fixed mapping/counting/full-day completeness remain UNVERIFIED. Claude independent advisory completed exit0/123.4s; PO corrected overclaims in SD_MEDIA_REVIEW. Stop live retries/parameter enumeration. media-check is now HOLD/MEDIA_PROTOCOL_UNVERIFIED before Keychain/network; session use/status/sd-check remain available. Next evidence: establish a Fixed-bearing interval using source-backed UTC lens metadata, then design bounded structured end-reply diagnostics; do not assume a shortest unlabeled interval contains Fixed. No need for Owner to re-enter credentials or change camera/router settings. See SD_SAMPLE_GUIDE and SD_MEDIA_REVIEW. Final synthetic validation follows in the checkpoint note; NOT_RUN_BY_DEVELOPER for PO final code.

**OD-45 live session milestone /2026-10-13 — CACHE_REUSE_VERIFIED / REFRESH_VERIFIED:** Owner-requested native bootstrap succeeded and saved a project-only Keychain session. Two independent subsequent use processes each succeeded with one inventory request and no login dialog. One explicit refresh-check succeeded with two auth requests; the original absolute deadline was unchanged. Cached sd-check then verified C545D EXACT, SD NORMAL, timezone +07:00 and 20 first-page SD entries for the existing requested date, using one inventory plus four device requests. No media downloaded or camera settings changed. All probe processes ended. VENDOR_48H_OBSERVED remains UNVERIFIED: this proves immediate reuse/refresh, not uninterrupted operation for 48 hours. Fixed media mapping, download, full-day completeness and counting remain UNVERIFIED. No code changed; latest code validation remains PO 546/546 full and 216/216 targeted PASS, NOT_RUN_BY_DEVELOPER. Next: prepare bounded one-clip retrieval and verify Fixed media under the existing media/storage gates; use the cached session while valid rather than requesting credentials again.

**OD-45 implementation /2026-10-13:** Local project Keychain storage and absolute48h lease are implemented; real disposable cross-process storage/ACL test passed, synthetic543tests passed. These results establish storage/local expiry only, not account cache reuse/vendor refresh or vendor48h availability. Objective-C helper uses existing clang after Swift SDK mismatch. Current live bootstrap evidence in STATUS; camera/media gates unchanged.

**OD-45 implementation authorized:** Owner instructs implementing SESSION_48H_DESIGN. Scoped Python manager plus native Swift Security helper exception and project-only Keychain tokens; exact scope in PROJECT_CONTROL. Implementation/testing in progress; not yet active.

**OD-44 priority:** Owner requests reusable48h authentication. [SESSION_48H_DESIGN](SESSION_48H_DESIGN.md) defines local Keychain session reuse, bounded refresh and absolute expiry before repeated media trials. DESIGN_READY only; not installed/active. Proposed native Security helper is a specifically scoped implementation change to the earlier Python-only plan, using installed Apple tools without new packages. SD-list milestone remains verified.

**OD-43 actual milestone / 2026-10-12:** Home Mac read C545D metadata and20 real SD clip entries for20261012 through the uniquely selected cloud target; SD NORMAL, timezone+07:00,4bounded requests, FIRST_PAGE_ONLY. This supersedes prior SD-unverified statements. Fixed media mapping, actual download, full-day completeness and counting remain unverified. Final PO510tests PASS. Next: bounded one-clip retrieval preparation and actual Fixed-track verification.

**OD-43 / 2026-10-12:** Owner อนุญาต bounded read-only SD metadata/listing จริงผ่าน named target. Implementation และข้อจำกัดอยู่ [SD_PROBE_GUIDE](SD_PROBE_GUIDE.md); ผล actual ล่าสุดดู [STATUS](STATUS.md). PO full503/503 tests PASS; synthetic ไม่แทนผลกล้อง/Fixed/download. เก็บคลิป SD บน Mac ที่บ้านเป็นเป้าหมายเดิม.

> Issue #1 · branch `claude/ft-d0-preflight` · baseline `73249aabf9d413325c4a772cd68a3ebc5890415e`
> สถานะเอกสาร: **D0 review/merge เสร็จตามคำสั่ง Owner 2026-10-07**; PR #2 merged ที่ `b05b8fb`, เวอร์ชันแรก `v0.1.0`. ไม่มีการอนุมัติข้ามเกตอุปกรณ์ของเฟสถัดไป; หลักฐานเดิมด้านล่างเป็นประวัติ
> คำสั่งควบคุมงานอยู่ที่ [PROJECT_CONTROL.md](../PROJECT_CONTROL.md) ซึ่งมีผลเหนือแผนเก่า
> ข้อมูล/อุปสรรคปัจจุบัน: [STATUS](STATUS.md); Owner Decisions: [DECISIONS](DECISIONS.md). Sync ตาม WORKFLOW ไม่เก็บสถานะใหม่ไว้เฉพาะ comments
> ไฟล์ตัวอย่าง `.env.example` และ `config.example.yaml` เป็น **LEGACY / NOT USED** (แผน RTSP/Pi) เอกสารนี้ไม่ได้ใช้ไฟล์เหล่านั้น

## 1. ข้อตัดสินใจ

**OD-40/41/42 ปัจจุบัน (2026-10-12):** Actual cloud login/MFA/inventory ผ่าน 13 กล้อง และจับคู่ชื่อที่ Owner เลือกได้หนึ่งรายการ C545D variant / CLOUD_INVENTORY_ONLY. Fixed เป็นเลนส์เป้าหมายตามภาพ Owner; protocol channel ยังไม่ยืนยัน. Native input ผ่าน iPhone remote ใช้ได้. เตรียม bounded named-target SD metadata/listing และ Fixed mapping ก่อนรอบ auth ถัดไป; ยังไม่มี SD/media downloader หรือ camera/Fixed PASS. Mac รับ SD เองเป็นเป้าหมายเดิม

**OD-37 ปัจจุบัน:** พบ [OnTapo SD relay และ C545D developer research](REMOTE_SD_RESEARCH.md). เลือกตรวจ/ออกแบบ adaptation ของ SD relay ก่อน Tapo Care; คงต้นฉบับ SD และ Mac บ้าน. มี author-reported TC65 download กับ PO static source review แต่ยังไม่มีผล C545D ของเรา จึง CONDITIONAL research ไม่ใช่ live/production PASS. ไม่ต้องเลือกหรือซื้อ Tapo Care ตอนนี้; auth/input/region/Fixed/quota ยังต้องพิสูจน์

**OD-36 ประวัติ — ลำดับ candidate ถูกแทนที่ด้วย OD-37:** ปรึกษา Claude และตรวจ primary sources แล้ว: automatic SD จาก Mac บ้านภายใต้ข้อจำกัดเดิมเป็น NO-GO สำหรับ implementation ตอนนี้ (ไม่ใช่พิสูจน์ว่าเป็นไปไม่ได้ถาวร). พัก acquisition scaffolding เพิ่มและไม่รอ Owner router UI เป็นเกตบังคับของคำตัดสิน. [FEASIBILITY_REVIEW](FEASIBILITY_REVIEW.md) แยก manual SD/local import หนึ่งคลิปกับ Tapo Care cloud-source เป็น CONDITIONAL proposals; cloud ต้องยอมรับ source/privacy/งบและพิสูจน์ auth/Fixed/completeness ใหม่ก่อน. ไม่เปลี่ยน SD spec หรือเปิดเกตวิดีโอ/นับ/ซื้อในงานนี้

**OD-35:** Home-to-shop เป็นเส้นทางที่ Owner ต้องการ; ยกเลิก first trial แบบย้าย Mac ที่ร้านเป็นขั้นบังคับ. อ่าน HOME_CONNECTION_PLAN: ตรวจ shop router UI/VPN Server/WAN access ก่อนเลือก client/tunnel และแก้ overlap; ยังไม่มี live tunnel/SD PASS

**OD-34 (2026-10-08):** PO ตรวจ OS route จริงแล้ว: private endpoint อยู่ใน attached LAN subnet บ้าน, route ไม่ใช่ tunnel; TCP/auth/SD ของกล้องร้านยัง NOT_TESTED. Owner อนุญาต bounded real diagnostic ใน PROJECT_CONTROL; first trial ใช้ Mac เดิมต่อ Wi-Fi ร้าน. ไม่อ้าง D1/D2 PASS จาก route observation และไม่เปลี่ยนสิทธิ์ Dev/settings.

**OD-33 (2026-10-08):** PO จัดการใบงาน/ประสาน Claude/review/ตรวจผลตาม Owner; offline [listing bridge](TAPO_BRIDGE_GUIDE.md) ตรวจรับแล้ว (330/330 PO tests PASS). ไม่เรียก SDK constructor, ปฏิเสธ setter/retry/scope widening ก่อน injected sender และ latch เมื่อข้อมูลผิดพลาด. ทดสอบ Fake SDK กับ static attribute contract เท่านั้น; actual SDK/auth/route/media/Fixed metadata/quota ไม่ผ่านเกตเพิ่ม.

**OD-32 (2026-10-08):** Owner อนุมัติ offline acquisition core; Claude พัฒนาและ PO ตรวจรับ `ft_acquire` กับ synthetic tests แล้ว (295/295 PASS). Request guard/listing/chunk budgets/manifest อยู่ใน [คู่มือ](ACQUISITION_CORE_GUIDE.md); ไม่มี upstream import/transport/auth/real-file publication. Proof flags เป็น input ของ validator ในอนาคต; cooperative deadline ไม่ interrupt callback ที่ค้าง. ไม่เปิดเกตอุปกรณ์และไม่ถือว่าเพดานพัฒนาเป็น quota ที่อนุมัติ live.

**ปัจจุบัน OD-24–28 (2026-10-08):** Owner อนุญาตติดตั้ง acquisition prerequisites แบบแยกบน Mac และอนุมัติ maintenance/control พร้อม private IPv4-input/offline check แล้ว. OD-28 รับ endpoint ที่ Owner ส่งจาก iPhone และบันทึก ignored local config mode 0600; offline validation PASS. คำห้ามติดตั้งเดิมด้านล่างเป็น baseline ก่อนข้อยกเว้นนี้; คำสั่งใหม่ไม่เปิด DNS/socket/auth/SD/video ในงานนี้. Private route/บัญชียังขาด; เกต quota/timezone/Fixed mapping ยังไม่ผ่าน. ใช้ PROJECT_CONTROL เป็น scope ปัจจุบัน.

1. **ทำ acquisition ก่อน ไม่ทำการนับคนแบบเรียลไทม์** เป้าหมายตอนนี้คือรู้ว่าดึงคลิปจากการ์ด SD ของกล้องได้อย่างไร อย่างปลอดภัย และตรวจซ้ำได้
2. **ยังไม่มีการเข้าถึงกล้องหรือเครือข่ายร้าน** FT-D0 ทำได้เฉพาะเอกสาร เครื่องมือ CLI แบบอ่านไฟล์ในเครื่อง และการทดสอบ
3. **ไม่มีฮาร์ดแวร์ใหม่** เป็นข้อจำกัดแน่นอนของ Owner ไม่ใช่ตัวเลือกที่แผนนี้จะเสนอให้ซื้อ และ **ไม่มีการซื้อซอฟต์แวร์** จนกว่า Owner จะอนุมัติข้อเสนอที่ระบุชัด
4. **ใช้ข้อมูลอุปกรณ์ที่ Owner ยืนยันแล้ว** ใน STATUS; ทีมตรวจวิธีรับคลิปและปลายทางจริง ไม่ขอรูปเราเตอร์/ทดลองมือถือซ้ำเป็นเงื่อนไขแรก. การเปลี่ยนเครือข่ายยังต้องมีขอบเขต/rollback ที่อนุมัติ (ดู §6 D1)
5. **Tapo C545D, Hardware 1.0 / Firmware 1.1.7 ยืนยันจากภาพ Device Info ที่ Owner ส่ง 2026-10-07 แล้ว** (OD-16). Router ZTE F6107A HW V9.0.09 / FW F6107A_PON_4.1 ยืนยันจากภาพแล้ว ไม่ปะปนกับ camera firmware
6. PR #2 merge เป็น v0.1.0 ตามคำสั่ง Owner แล้ว; การ merge งานถัดไป, การติดตั้ง, scheduler และ GitHub Actions ไม่ได้รับสิทธิ์อัตโนมัติ

## 2. ข้อเท็จจริง (มีแหล่งที่มากำกับ)

ป้ายที่ใช้: **[Owner]** คุณ Eak แจ้ง · **[PO-verified]** PO ตรวจผ่านการเชื่อมต่อระยะไกลหรือการทดสอบที่ PO รัน · **[PO-checked]** PO ตรวจแหล่งเอกสารภายนอก · **[Repo]** อ่านจากไฟล์ใน repo · **[Dev]** ผลจากการเขียนโค้ด/เอกสารของ Claude ใน FT-D0 · **[UNKNOWN]** ยังไม่มีหลักฐาน

- [Owner] ไม่ซื้อฮาร์ดแวร์เพิ่ม; รายจ่ายซอฟต์แวร์ต้องมีข้อเสนอแยกก่อน
- [Owner] คอมพิวเตอร์ที่บ้านคือ MacBook และอยู่คนละเครือข่ายกับ Wi-Fi ของร้าน
- [Owner, 2026-10-08, OD-21] ร้านไม่มีคอมพิวเตอร์/NAS; ไม่ใช้ shop host เป็น gateway และไม่ซื้อเพิ่ม
- [Owner image, 2026-10-08, OD-22] SD playback: 2026-10-08 เริ่ม 09:51:53 ความยาว 03:00; Fixed + PT Lens. ยืนยันรายการ UI ไม่ใช่ source metadata/timezone หรือช่องทาง export จาก Mac
- [Owner, 2026-10-08, OD-23] ใช้ Fixed Lens เป็นมุมหลัก ไม่ใช้ PT Lens สำหรับการนับ; Owner เปิด playback ขณะอยู่ร้าน. ไม่อนุมาน Wi-Fi/mobile data หรือ remote export จากบ้าน
- [Owner] คลิปเหตุการณ์ในการ์ด SD ของกล้องมีความยาวไม่แน่นอนสูงสุดราว 3 นาที และมีช่องว่างระหว่างคลิป
- [Owner, 2026-10-07, OD-15] กล้องบันทึกเฉพาะเมื่อมีคนเดินผ่าน; ช่องว่างเป็นเงื่อนไขของกล้อง จึงรวมยอดจากคลิปของวันเป็นยอดนับการเดินผ่านทั้งวันได้
- [Owner image, 2026-10-07, OD-16] Device Info: Model C545D, Hardware Version 1.0, Firmware Version 1.1.7; บันทึกค่าที่อ่านได้โดยไม่เก็บภาพใน git
- [Owner] โทรศัพท์ที่อยู่ในร้านดาวน์โหลดคลิปได้ นี่เป็นการดาวน์โหลดด้วยมือ **ไม่ใช่หลักฐานว่าเครื่องที่บ้านดึงอัตโนมัติได้**
- [Owner] ต้องการวิเคราะห์เป็นชุดรายวันหรือตามช่วงเวลาที่กำหนด และนับเฉพาะคนที่เดินผ่าน ไม่นับคนที่นั่ง
- [PO-verified] เข้า shell ระยะไกลของ macOS 14.8.9 บน x86_64 ได้
- [PO-verified] Mac มี RAM 16 GiB และ 8 logical CPU (ข้อมูลเครื่องเท่านั้น)
- [PO-verified] มี Python 3.9.6, git, gh และ claude บน PATH โดยมี Claude CLI เวอร์ชัน 2.1.288
- [PO-verified] Claude runtime/auth: smoke call คืนค่า READY, exit 0, `is_error=false`, `modelUsage` = `claude-sonnet-5` (ยืนยันการรันและการยืนยันตัวตนของ runtime ณ การทดสอบนี้ ไม่ใช่หลักฐานการติดตั้งในเวลาอื่น)
- [PO-verified] การตั้งค่าพลังงาน (อ่านอย่างเดียว ไม่ได้เปลี่ยนค่า): idle sleep = 1 ทั้ง AC และ battery
  **การเปิดเครื่องทั้งคืนยังเป็น UNKNOWN** เพราะยังไม่ได้ตรวจ active wake assertions
- [PO-verified] พื้นที่ว่างประมาณ 20.8 GiB (ค่าณ เวลาที่ตรวจ)
- [PO-verified] ไม่พบ ffprobe และ tailscale บน PATH ซึ่ง **ไม่ได้พิสูจน์ว่าไม่มีแอปแบบ GUI ติดตั้งอยู่**
- [PO-verified] เข้าถึง issue #1 บน GitHub ได้ GitHub connector สร้าง Issue #1 สำเร็จจริง และ git push dry-run ผ่าน; gh auth ไม่ได้ตรวจและไม่ใช่สิ่งที่ต้องเปลี่ยนเพื่อทำ D0
- [PO-verified] PO รัน unittest ชุด 33 เคสบน Mac (Python 3.9.6) ได้ 32 ผ่าน และ 1 ERROR จากลำดับ cleanup ของเทสต์ (ไม่ใช่ความล้มเหลวของสิทธิ์) — รายละเอียดใน STATUS รอบ 2
- [PO-checked] แหล่งภายนอก https://github.com/JurajNyiri/pytapo (ตรวจ 2026-10-06): README ระบุ Python 3.13; ตัวอย่างดาวน์โหลด SD กล่าวถึง ffmpeg; การยืนยันตัวตนขึ้นกับรุ่นและ firmware; ตัวอย่างบันทึกใช้ credential ของบัญชีคลาวด์ในเครื่อง
  **เป็นข้อกำหนดของ upstream ที่เป็นไปได้ (candidate) เท่านั้น** ต้อง pin และตรวจ release ที่เลือกก่อนติดตั้งใน runtime แยก
  ห้ามประกาศว่า Python 3.9 พร้อมสำหรับ downloader
- [PO-checked] README ของ pytapo เตือนว่า integration test ของ upstream อาจย้ายกล้อง เปลี่ยน privacy mode และรีบูต **จึงห้ามรันใน FT-D0 และห้ามรันโดยไม่ได้รับอนุมัติเฉพาะ**
- [Repo] เอกสารเดิม (baseline) วางแผนใช้ Raspberry Pi 5 ในร้าน RTSP แบบ real-time และ systemd ซึ่ง **ถูกแทนที่แล้ว**
- [Repo] **LEGACY / NOT USED:** `.env.example` และ `config.example.yaml` เป็นแม่แบบของแผน Pi/RTSP เดิม **`tools/ft_data.py` ไม่อ่านไฟล์เหล่านี้** ยังไม่ได้ตรวจทาน และอยู่นอกขอบเขตที่แก้ได้ใน FT-D0 จึงไม่แก้ไข
- [Dev] `tools/ft_data.py` เป็น CLI ที่ใช้ stdlib อย่างเดียว อ่านไฟล์ในเครื่องเท่านั้น และไม่ดึงข้อมูลจากกล้อง
- [Dev] `.github/ISSUE_TEMPLATE/claude-task.md` ยังไม่ได้ตรวจทาน และอยู่นอกขอบเขตที่แก้ได้ใน FT-D0

## 3. สมมติฐานและ UNKNOWN

| หัวข้อ | สถานะ | หมายเหตุ |
| --- | --- | --- |
| Camera Hardware/Firmware | CONFIRMED | C545D / Hardware 1.0 / Firmware 1.1.7; ภาพ Owner 2026-10-07, OD-16 |
| Router model/HW/FW | CONFIRMED | ZTE F6107A / V9.0.09 / F6107A_PON_4.1; route/VPN capability ยัง NOT_TESTED |
| บัญชีและวิธียืนยันตัวตนกับกล้อง | UNKNOWN | ประเภทข้อมูลลับขึ้นกับ adapter ที่เลือก |
| การแสดงรายการคลิปใน SD (pagination, ความครบ) | UNKNOWN | ยังไม่ทดสอบ |
| เวลาเริ่มของคลิปจาก metadata ต้นทาง และความหมายของเขตเวลา | UNKNOWN | ยังไม่ยืนยันเขตเวลา ห้ามแปลง UTC เป็นเวลาไทยโดยเดา ห้ามใช้ชื่อไฟล์หรือ mtime แทน ถ้าดัชนีไม่มี timestamp ให้เสนอแหล่งเวลาที่ตรวจสอบได้ |
| ขนาดและนาทีต่อคลิปจริง | UNKNOWN | ต้องวัดจากตัวอย่างจริงก่อนตั้งงบ |
| นโยบายเก็บรักษาและสำรองพื้นที่ | UNKNOWN | เป็นการตัดสินใจของ Owner |
| ช่วงเวลาดึงข้อมูลที่ต้องการ | UNKNOWN | เป็นการตัดสินใจของ Owner ตอน D5 |
| ปลายทางชั่วคราวของวิดีโอ | UNKNOWN | ต้องอยู่นอก git และมีโควตา |
| ความเข้ากันได้ของ `pytapo` กับ C545D | UNKNOWN | release 3.4.26 pin/ตรวจ static/ติดตั้ง runtime แยกแล้ว OD-24; ยังไม่เชื่อมกล้อง |
| การเปิดเครื่องทั้งคืน (active wake assertions) | UNKNOWN | ยังไม่ได้ตรวจ ความน่าเชื่อถือข้ามคืนจึงยังไม่รู้ ห้ามเปลี่ยนการตั้งค่าพลังงาน |

## 4. ตารางความพร้อม

ค่า STATUS: PASS (มีหลักฐาน) · BLOCKED (มีปัญหาที่รู้แล้ว) · UNKNOWN (ยังไม่มีหลักฐาน) · NOT_REQUIRED (ไม่จำเป็นในเฟสนี้) · INFO (ข้อมูลประกอบ ไม่ใช่เกต)

| รายการ | STATUS | หลักฐาน/แหล่ง | ขั้นถัดไป | ผู้รับผิดชอบ | บล็อกเฟส |
| --- | --- | --- | --- | --- | --- |
| เข้า shell ระยะไกลบน Mac | PASS | [PO-verified] macOS 14.8.9 x86_64 | ไม่มี | PO | — (ไม่ใช่การเข้าถึงกล้อง) |
| ฮาร์ดแวร์ Mac | INFO | [PO-verified] RAM 16 GiB, 8 logical CPU | ไม่มี | — | — |
| Python สำหรับ tool | PASS | [PO-verified] 3.9.6; unittest 52/52 ผ่าน | ไม่มีสำหรับ D0 | PO | — |
| git / gh / claude บน PATH | PASS (การมีอยู่เท่านั้น) | [PO-verified] | ไม่มี | — | — |
| Claude CLI / runtime / auth | PASS | [PO-verified] smoke: READY, exit 0, is_error=false, modelUsage claude-sonnet-5 | ตรวจซ้ำถ้าเปลี่ยน CLI หรือบัญชี | PO | D0 |
| การตั้งค่าพลังงาน: idle sleep | PASS (อ่านอย่างเดียว) | [PO-verified] idle sleep = 1 ทั้ง AC และ battery; ไม่ได้เปลี่ยนค่า | ไม่มี | PO | — |
| การเปิดเครื่องทั้งคืน (active wake assertions) | UNKNOWN | ยังไม่ได้ตรวจ | ตรวจแบบอ่านอย่างเดียวเมื่อ Owner ต้องการ ไม่เปลี่ยนค่า | PO | D2 (ถ้าต้องดึงนอกเวลา) |
| gh auth | NOT_REQUIRED | ไม่ได้ตรวจ; งานนี้ใช้ git push + GitHub connector; dry-run ผ่านและสร้าง Issue #1 แล้ว | ตรวจผล push/PR จริงใน GitHub | PO | — |
| ffprobe | NOT_REQUIRED | ไม่พบบน PATH; ยังไม่ตัดสินใจว่าจะใช้หรือไม่ | ตัดสินใจก่อน D2 ว่าต้องใช้เพื่อตรวจ container หรือไม่ | Owner/PO | D2 (ถ้าเลือกใช้) |
| tailscale | NOT_REQUIRED | ไม่พบบน PATH; ทางเชื่อมต่อยังไม่เลือก | ทีมเลือกวิธีจากข้อมูลยืนยันแล้ว | PO | D1 (ถ้าเลือกทางนี้) |
| ML / Google Sheets / cloud | NOT_REQUIRED | ไม่จำเป็นสำหรับ D0 | เปิดข้อเสนอแยกในอนาคต | Owner | D4 |
| พื้นที่ว่าง ~20.8 GiB | PASS (เทียบเกณฑ์เสนอ 10 GiB) | [PO-verified] ค่าณ เวลาตรวจ; เกณฑ์ยังไม่ผ่านการอนุมัติ | Owner ยืนยันเกณฑ์ | Owner | D2/D3 |
| งบไบต์และนาทีต่อวัน | UNKNOWN | ยังไม่มีตัวอย่างจริง | วัดจากคลิปตัวอย่าง 1 คลิปใน D2 แล้วตั้งงบ | PO + Owner | D3 |
| รุ่นเราเตอร์ / VPN capability | MODEL_CONFIRMED / VPN_UNKNOWN | รุ่นและเวอร์ชันอยู่ STATUS | ทีมเลือกวิธีจากข้อมูลเดิม ไม่ขอรูปเพิ่มเป็นเงื่อนไขแรก | PO + Claude | D1 |
| เส้นทางข้ามเครือข่าย | BLOCKED_ROUTE_OVERLAP | OD-34 OS route: private target ทับ LAN บ้าน ไม่ผ่าน tunnel | first trial Mac เดิมต่อ Wi-Fi ร้าน; PO ตรวจ bounded TCP เมื่อยืนยันเครือข่ายร้าน | PO + Owner งานย้ายเครื่อง | D1/D2 |
| เครือข่ายร้านเข้าถึงจาก Mac ที่บ้าน | UNKNOWN | ยังไม่มีเส้นทางที่พิสูจน์ได้ | ออกแบบเส้นทางใน D1 แล้วตั้งค่าเป็นขั้นแยกที่ได้รับอนุมัติ | Owner + PO | D1 |
| Camera Hardware/Firmware | CONFIRMED | ภาพ Owner: C545D / HW 1.0 / FW 1.1.7 | ไม่ขอซ้ำ; ทีมใช้เลือก adapter และตรวจ compatibility | PO + Claude | — (ข้อมูลรุ่น ไม่ใช่ SD export PASS) |
| อินเทอร์เฟซอ่านอย่างเดียวของกล้อง | UNKNOWN | ยังไม่มีการตรวจ | ยืนยันด้วยเอกสารทางการ/หน้าเครื่อง ไม่ใช่ฟังก์ชันที่คิดเอง | Dev + Owner | D1 |
| ประเภทข้อมูลลับสำหรับดึง SD | UNKNOWN | ขึ้นกับ adapter | เลือก adapter ก่อนแล้วกำหนดประเภทใน D1 (เก็บในเครื่องเท่านั้น ไม่ส่งในแชต) | PO | D1 |
| candidate downloader (`pytapo`) | UNKNOWN | [PO-checked] 3.4.26 pin/static audit และ isolated installation แล้ว OD-24 | ยังต้อง route/auth/SD/Fixed compatibility; ไม่รัน integration test ของ upstream | Dev/PO + Owner | D1/D2 |
| การดาวน์โหลดอัตโนมัติจาก Mac บ้าน | UNKNOWN | มีแค่การดาวน์โหลดด้วยมือจากโทรศัพท์ | พิสูจน์ใน D2 เท่านั้น | Dev/PO | D2 |
| การแสดงรายการคลิปและความครบ | UNKNOWN | ยังไม่ทดสอบ | ทดสอบช่วงสั้นใน D2 | Dev | D2 |
| เขตเวลาของ timestamp | UNKNOWN | ยังไม่มีแหล่งที่ยืนยัน | ยืนยันจาก metadata ต้นทางและความหมายของเขตเวลา | Dev | D2 |
| inventory และ doctor (โค้ด) | PASS | [PO-verified] unittest 52/52, regression แยก 7/7; [หลักฐาน](FT_D0_EVIDENCE.md) | Owner review/merge | PO + Owner | D0 review |
| นโยบายเก็บรักษาและ reserve | UNKNOWN | ยังไม่ได้ตัดสินใจ | Owner ตัดสินใจก่อน D2 | Owner | D2 |
| ช่วงเวลาดึงที่ต้องการ | UNKNOWN | ยังไม่ได้ระบุ | Owner ระบุก่อน D5 | Owner | D5 |
| สถานะระบบจริงหน้าร้าน | UNKNOWN / NOT TOUCHED | [PROJECT_CONTROL] ไม่ได้รับอนุญาตให้ตรวจ | ไม่มี | — | ทุกเฟส |
| ไฟล์ตัวอย่าง RTSP/Pi (`.env.example`, `config.example.yaml`) | NOT_REQUIRED (LEGACY) | [Repo] ไม่ได้ใช้โดย CLI | ไม่แก้ในรอบนี้; Owner/PO ตัดสินใจภายหลัง | Owner/PO | — |

## 5. โซ่การเชื่อมต่อ

```text
PO / ChatGPT  ──(PASS: เข้า shell Mac ที่บ้าน)──▶  MacBook ที่บ้าน  ──(UNKNOWN)──▶  เครือข่ายร้าน  ──(UNKNOWN)──▶  กล้อง / SD
```

- **การควบคุม Mac ระยะไกล ≠ การเข้าถึงกล้อง** ข้อแรกพิสูจน์แล้ว ส่วนที่เหลือยังไม่มีหลักฐาน
- **การติดตั้ง VPN ที่บ้านอย่างเดียว ไม่ทำให้กล้องในร้านเข้าถึงได้** เพราะกล้องอยู่บนเครือข่ายของร้าน
- **การซื้อคลาวด์ไม่ทำให้ดึง SD ได้โดยอัตโนมัติ** ต้องพิสูจน์ช่องทางรับ/ส่งออกที่กล้องหรือระบบเดิมรองรับ เช่นเส้นทางเข้าร้านหรือบริการของผู้ผลิตที่รองรับงานนี้จริง ห้ามสมมติว่ามี remote API
- รุ่นเราเตอร์/เวอร์ชัน/แพ็กเกจยืนยันแล้ว; ทีมเลือกวิธีเข้าถึงจากหลักฐาน ไม่บังคับให้ Owner หาข้อมูลทุกเมนูหรือทำการทดลองมือถือเพิ่ม หากต้องการข้อมูลเครือข่ายเพิ่มให้ระบุเหตุผลตามวิธีที่เลือก
- Port forwarding ของ RTSP ยังไม่แนะนำ เพราะการเข้ารหัสและความปลอดภัยยังไม่ผ่านการประเมิน
- ทางเลือกที่ต้องมีอุปกรณ์ใหม่ในร้าน **ไม่อยู่ในแผนนี้** (ข้อจำกัด: ไม่มีฮาร์ดแวร์ใหม่)

## 6. เฟส

| เฟส | เป้าหมาย | ทำอะไร | เสร็จเมื่อ | ไม่ทำ |
| --- | --- | --- | --- | --- |
| **D0** เตรียม | เอกสาร + CLI อ่านอย่างเดียว | เขียน `tools/ft_data.py`, ทดสอบ, อัปเดตเอกสาร | PO รันทดสอบ, ตรวจ PR, Owner merge | เข้ากล้อง, เข้าเครือข่ายร้าน, ดึงวิดีโอ, เปลี่ยนการตั้งค่าใด ๆ |
| **D1** เส้นทางและอินเทอร์เฟซ | ออกแบบเส้นทางพร้อมหลักฐาน และเตรียมคำขอตั้งค่าที่อนุมัติเป็นรายครั้ง | ใช้รุ่นเราเตอร์/ISP/กล้องที่ยืนยันแล้ว ใช้ camera version ที่ยืนยันแล้ว รับ endpoint readiness ที่ขาด, ทีมเลือกเส้นทาง, ยืนยันอินเทอร์เฟซอ่านอย่างเดียว, กำหนดประเภทข้อมูลลับ (เก็บในเครื่อง), นโยบายพื้นที่. **การตั้งค่าเส้นทางจริงเป็นขั้นแยก** ที่ Owner อนุญาตเฉพาะ (ก) เป้าหมายและสภาพแวดล้อม (ข) ขั้นตอนและผลที่คาดไว้ (ค) แผนย้อนกลับ | เอกสารหลักฐาน + Owner อนุมัติขั้นตั้งค่า (ถ้ามี) และ D2 | เปลี่ยนการตั้งค่าเราเตอร์/กล้อง/VPN โดยไม่มีการอนุมัติเป้าหมายและแผนย้อนกลับ |
| **D2** ดึงหนึ่งคลิป | พิสูจน์ว่าดึงได้จริงและซ้ำได้ | แสดงรายการช่วงสั้น, ดึงคลิปที่อนุมัติ **1 คลิป**, ตรวจเนื้อหา/เวลา/ความยาว, ทำซ้ำแล้วไม่เกิดรายการซ้ำ | ผลบันทึกแล้ว Owner อนุมัติ D3 | ดึงหลายคลิป, ตั้ง schedule |
| **D3** ดึงรายวัน | ดึงเป็นชุดอย่างทนทาน | resume, dedup (ไบต์เหมือนกัน), manifest, ขีดจำกัดงบ, retry แบบจำกัดจำนวน | เกณฑ์ข้อ 7 ผ่านและมีตัวเลขงบจากตัวอย่างจริง | ทำงานอัตโนมัติ |
| **D4** นับคนและกรอง | วิเคราะห์ตามช่วงเวลา | ข้อเสนอแยกสำหรับโมเดลและตัวกรอง (เฉพาะคนเดินผ่าน ไม่นับคนนั่ง) | Owner อนุมัติข้อเสนอ และผ่านเกณฑ์ความแม่นยำที่ PLAN.md กำหนดในส่วนข้อกำหนดที่ยังใช้ต่อ | อ้างผลนับหรือความแม่นยำผ่านก่อนทดสอบ |
| **D5** นำร่องและตั้งเวลา | ทำงานประจำ | ตั้ง scheduler แยกจากคำสั่งที่รันด้วยมือ | Owner อนุมัติเป็นลายลักษณ์อักษร | ทำก่อนได้รับอนุมัติ |

## 7. เกณฑ์หลักฐานก่อนเปิดงบ (D2–D3)

1. **การแสดงรายการคลิป**: อ่านทุกหน้าจนหมด บันทึกจำนวนหน้า และยืนยันว่าไม่มีหน้าถัดไป ถ้าผลชนเพดานหรือไม่มีคำตอบว่าจบ ให้ถือว่า **ไม่ครบ**
2. **เวลา**: ใช้เวลาเริ่มจาก metadata ของต้นทางเท่านั้น หลังยืนยันความหมายของเขตเวลาแล้ว (ห้ามแปลง UTC เป็นเวลาไทยโดยเดา) ชื่อไฟล์และ mtime ใช้ไม่ได้ ถ้าดัชนีไม่มี timestamp ให้เสนอแหล่งเวลาที่ตรวจสอบได้ก่อนดำเนินการ
3. **ความครบของแคตตาล็อกกับคลิปที่บันทึกคน**: แยกสองเรื่องนี้ออกจากกัน แคตตาล็อกครบ (catalog complete) หมายถึงกล้องแสดงรายการครบในช่วงที่ขอ ส่วนคลิปที่มีคนจริง (persons recorded) เป็นอีกเรื่องหนึ่ง
4. **ช่องว่างระหว่างคลิป**: Owner ยืนยันว่ากล้องบันทึกเฉพาะตอนมีคนเดินผ่าน (OD-15); เป็นเงื่อนไขปกติ ไม่ถือเป็นข้อมูลขาด และไม่เพิ่มยอดในช่วงไม่มีเหตุการณ์. รวมคลิปครบตามรายการต้นทางของวันเป็นยอดนับทั้งวันได้; ไฟล์ที่ดาวน์โหลดขาด/ล้มเหลวต้องแยกรายงาน
5. **ขนาดและนาที**: วัดจากคลิปตัวอย่างจริงก่อน แล้วค่อยกำหนดงบต่อวันและต่อครั้ง งบที่ตั้งก่อนมีตัวอย่างจริงถือว่าไม่ผ่าน
6. **เพดาน**: จำนวนคลิปสูงสุด, ไบต์สูงสุด และช่วงวันที่สูงสุดต้องมาจาก Owner (ค่าทดสอบในเอกสารนี้ไม่ใช่การอนุมัติ)
7. **พื้นที่สำรอง**: ตรวจพื้นที่ว่างก่อนเริ่มทุกครั้ง ค่าเสนอ 10 GiB ยังไม่ผ่านการอนุมัติ
8. **กันซ้ำ ทับซ้อน และกันไฟล์ขาด**: แฮช SHA256 + ขนาด ตรวจได้เฉพาะไบต์ที่เหมือนกันทุกประการ **ไม่ใช่ dedup ของวิดีโอที่ทับซ้อนหรือถูกเข้ารหัสใหม่หรือฉากที่เหมือนกัน** การกันทับซ้อนตามช่วงเวลาจาก metadata ต้นทางและ ID ของกล้องเป็นงาน D3/D4 ดาวน์โหลดลงไฟล์ชั่วคราว ตรวจขนาดแล้วจึงย้ายชื่อ ไฟล์ที่ค้างไม่ถูกนับเป็นคลิปที่ดึงสำเร็จ
9. **ลองใหม่จำกัดจำนวน**: กำหนดเพดานการลองใหม่ต่อคลิป เมื่อเกินให้บันทึกสถานะ FAILED พร้อมรหัสเหตุผล ห้ามข้ามเงียบ ๆ และห้ามนับเป็นศูนย์
10. **ทำซ้ำได้**: รันซ้ำช่วงเดิมแล้วต้องไม่เกิดรายการซ้ำและไม่เกิดการดึงซ้ำที่ไม่จำเป็น
11. **manifest**: เก็บเฉพาะข้อมูลอธิบาย (ID, ขนาด, แฮช, เวลาจากกล้อง, สถานะ) ไม่เก็บวิดีโอและไม่เก็บ path จริงในไฟล์ที่แชร์ได้

## 8. การแยกการควบคุมด้วยมือออกจากงานอัตโนมัติ

- **คำสั่งที่ Owner หรือ PO รันเอง** (foreground) ต้องระบุช่วงเวลาและผลลัพธ์ชัดเจน
- **งานอัตโนมัติ** (scheduler) เป็นเรื่องของ D5 เท่านั้น ต้องมีข้อเสนอแยก ต้องมีการอนุมัติ และต้องไม่ถูกตั้งไว้ใน FT-D0
- GitHub Issue ไม่ใช่ worker ที่ทำงานเองอยู่เบื้องหลัง ไม่มี Actions หรือ schedule ที่เปิดใช้งาน

## 9. ข้อกำหนดที่ต้องได้จาก Owner ตามเกต

| ข้อมูล | ต้องการที่เกต |
| --- | --- |
| รุ่นเราเตอร์/เวอร์ชัน/แพ็กเกจ | ยืนยันแล้ว; ไม่ขอซ้ำ; route เป็นงานทีม D1 |
| Camera Hardware/Firmware | ยืนยันแล้ว C545D / HW 1.0 / FW 1.1.7; ไม่ขอซ้ำ |
| การเข้าถึงที่ Owner ตั้งเองในเครื่อง (ไม่ส่งรหัสผ่านในแชตหรือ Issue) | D1 หรือ D2 |
| นโยบายเก็บรักษาและพื้นที่สำรอง | ก่อน D2 |
| ช่วงเวลาดึงที่ต้องการ | D5 เท่านั้น |

## 10. ข้อควรรู้เรื่องความเป็นส่วนตัวและความปลอดภัย

- ห้ามเก็บวิดีโอ ภาพ รหัสผ่าน IP ของร้าน หมายเลขซีเรียล หรือข้อมูลส่วนบุคคลใน git หรือหลักฐานที่แชร์ได้
- **ไม่ขอ secret หรือรหัสผ่านในแชต** และไม่ใส่ใน Issue หรือคำสั่ง ให้เก็บในเครื่องที่ Owner ตั้งเองเท่านั้น
- **ไม่เปลี่ยนการตั้งค่าบัญชีโดยอัตโนมัติ** (รวมบัญชีคลาวด์และ privacy mode ของกล้อง)
- **ห้ามรัน integration test ของ upstream** ของไลบรารีที่เชื่อมกับกล้องจริง เพราะ README ของ [pytapo](https://github.com/JurajNyiri/pytapo) เตือนว่าอาจย้ายกล้อง เปลี่ยน privacy mode และรีบูต (ตรวจ 2026-10-06)
- ห้าม commit `data/`, `reports/`, `artifacts/`, `*.jsonl`, config ท้องถิ่น, วิดีโอดิบ และ log (ดู `.gitignore`)
- ห้ามอ่านโฟลเดอร์บ้านหรือไฟล์ความลับของ Owner โดยไม่ได้รับคำสั่งเฉพาะ
- เอกสารอ้างอิงที่ใช้: [Claude Code headless](https://code.claude.com/docs/en/headless) · [Claude Code model config](https://code.claude.com/docs/en/model-config) · [pytapo](https://github.com/JurajNyiri/pytapo) (candidate เท่านั้น ยังไม่ได้ pin release และยังไม่ได้ตรวจความเข้ากันได้กับ C545D)

## 11. ประวัติการพัฒนา D0 (สถานะล่าสุดอยู่ STATUS.md)

- รอบ 1: เอกสาร, `tools/ft_data.py`, `tests/` (stdlib unittest เท่านั้น)
- รอบ 2 (ตามผล PO และคำสั่ง PO ฉบับอิสระ): แก้ root symlink แบบ `/.`, การสลับโฟลเดอร์เป็นลิงก์, การอ่านไฟล์ที่กำลังเปลี่ยน, การสะท้อนค่าอาร์กิวเมนต์ใน error, ลำดับ cleanup ของเทสต์ และอัปเดตเอกสารตามข้อสรุป PO
- ผู้พัฒนาไม่ได้รันทดสอบ (NOT_RUN_BY_DEVELOPER); **PO รันแยกแล้ว 52/52 ผ่าน และ regression 7/7 ผ่าน** ดู [FT_D0_EVIDENCE.md](FT_D0_EVIDENCE.md). ผลรุ่นแรกที่มี 1 ERROR เก็บไว้ในประวัติ ไม่ได้ซ่อนหรือข้ามเทสต์
- ไม่มีการเข้าถึงกล้อง เครือข่ายร้าน หรือวิดีโอจริง
- Claude ไม่ได้ push; PO เป็นผู้จัด commit/push/PR หลังตรวจ. ไม่มี merge, ติดตั้ง, เปลี่ยนการตั้งค่าเครื่อง หรือปิด Issue

## 12. Owner Execution Roadmap

อัปเดต 2026-10-06 ตามคำขอ Owner ให้ระบุขั้นตอน เจ้าของงาน และสิ่งที่ต้องช่วยเพื่อปลดล็อกงาน.
**นี่คือแผน ไม่ใช่การอนุมัติข้ามเฟส:** ยังอยู่ FT-D0 / Issue #1 / PR #2; ไม่มีสิทธิ์ติดตั้ง เข้ากล้อง เปลี่ยนเครือข่าย หรือรันรายคืนเพิ่มจากเอกสารนี้.
เป้าหมายส่งมอบแรก: **MacBook ที่บ้านอ่านรายการบันทึกของกล้องร้าน และดึงหนึ่งคลิปที่อนุมัติได้จริง พร้อมเวลาและความยาวที่ตรวจสอบได้**. CLI เป็นทางเริ่มต้น; UI และการนับคนตามมาหลังพิสูจน์การรับข้อมูล.

| เฟส | งานของ PO / Claude | สิ่งที่ Owner ช่วย | เกณฑ์รับงาน | สถานะ |
| --- | --- | --- | --- | --- |
| D0 เตรียม | Control, roadmap, doctor/inventory, tests และหลักฐาน | ตรวจ PR #2 และ merge เมื่อเห็นชอบ | เอกสาร/โค้ดผ่านการตรวจและ Owner merge; ไม่อนุญาต deploy โดยปริยาย | D0 merged เป็น v0.1.0; tests รวม 113 PASS รอบ workflow และ regression 7 checks ตามหลักฐานเดิม |
| D1 วิธีรับข้อมูล | ตรวจอุปกรณ์เดิม เลือกช่องทางเข้าถึงและ adapter; ระบุ dependencies/สิทธิ์/งบ/rollback | camera version/endpoint-account readiness และคลิปเป้าหมาย; รุ่นเราเตอร์ตอบแล้ว | มีแบบที่ตรงอุปกรณ์; ถ้าต้องตั้งค่า ให้ Owner อนุมัติเป้าหมายและขั้นตอนก่อน แล้วพิสูจน์เส้นทางจริง | รอข้อมูลหน้างาน; ยังไม่ตั้งค่า |
| D2 หนึ่งคลิป | อ่านรายการช่วงสั้น ดึงหนึ่งไฟล์ ตรวจเนื้อหา/เวลา/ความยาวและการรันซ้ำ | เลือกช่วงเวลาที่ยังเปิดย้อนหลังได้; กรอก secret ในเครื่องผ่านช่องทางที่จัดให้; อนุมัติชุดทดลอง | ดึงจาก Mac บ้านได้ เปิดไฟล์ได้ เวลาเทียบต้นทางตรง รันซ้ำไม่ซ้ำ กล้องยังบันทึกปกติ | รอ D1 และสิทธิ์ทดลอง |
| D3 รายวัน | อ่านรายการครบหน้า manifest งานค้าง/ทำต่อ retry จำกัด quota และตรวจไฟล์ซ้ำ/เวลาทับซ้อน | ยืนยันเพดานข้อมูลและการเก็บหลังวัดขนาดจริง | ครบตามรายการต้นทางที่ตรวจได้ หรือระบุไฟล์ขาดชัด; ทดสอบเน็ตหลุด/รันซ้ำ/พื้นที่ต่ำ | ยังไม่เริ่ม |
| D4 นับและกรอง | Ground truth, line crossing, seated negatives, เวลาแต่ละเหตุการณ์และตัวกรอง | ตรวจเส้นนับ กติกาเดินกลับ และตัวอย่างรายงาน | คง baseline 80% พร้อม FP/FN และชุดทดสอบแยกตาม PLAN; รายงานยอดการเดินผ่านทั้งวันตาม OD-15; ไม่อ้างว่าเป็นจำนวนบุคคลไม่ซ้ำ | ยังไม่เริ่ม |
| D5 งานประจำ | Scheduler เฉพาะงาน ตรวจ sleep/งานซ้อน/วันตกค้าง ข้อผิดพลาดและ rollback | เลือกเวลาและอนุมัติวิธีไม่พักเครื่อง/scheduler/pilot | ข้อเสนอเกณฑ์: ผ่าน 3 รอบรายวันต่อกัน พร้อมรายการครบ/ขาด ไม่มี failure ที่ไม่รายงาน; ต้องอนุมัติก่อนใช้เป็นเกณฑ์จริง | ยังไม่เริ่ม; ไม่มี schedule |

### หลักการทำงานไม่ให้ติดโดยไม่จำเป็น

- Checklist §13 ระบุเฉพาะข้อมูลที่ยังขาด; ข้อมูลอุปกรณ์ที่ Owner ยืนยันอยู่ใน STATUS/DECISIONS ไม่ขอซ้ำ ไม่บังคับทดลองผ่านมือถือ. ส่งข้อมูลคู่กับ review PR ได้
- PO จัดทำการวิเคราะห์จากเอกสารในขอบเขตเตรียมงานได้ระหว่างรอข้อมูล; Claude ยังไม่เริ่ม downloader หรือแตะอุปกรณ์จนมี control transition.
- ไม่ต้องสร้างระบบสั่ง AI ใหม่: ช่องทางรีโมต Mac → Claude → PO test → GitHub PR พิสูจน์ใน D0 แล้ว.
- ยังไม่ต้องมี ML weights, Dashboard, Sheets credential, Actions, cloud subscription หรือ VPN ที่เลือกโดยยังไม่ทราบอุปกรณ์.
- พื้นที่ว่างราว 20.8 GiB เป็นผลตรวจครั้งก่อน ไม่ใช่พื้นที่รับรองตลอดไป ต้องตรวจใหม่ก่อนดาวน์โหลด; reserve 10 GiB ยังเป็นข้อเสนอ.
- ก่อนรันรายคืนต้องทดสอบ power/sleep และการทำงานตกค้างเมื่อเครื่องปิด; ไม่บล็อกการทดลองที่สั่งด้วยมือ.
- เลข D0–D5 เป็นเฟส ไม่ใช่จำนวนวัน ประเมินระยะเวลาหลังรู้เส้นทางและวัดขนาด/ความเร็วจริง ไม่รับรองเวลาจากสมมติฐาน.

### จุดตัดสินใจเรื่องการเชื่อมต่อ

ผลล่าสุด: [ACQUISITION_ROUTE_DECISION](ACQUISITION_ROUTE_DECISION.md) ตรวจคู่มือ AIS F6107A และ source `pytapo` แบบ static; ยังไม่ยืนยัน private route/server capability หรือ remote SD API สำหรับ Mac. ชุดคำถามเฉพาะ capability พร้อมให้ Owner ใช้ถาม AIS/TP-Link; ไม่มีการติดต่อจริง ไม่มี network/device test. ถ้า Owner เลือก local/manual trial ให้จัด scope แยก ไม่ถือเป็น automatic acquisition จากบ้านผ่าน.

PO ต้องตรวจอุปกรณ์เดิม/ผู้ดูแลเครือข่ายจริงก่อนเลือกวิธี ไม่สมมติว่าเราเตอร์ทุกตัวทำ VPN ได้ หรือซื้อคลาวด์แล้วดึง SD ได้.
หากไม่มีช่องทางอัตโนมัติที่พิสูจน์ได้ภายใต้ข้อจำกัดไม่ซื้อฮาร์ดแวร์ ให้หยุดสร้าง downloader ตามการคาดเดาและสรุปหลักฐานให้ Owner เลือกทางที่ทำได้.
Manual import เป็นทางสำรองสำหรับพัฒนาการนับ ไม่ใช่ automatic acquisition ผ่าน. อุปกรณ์เดิมอีกตัวในร้านใช้เป็นทางเลือกได้เฉพาะเมื่อ Owner ยืนยันว่ามีและอนุญาต ไม่เสนอซื้อเพิ่ม.

### CLI เป้าหมาย

มีอยู่จริง: `doctor`, `inventory`.
ต้องพัฒนาหลังได้รับอนุมัติ: ตรวจการเชื่อมต่อเฉพาะเป้าหมาย → อ่านรายการตามเวลา → ดาวน์โหลดหนึ่งคลิป → ตรวจไฟล์ → ดึงเป็นชุด/ทำงานค้างต่อ.
นี่เป็นลำดับคำสั่งที่ออกแบบไว้ ไม่ใช่คำสั่ง downloader ที่พร้อมรัน. ต้องมี exit code, สถานะครบ/ขาดและ log ที่ปกปิดข้อมูลลับ; ห้ามขยายช่วงวันที่หรือเปลี่ยนการตั้งค่ากล้องเอง.
วิดีโอเก็บนอก git ภายใต้เพดานที่อนุมัติ; ไม่ส่ง raw video หรือ secret ขึ้น GitHub หรือให้ coding agent อ่านโดยไม่จำเป็น.

## 13. Owner Checklist

อัปเดตหลัง Owner ยืนยันอุปกรณ์และสั่งทดลองดึงจริง: ไม่ขอรูป/สเป็กเราเตอร์หรือแพ็กเกจซ้ำ ไม่บังคับทดลอง 4G/5G เพิ่ม. ข้อมูลยืนยันแล้วอยู่ STATUS; การตัดสินใจอยู่ DECISIONS

### ข้อมูลที่ยังต้องการตอนนี้

ข้อมูลกล้องยืนยันแล้ว: C545D / Hardware 1.0 / Firmware 1.1.7 (ภาพ Owner; OD-16). ขอเฉพาะข้อมูลที่ยังขาด:

1. IP/ปลายทางกล้องรับและบันทึกส่วนตัวบน Mac แล้ว OD-28; ไม่ต้องส่งซ้ำ ไม่ใส่ค่าบน GitHub/ใน prompt. Owner ใช้ iPhone ต่อได้; Codex รันงาน Mac ตาม scope
2. แอป Tapo ใช้ได้, Version 3.21.106, Camera Account On และ Third-Party Compatibility On ยืนยันแล้ว (OD-18/19/20); ไม่ขอซ้ำ. เหลือ readiness ของบัญชีตาม adapter ที่เลือก; ไม่ขอ secret ในแชตและไม่สั่งเปลี่ยนค่า
3. คลิปเป้าหมายมีแล้ว: 2026-10-08 เริ่ม 09:51:53 / 03:00 (OD-22). Owner เลือก Fixed Lens ไม่ใช้ PT Lens และเปิดภาพขณะอยู่ร้าน (OD-23); ไม่ขอซ้ำ ไม่ต้องทดลองสลับ network หรือส่งวิดีโอ. ทีมต้องตรวจ channel mapping/metadata จากไฟล์ก่อนรับผล

### งานทีม ไม่ใช่ภาระให้ Owner ออกแบบ

PO + Claude เลือก adapter/release และ runtime ที่เข้ากันได้, จัด private input, เสนอขอบเขต/พื้นที่/rollback และบันทึก control ตามคำสั่งทดลองที่ได้รับแล้ว ไม่วนขออนุมัติทั่วไปซ้ำ
ทีมตรวจเส้นทางบ้านไปกล้องเป้าหมายและสร้างตัวดึงหนึ่งคลิป ไม่ถือ Wi-Fi ยี่ห้อเดียวกันหรือ RTSP ผ่านเป็นหลักฐาน SD export ผ่าน
หากต้องใช้ข้อมูลจากผู้ดูแลเครือข่ายเพิ่มเติมให้ระบุเหตุผลจากวิธีที่เลือก ไม่กลับไปบังคับภาพเราเตอร์ทุกเมนูเป็นขั้นแรก

### ก่อนทดลองและภายหลัง

ให้ Mac พร้อมช่วงทดลอง; ทีมตรวจพื้นที่ใหม่และเสนอเพดานหนึ่งคลิป/bytes/reserve ไม่ลบไฟล์หรือเปลี่ยน power settings เอง
เวลารัน, ระยะเวลาเก็บ, reserve, งบซอฟต์แวร์, เส้นนับและกติกาเดินกลับ รอผลทดลอง/การตัดสินใจที่เกี่ยวข้อง ไม่ต้องตอบทั้งหมดเพื่อทำงานเตรียม
PR #2 merged เป็น v0.1.0 แล้ว; merge แยกจากสิทธิ์ live. คำสั่ง sync เอกสารไม่เปิด scheduler ไม่อนุมัติซื้อของหรือเปลี่ยนเครือข่าย

### Tapo checklist จาก Claude advisory ล่าสุด — ยังไม่ใช่ผลทดลองอุปกรณ์

| รายการ | สิ่งที่แนะนำตรวจ | สถานะ |
| --- | --- | --- |
| Device Info | C545D / HW 1.0 / FW 1.1.7 ยืนยันแล้ว; endpoint เก็บในเครื่องเป็นส่วนตัว | Version CONFIRMED (OD-16); endpoint configured / offline validation PASS (OD-28); route NOT_TESTED |
| Advanced Settings / Camera Account | On ยืนยันจากภาพ Owner 2026-10-08; ไม่สร้าง/reset เป็นเงื่อนไขบังคับของทุก SD adapter | APP_STATUS_CONFIRMED; SD auth ยังไม่ทดสอบ |
| บัญชีเจ้าของ Tapo | readiness เท่านั้น; candidate SD downloader อาจใช้ cloud password ไม่ใช่รหัส Wi-Fi | รอ private input |
| Me / Third-Party Services / Third-Party Compatibility | On; แอป Version 3.21.106 จากภาพ Owner 2026-10-08 (OD-20) | APP_STATUS_CONFIRMED; ไม่เปลี่ยนค่า ไม่ใช่ SD auth/route PASS |
| Storage & Recording | คง event recording และคลิปเดิม ไม่ format SD/เปลี่ยน continuous เพื่อทดลองคลิปที่มี | ไม่ต้องเปลี่ยน |
| Playback & Download / SD | 2026-10-08 เริ่ม 09:51:53 / 03:00; Fixed + PT ตามภาพ Owner (OD-22) | UI_TARGET_CONFIRMED; metadata/timezone/channel mapping ยังไม่ยืนยัน |

คำแนะนำสรุปจาก brief และ Claude advisory ที่ได้รับจริง ไม่ได้ยืนยันว่าทุกเมนูมีบน firmware เครื่องนี้; ตรวจคู่มือ/release ก่อนใช้
แหล่งที่ใช้อ้างใน advisory: TP-Link FAQ 2790 (Camera Account), 4416 (Third-Party Compatibility), 2617 (SD Recording), README ของ JurajNyiri/pytapo. candidate 3.4.26 ตรวจ static/ติดตั้ง runtime แยกแล้ว OD-24 และทำ private IPv4-input/offline check แล้ว OD-25; ยังไม่ทดสอบกับ C545D จริง
ไม่มีการส่งรหัส token OTP IP รูปที่มีข้อมูลลับ หรือวิดีโอเข้า repo. การมอบหมายให้ Claude ต้องอ้าง STATUS/DECISIONS ล่าสุดตาม WORKFLOW
