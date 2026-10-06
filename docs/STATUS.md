# สถานะงานและจุดส่งต่อให้ Claude

> อัปเดต: 2026-10-07 03:53 +0700 · Issue #1 · PR #2 · branch `claude/ft-d0-preflight`
> อ่าน HEAD ของ branch/PR ที่ active ไม่ใช่ main ที่ยังไม่ได้ merge. สิทธิ์ยึด PROJECT_CONTROL และ Owner Decision
> [PLAN](PLAN.md) · [Roadmap](PREPROJECT_PLAN.md) · [Owner Decisions](DECISIONS.md) · [Workflow](WORKFLOW.md)

## สรุปปัจจุบัน

- **เฟส:** D0 implementation พร้อม review; PR #2 ยังเปิด/unmerged. เป้าหมายถัดไปที่ Owner สั่งคือทดลองดึงคลิป SD หนึ่งคลิป
- **ทีม:** PO รีโมต Mac/เรียก Claude/ตรวจงาน/push GitHub ได้แล้ว; ไม่ต้องสร้างระบบสั่ง AI ใหม่
- **โค้ดที่มีจริง:** `doctor` และ local `inventory` เท่านั้น; **ยังไม่มี downloader**
- **ผลฝั่งกล้อง:** `BLOCKED_BEFORE_CAMERA_REQUEST`; คำขอกล้อง 0, auth attempts 0, คลิปดาวน์โหลด 0 ตามหลักฐานล่าสุด — ไม่ใช่ทดสอบแล้วกล้องเชื่อมไม่ได้
- **Claude ล่าสุด:** ให้คำแนะนำข้อมูลที่ต้องใช้และ Tapo settings แล้ว เป็น advisory ไม่ใช่การตั้งค่า/ทดสอบจริง
- **ไม่มี scheduler/worker เปิดอยู่:** การอัปเดต docs ไม่ทำให้ Claude ทำงานต่อหลังจบแชตเอง
- **Owner instruction:** อัปเดตข้อสรุป/ความคืบหน้า/blockers ใน GitHub ระหว่างที่คุยกัน; ไม่คัดลอกบทสนทนาทั้งหมดหรือข้อมูลลับ

## ข้อมูลยืนยันแล้ว — ไม่ขอซ้ำ

| รายการ | ค่า / สถานะ | หลักฐาน |
| --- | --- | --- |
| กล้อง | Tapo C545D; camera Hardware/Firmware ยัง UNKNOWN | Owner; comment 6013505806 |
| เราเตอร์ | ZTE ZXHN F6107A; HW V9.0.09; FW F6107A_PON_4.1 | ภาพ Owner; comments 6013831335 / 6014086882 |
| อินเทอร์เน็ต | AIS Fibre 1000/200 Mbps; เป็นแพ็กเกจ Owner แจ้ง ไม่ใช่ speed test | Owner |
| บ้าน/ร้าน | คนละที่คนละ network แม้ Owner แจ้งอุปกรณ์ยี่ห้อ/แบบเดียวกัน | ไม่พิสูจน์ reachability |
| ต้นฉบับ | microSD, event clips ความยาวต่างกันและมีช่วงว่าง; มือถือที่ร้านดาวน์โหลดได้ | Owner |
| Mac/Claude | D0 ตรวจ macOS 14.8.9 x86_64 / Python 3.9.6; `claude-sonnet-5` รันจริงได้ | FT_D0_EVIDENCE / comment 6014447731 |
| พื้นที่/sleep | ผลตรวจเดิมราว 20.8 GiB และ idle sleep=1; ต้องตรวจใหม่ก่อนดึง/รันรายคืน | ไม่ใช่พื้นที่รับรองหรืออนุญาตเปลี่ยนค่า |

## อุปสรรคและผู้รับผิดชอบ

| ID | สิ่งที่ติด | ขั้นถัดไป / ผู้รับผิดชอบ |
| --- | --- | --- |
| B1 | Downloader ยังไม่เขียน | PO + Claude เลือก adapter/release และทำคำสั่งดึงหนึ่งคลิปตาม scope ทดลอง |
| B2 | ไม่พบ endpoint/บัญชีในไฟล์โปรเจกต์ที่ตรวจ ไม่ใช่ค้นทั้ง Mac | ทีมจัด private local input; Owner กรอกเฉพาะในเครื่อง ไม่ส่ง secret ในแชต/GitHub |
| B3 | เส้นทางบ้านไปกล้องร้าน NOT_TESTED | ทีมตรวจเป้าหมายที่ระบุจริง/ทางเข้าถึง ไม่เดา IP หรือสแกนอุปกรณ์อื่น |
| B4 | Camera firmware/auth/compatibility ยัง UNKNOWN | Owner ส่ง camera version และสถานะบัญชี; ทีมตรวจวิธีที่เลือก ไม่ถือ RTSP ผ่านว่า SD ผ่าน |
| B5 | ยังไม่มีคลิปเป้าหมายและเพดานทดลอง | Owner แจ้งวัน/เวลา/มุมหนึ่งคลิป; ทีมเสนอพื้นที่/bytes และตรวจไฟล์หลังดึง |

## รอจาก Owner และงานถัดไป

1. Hardware/Firmware **ของกล้อง**; ไม่ขอชื่อ C545D หรือ router version ซ้ำ
2. พบ IP กล้องแล้วหรือยัง; บัญชีเจ้าของ Tapo พร้อมหรือไม่; Camera Account และ Third-Party Compatibility อยู่สถานะใด — ขอเฉพาะสถานะ ไม่ขอค่าลับ/ไม่สั่งให้เปิดเอง
3. วัน/เวลาของหนึ่งคลิปที่ยังเปิดย้อนหลังได้ และมุม/เลนส์ถ้ามีหลายภาพ; ไม่ต้องส่งคลิปเดิมใหม่
4. **ทีมรับผิดชอบ:** private input, adapter, runtime, เส้นทาง, ตัวดาวน์โหลด, ขอบเขต/rollback และผลตรวจ. Owner สั่งให้ทดลองแล้ว ไม่วนขออนุมัติทั่วไปซ้ำหรือบังคับทดลอง 4G/5G/รูปเราเตอร์เพิ่ม
5. ก่อนแตะกล้อง PO บันทึก control ที่ระบุ target/สิทธิ์/bytes/rollback ตามคำสั่งทดลอง; ไม่ตีความรวมสิทธิ์ reset/เปิดพอร์ต/ติดตั้งทั่วเครื่อง/ซื้อ/merge/deploy/schedule. คำสั่ง sync รอบนี้เป็นเอกสารเท่านั้น
6. D3 ดึงรายวัน → D4 นับ/filters → D5 งานประจำ ยังไม่เริ่ม; แต่ละขั้นใช้เกณฑ์ใน PLAN/PREPROJECT ไม่ลดเกณฑ์เพื่อให้ผ่าน

## หลักฐานและการส่งต่อ

D0: [FT_D0_EVIDENCE.md](FT_D0_EVIDENCE.md) — 52 tests และ 7 independent checks ผ่านในรอบเดิม. Roadmap `9698f56` รัน 52 tests ซ้ำแล้ว. ไม่ใช่หลักฐานดึงกล้อง
[ผล inspection ล่าสุดที่เผยแพร่](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6014447731) · [Router version](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6014086882)
ก่อน Claude เริ่มงาน PO ต้องยืนยัน branch/commit ตรง GitHub; Claude อ่าน CONTROL/AGENTS/PLAN/STATUS/DECISIONS และสรุป phase/blockers/next action ก่อนลงมือ. ถ้าไม่มี network tools PO ส่งบริบทที่ตรวจแล้วให้

## บันทึกล่าสุด (ใหม่สุดอยู่บน)

- 2026-10-07 · PO validation · รอบ sync เอกสารนี้: UTF-8/Markdown fences/local links/diff check ผ่าน, ตรวจ patterns ข้อมูลลับไม่พบในเอกสารที่แก้, code/tests/PROJECT_CONTROL ไม่เปลี่ยน. รัน unittest เดิมซ้ำ **52/52 PASS**; 7 independent checks เป็นหลักฐานรอบ D0 ไม่ได้รันใหม่. ไม่อ้างการตรวจ patterns เป็น full security audit

- 2026-10-07 03:53 +0700 · PO · Owner สั่ง sync GitHub ระหว่างสนทนา: รวมข้อมูลอุปกรณ์/ผล Claude advisory/อุปสรรคที่เคยอยู่ใน PR comments ลงสถานะกลาง เพิ่ม DECISIONS และกติกาอ่านก่อนเริ่มงาน. รอบนี้เอกสารเท่านั้น ไม่เรียก Claude ใหม่ ไม่เปลี่ยนโค้ดหรือ control ไม่แตะกล้อง/บัญชี/เครือข่าย/main. ตรวจ publish/read-back ก่อนสรุป; ประวัติผล tests ด้านล่างไม่ใช่การทดสอบกล้องใหม่

### ประวัติก่อน sync รอบนี้ (ไม่ใช่สถานะปัจจุบัน)
- 2026-10-06 · PO · ตามคำขอ Owner เพิ่ม Execution Roadmap และ Checklist O1–O10 ใน PREPROJECT_PLAN §12–13: งานที่ส่งตอนนี้/ก่อนทดลอง/ภายหลัง เจ้าของงาน blockers และเกณฑ์รับงาน. แก้เฉพาะ docs/PLAN.md, docs/PREPROJECT_PLAN.md และ docs/STATUS.md ใน PR #2; ไม่เปลี่ยน code/control ไม่เรียก Claude ใหม่. รันชุดทดสอบเดิมซ้ำ 52/52 ผ่าน; regression 7/7 เป็นหลักฐานเดิมไม่ได้รันใหม่รอบเอกสารนี้. ยังอยู่ D0 review; ไม่มีสิทธิ์ใหม่สำหรับกล้อง เครือข่าย การติดตั้ง scheduler หรือ merge. เป้าหมายถัดไปคือเลือกช่องทางรับข้อมูลแล้วทดลองดึงหนึ่งคลิปจริงตามเกต.

- 2026-10-06 · PO · ตรวจ source ที่ Claude แก้รอบ 2 และรันบน Mac จริง: compile PASS, unittest **52/52 PASS**, independent regression **7/7 PASS**. doctor: preparation PASS แต่ **live_ready=false**. หลักฐาน [FT_D0_EVIDENCE.md](FT_D0_EVIDENCE.md). แก้ WORKFLOW ให้ใช้คำสั่ง restricted file tools ที่ทดสอบจริง ไม่มี Bash/auto-checkout/resume ที่ขัดกับ control. งานพร้อม PR review; main และ Production ไม่ได้เปลี่ยน; Issue ยังเปิด.

- 2026-10-06 · Claude (dev) · FT-D0 รอบ 2 (ตามผล PO อิสระ): แก้ `tools/ft_data.py` ให้ปฏิเสธ root ที่เป็นลิงก์แม้เขียนแบบ `/.` หรือ `/`, ปฏิเสธ `..` ในเส้นทาง root, เปิดรายการย่อยแบบ anchored (`O_NOFOLLOW` จาก fd ของโฟลเดอร์แม่) และนับการสลับเป็นลิงก์เป็น `changed`; อ่านไฟล์แบบจำกัดไม่เกินขนาดตอนเปิด และตรวจ fstat/inode/ขนาด/mtime/ctime กับชื่อไฟล์ก่อนและหลังอ่าน; ทำให้ข้อความ argparse ไม่สะท้อนค่าที่ผู้ใช้พิมพ์ (รหัสคงที่ + `--json`); ปฏิเสธ NUL และอาร์กิวเมนต์ที่ไม่ใช่ข้อความ
- 2026-10-06 · Claude (dev) · FT-D0 รอบ 2: `tests/test_ft_data.py` เพิ่มเทสต์กรณี root `/.` การสลับโฟลเดอร์เป็นลิงก์ก่อนเปิด การเติบโต/การตัดทอน/การเปลี่ยน metadata/การแทนที่ entry ระหว่างอ่าน และการเทสต์ redaction; แก้ลำดับ cleanup ของเทสต์ `unreadable` โดยคืนสิทธิ์ก่อน tearDown (ไม่ข้ามเทสต์) — การทดสอบ **NOT_RUN_BY_DEVELOPER** รอ PO รันใหม่
- 2026-10-06 · PO · ผลรันรอบ 1 บน Mac (Python 3.9.6): 33 เคส — 32 ผ่าน, 1 ERROR (`test_unreadable_clip_marks_incomplete_without_raw_error` จากลำดับ cleanup, ไม่ใช่ความล้มเหลวด้านสิทธิ์) ยังไม่ถือว่า D0 ผ่าน
- 2026-10-06 · PO · ผล smoke Claude CLI: READY, exit 0, is_error=false, modelUsage claude-sonnet-5 → Claude runtime/auth เป็น PASS
- 2026-10-06 · Claude (dev) · FT-D0: เพิ่ม `docs/PREPROJECT_PLAN.md`, `tools/ft_data.py` (doctor/inventory), `tests/` (unittest) และปรับเอกสารให้ตรงกับ PROJECT_CONTROL · การทดสอบ **NOT_RUN_BY_DEVELOPER** รอ PO
- 2026-10-06 · Claude · เปลี่ยนวิธีทำงาน: คุณ Eak คุยกับ ChatGPT ที่เดียว ChatGPT วางแผนและสั่ง Claude CLI (ดู WORKFLOW.md)
- 2026-10-06 · Claude · ตั้ง repo: PLAN.md, AGENTS.md, STATUS.md และไฟล์ตั้งค่าตัวอย่าง (ฉบับ Raspberry Pi ถูกแทนที่แล้ว)
