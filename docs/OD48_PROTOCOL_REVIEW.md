# OD-48 Protocol Review — Download Frame Over PLAYBACK(1) Relay (final)

Status: OFFLINE FINAL ADVISORY. NOT_RUN_BY_DEVELOPER (PO ran all tests). No
code/tests/network/runtime/private config/Keychain/media/Git access in this
revision.

## Outcome supersedes the prior "NOT JUSTIFIED AS FRAMED" verdict
PO ran the bounded experiment the prior advisory called unproven: unchanged
`streamType:1` relay negotiation plus the exact already-tested native
`download_frame` (channels[0], media_type0, raw start/end, player_id) on the
16s Fixed-candidate interval. Result: HTTP transfer succeeded, 5,218,504
bytes, two H.264 tracks 2304x1296, index0/index2, duration 15.867s — not the
0-byte terminal-notification ending seen on the 16s/50s playback-mode trials.
PO visually confirmed index0 carries the Fixed-Lens overlay and matching
wide shop view (index2 is PT). Offline `ffmpeg` stream-copy of index0 only
(no audio) produced a 2,449,973-byte MP4, 240 frames, 15.866667s; an initial
null-muxer check warned about output timebase only, and the corrected
verification (fps_mode passthrough, enc_time_base demux) decoded the full
file exit0 with no stderr — a verification-method fix, not a repair of
camera data. First/end frames were checked before the diagnostic JPEGs were
removed.

This settles compatibility for this one sample: a cloud-negotiated
`streamType:1` relay does accept the native download-frame method, resolving
the previous uncertainty about this pairing for the tested sample. The earlier lack-of-proof concern was reasonable before this
run; it no longer describes the current evidence and should not be kept as
the live advisory.

## Corrections to the prior text
- **Dead-code claim was wrong.** `_stream(mode="download")` is a tested,
  reachable branch, not dead code; only production default selection was
  (and remains) held back from automatic use.
- **Motor-status handling was wrong.** `channel_motor_status` is a
  spontaneous device notification, not a motor command and not a failure;
  it must not trigger an abort by itself.

## Still open (do not claim beyond this)
- Only one 16s interval and one connection succeeded — no evidence yet for
  longer clips, other durations, or other intervals/firmware.
- No ACK/completion semantics have been defined for a batch of clips, nor a
  retry/backoff policy for a failed one.
- Nothing establishes unattended, scheduled, or multi-day retrieval; the two
  retained artifacts are private, outside git, and expire after24h with cleanup on the next enabled invocation; actual
  deletion can occur later because there is no background worker.
- Full-day completeness and footfall counting remain untested.

## สรุปสั้นเป็นไทย
ผลทดลองจริงของ PO ยืนยันว่าชุด native download frame เดิมใช้งานได้บน relay
streamType1 ที่เจรจาไว้แล้ว ได้ไฟล์ Fixed Lens จริงหนึ่งคลิป (16 วินาที,
ตรวจภาพแรก/ท้ายและ decode ทั้งไฟล์ผ่าน) คำแนะนำเดิมที่ว่า "ยังไม่มีหลักฐาน
รองรับคู่นี้" ถูกแทนที่ด้วยหลักฐานจริงแล้วสำหรับตัวอย่างนี้ ไม่ใช่ข้อพิสูจน์ว่า
ทุกช่วงคลิป/ทุก firmware ใช้ได้ และยังไม่มีระบบรับ-ยืนยันครบ batch, การนับคน
หรือการเก็บรักษาไฟล์แบบไม่มีคนดูแลประจำ
