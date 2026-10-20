# Remote SD Research — OD-37 (international developer sources)

BASELINE: `2eda445ef37fad2fd69082f8a59b8fc22fddb24d` · branch `claude/ft-d0-preflight`
สถานะงาน: เอกสารคำปรึกษาเท่านั้น ไม่มีการติดตั้ง/import/รัน upstream, Claude ไม่มี network/credential/กล้อง/วิดีโอ; PO ใช้เครือข่ายอ่านเฉพาะ public sources NOT_RUN_BY_DEVELOPER — ไม่ได้รัน unittest
แหล่งข้อมูล: PO ดาวน์โหลด 18 ไฟล์ source/doc สาธารณะไปตรวจแบบ static ใน temp folder ที่ฉันเข้าถึงไม่ได้; ที่นี่คือการประเมินอิสระของฉันต่อ **รายงานของ PO** ไม่ใช่ผลตรวจไฟล์เอง

## หลัก: แยกชั้นของหลักฐานเสมอ

1. **Author-reported** (ผู้พัฒนา repo รายงานเอง, OnTapo รายงาน TC65/C216; tapo-monitoring รายงาน C545D คนละเครื่อง ไม่ใช่ independent device verification ของเรา)
2. **PO static review** (PO อ่าน source ใน temp, ยังไม่รัน)
3. **ผลจริงของโปรเจกต์นี้กับ C545D**: **ไม่มี (none)** — ยังไม่มีการต่อกล้องจริงเลย

## ตารางสรุป candidate

| Candidate | ชั้นหลักฐาน | C545D ตรง? | สถานะ |
| --- | --- | --- | --- |
| OnTapo (relay SD, TC65) | Author-reported (3 commits, 0 stars, ใหม่) | ไม่ตรง, ไม่พิสูจน์ | CONDITIONAL research — เป้าหมายหลัก |
| tapo-monitoring (local API docs) | Author-reported C545D HW1.0/fw1.1.7 แต่คนละเครื่อง | ใกล้ที่สุดแต่ "primary maintainer, not our device" | ใช้เป็นข้อมูลอ้างอิง channel/lens, ไม่ใช่ relay/cloud |
| go2rtc tapo plugin | Author-reported, LAN livefeed | ไม่เกี่ยวกับ SD/cloud | excluded (ไม่ตอบโจทย์ home→shop) |
| C200 UART re, C260 RE | Author-reported, hardware/firmware/discovery research | คนละรุ่น + brick risk | excluded เด็ดขาด |
| tapo-cli / Tapo Care / emulator | เดิมจาก OD-36 | ไม่เปลี่ยน | ยังเป็น fallback รอง, ไม่ยกเลิก research แต่ priority ต่ำกว่า OnTapo ตาม OD-37 |

## OnTapo — จุดที่ใช้ได้และจุดเสี่ยงจาก PO static review

- `session.py`: login ครอบคลุมทุกกล้องในบัญชี ต้อง allowlist เฉพาะกล้องเป้าหมายเองที่ชั้น adapter; error path มี `resp.text` ดิบ ต้อง redact ก่อน log เสมอ; `camera.py` มี setter/motor อยู่ด้วย — ห้ามเชื่อว่า server จะปฏิเสธ setter เอง ต้อง guard ที่ขอบเขต request เหมือน OD-31/33
- `_http.py`: ใช้ `ssl.create_default_context` + CA ที่แถมมา ไม่ใช่ `verify=False` — ดีกว่า tapo-cli เดิม แต่ CA provenance/hostname ของ "aps1-cipc-api.i.tplinkcloud.com" ยังไม่ตรวจอิสระ
- `relay.py`/`stream.py`: ยืนยันว่ามี **cloud transit** ผ่าน vendor relay แม้ไม่ซื้อ Tapo Care (เก็บ storage); ไม่เท่ากับพิสูจน์ bit-exact SD export. เขียนไฟล์ด้วย `open(...,"wb")` ทับไฟล์เดิมได้ มี multipart cap 64 MiB ต่อ part และ playback hard cap แต่ไม่มี quota รวมของงาน; hard cap หรือ EOF เมื่อไม่มี PTS อาจคืน byte count ของคลิปที่ยังตรวจไม่ครบ ต้องมี overall deadline ครอบ connect/drain/cleanup ด้วย. `search_day` ใช้ `end_index=999999999` ต้องทำ bounded pagination เองแบบเดียวกับ pytapo wrapper เดิม
- channel `[0,1]` เป็นสมมติของ OnTapo เอง **ห้ามตีความเป็น Fixed/PT mapping** — ใช้ tapo-monitoring เป็นข้อมูลตั้งต้น (`getAllChnInfo`: chn1=Fixed, chn2=PT) แล้วต้องตรวจ mapping/ภาพของไฟล์จริงเมื่อถึงขั้น live
- Python>=3.11 + httpx>=0.27; isolated Python3.13.16 ที่ติดตั้งแล้วผ่าน minimum version ทางเอกสาร แต่ OnTapo/httpx ยังไม่ได้ install/import/test. ไม่ปะปนกับข้อกำหนด stdlib Python3.9 ของเครื่องมือ D0; ต้อง pin/audit dependency ที่จะใช้ใหม่

## tapo-monitoring (docs/tapo-local-api.md) — ข้อมูลอ้างอิง ไม่ใช่ relay

- เป็น **local API** (ผ่าน LAN ของกล้อง) ไม่ใช่ cloud relay จึงไม่แก้ปัญหา home→shop โดยตรง แต่ maintainer รายงานจาก C545D (HW1.0 EU fw1.1.7) ว่า `searchVideoOfDay` คืน 2 clips/event ไม่มี label เลนส์ และ `searchDetectionList` channel1=Wide, channel2=PT — **ห้ามสมมติว่า search channel = media stream channel**
- `total_num` อาจนับซ้ำต่อเลนส์ ไม่เท่าจำนวนคนเดินผ่าน — ต้องระวังเมื่อทำ counting
- plain getter บางตัว (`checkDetectEventState`, `getInfLampCapability`) ถูกรายงานว่าทำ HTTP API process restart/พอร์ต 443 หยุดตอบชั่วคราว ไม่ใช่หลักฐาน reboot ทั้งกล้อง — ห้าม probe getter เหล่านี้แม้เป็น read-only ตามชื่อ

## Dev design ที่เสนอ (ยังไม่ implement ในงานนี้)

1. **Audited library boundary**: เลือก bind เฉพาะ method ที่ตรวจแล้วแบบเดียวกับ `tools/ft_tapo_bridge.py` เดิม (OD-33) — ปรับ facade ให้รองรับ relay client แยกจาก pytapo ไม่ผสม stack
2. **Account/MFA input**: ยังต้องออกแบบช่องทาง private input ที่ Owner ใช้จาก iPhone ได้จริง. getpass บน Mac อย่างเดียวไม่ตอบข้อจำกัดนี้; ไม่รับ secret ใน chat/Issue ไม่ค้น Keychain/ไฟล์บ้าน ไม่ใช้ iCloud plaintext หรือเปิด web server. ขณะนี้ยังไม่มี credentials และยังไม่มีช่องทางที่พิสูจน์แล้ว
3. **เป้าหมายกล้องเดียว**: allowlist เฉพาะ C545D ของ Owner ที่บัญชีผูกไว้ แม้ login มองเห็นทุกกล้อง
4. **Readonly listing ช่วงสั้นก่อน**: bounded `search_day`/pagination เอง ไม่ใช้ `end_index` ใหญ่ของ upstream
5. **หนึ่งคลิป Fixed + ตรวจ completeness**: ตรวจ track/duration/EOF ไม่เชื่อ hardcap ว่าให้คลิปสมบูรณ์เสมอ ต้องมี fail-closed validation + atomic no-overwrite ก่อนรับว่า PASS
6. **Day batch → counting**: ทำเฉพาะหลังขั้น 5 ผ่านซ้ำ (idempotent) ตาม ONE_CLIP_PLAN เดิม ไม่ผสมยอดสองเลนส์

## UNKNOWN (ไม่ใช่สมมติว่าทำไม่ได้)

- OnTapo ทำงานกับ C545D จริงหรือไม่ (repo ใหม่ ไม่มีผู้ใช้ยืนยัน)
- Media relay ใช้ region aps1 คงที่ แม้ login มี region redirect; ยังไม่พิสูจน์บัญชี/ภูมิภาคจริง รวม CA provenance/host allowlist และคำสั่งที่ C545D cloud gateway รับ
- ความเข้ากันได้ของ dependencies บน Mac และ secure input จาก iPhone ยังไม่พิสูจน์
- search channel กับ media/download channel ของ OnTapo ตรงกับ mapping ของ tapo-monitoring หรือไม่

## Stop rule (finite)

1. ก่อนลอง OnTapo จริง: ต้องมี dependency audit ผ่าน + CA/hostname ตรวจแล้ว + guard ปฏิเสธ setter ผ่าน synthetic test (แบบ OD-32/33) ก่อนแตะกล้องจริง
2. ถ้า channel mapping ไม่ชัดหรือได้ PT แทน Fixed → หยุดที่ adapter ไม่เดาต่อ ไม่รวมยอด PT
3. ถ้าคลิปไม่สมบูรณ์ (ตัดกลาง/EOF ก่อนกำหนด) → หยุด ไม่ยอมรับเป็น ONE_CLIP_PASS
4. ข้อเสนอรอบจริงหลัง prerequisites พร้อม: กล้องเดียว ช่วงคลิปเดียว รายการไม่เกิน 2 หน้า x 10 รายการ, auth failure ไม่ retry, download retry 0, 1 GiB รวม/10 นาที/retention 24 ชั่วโมงนอก sync+git (ยังไม่อนุมัติ storage/live scope ในงานวิจัยนี้). ถ้า auth/region/relay/mapping/ความครบถ้วนไม่ผ่านให้หยุดพร้อม error ที่ redacted; กลับมาประเมิน manual SD หรือ Tapo Care ตาม blocker ไม่เปลี่ยนไปซื้อ/flash/ลองหลายบัญชีอัตโนมัติ

## คำตัดสิน

**CONDITIONAL GO** สำหรับ research/adapt OnTapo แบบแคบ (เฉพาะ SD listing/download path ที่ audit แล้ว) — เป็น research ขั้นถัดไปที่ priority สูงกว่า Tapo Care ตาม OD-37 ไม่ใช่การอนุมัติ live. **Production ยัง NO-GO** จนกว่าจะมีหลักฐาน C545D จริงผ่านทุก stop rule ข้างบน ข้อสรุป OD-36 ว่ายังไม่พบ candidate SD relay ถูกแทนด้วยหลักฐานนี้; router VPN ยัง UNKNOWN และพักเป็นทางหลัก ไม่มีอุปกรณ์จริงทำงานแล้วในทุกกรณี

## Developer summary

- งานที่ทำ: อ่าน PROJECT_CONTROL/FEASIBILITY_REVIEW/ONE_CLIP_PLAN และ evidence packet ของ PO เขียนบันทึกวิจัยใหม่
- ไฟล์ที่เปลี่ยน: `docs/REMOTE_SD_RESEARCH.md` เท่านั้น
- ผลทดสอบ: NOT_RUN_BY_DEVELOPER — ไม่มีการรันกล้อง/เครือข่าย/SDK จริง

## แหล่งที่ PO ตรวจและการตรวจรับ

- [OnTapo README / รายงาน TC65 และ C216](https://github.com/noriellecruz/ontapo/tree/a387f6abddb72f7e6eea72b374df5ad189da1f5f), [PyPI 0.1.0](https://pypi.org/project/ontapo/): เผยแพร่ 2026-08-27; repo มี 3 commits และยังไม่มี compatibility issue ตอนตรวจ. ไม่พบ C545D หรือ Mac live evidence
- [relay.py](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/src/ontapo/relay.py), [stream.py](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/src/ontapo/stream.py), [camera.py](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/src/ontapo/camera.py): PO static read ของ control/media path; ไม่ได้รัน upstream
- [MIT LICENSE](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/LICENSE) กับ [DISCLAIMER](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/DISCLAIMER.md): โครงการระบุ educational/research และไม่ตั้งใจให้ใช้ production/commercial. ไม่ตีความ MIT เป็น non-commercial license และไม่ถือ license เป็น vendor approval
- [C545D local API research](https://github.com/PeterkoCZ91/tapo-monitoring/blob/d36f0acb7fcc8923886783afaef71404f63c3b0a/docs/tapo-local-api.md): HW1.0 EU / fw1.1.7 Build260421 / pytapo3.4.18; เป็น local evidence ไม่ยืนยันเมื่อนำมารวมกับ OnTapo relay
- [go2rtc](https://github.com/AlexxIT/go2rtc/blob/master/internal/tapo/README.md), [Gladys](https://gladysassistant.com/docs/integrations/external/tapo/): ใช้ cloud บางส่วนได้แต่ภาพยังต้อง LAN; ไม่เลือกแทน SD relay. [C200 RE](https://github.com/nervous-inhuman/tplink-tapo-c200-re), [C260 TDPv2](https://spaceraccoon.dev/reverse-engineer-tapo-c260-tdp-v2/): ไม่ใช่หลักฐานดัดแปลง C545D ให้รับ SD จากบ้านได้
- Claude advisory COMPLETED_LOCAL, child exit0, 95.3s; PO แก้ข้อมูลหลัง handoff เรื่อง 64MiB part cap (packet เดิมคลาดเคลื่อน), Python, API process restart และ iPhone input. Camera/auth/SD requests0, clips0. PO regression แยกจาก NOT_RUN_BY_DEVELOPER อยู่ STATUS
