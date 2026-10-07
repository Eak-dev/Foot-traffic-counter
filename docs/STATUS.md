# สถานะงานและจุดส่งต่อให้ Claude

> อัปเดต: 2026-10-07 · Owner ยืนยันยอดทั้งวันและ camera version; LOCAL_ONLY · Issue #1 · PR #2 · branch `claude/ft-d0-preflight`
> Local checkout/HEAD/งานค้างเป็นสถานะปัจจุบัน; remote อาจตามหลังจนถึง checkpoint. สิทธิ์ยึด PROJECT_CONTROL และ Owner Decision
> [PLAN](PLAN.md) · [Roadmap](PREPROJECT_PLAN.md) · [Owner Decisions](DECISIONS.md) · [Workflow](WORKFLOW.md)

## สรุปปัจจุบัน

- **เฟส:** D0 ผ่าน review และ merge ตามคำสั่ง Owner แล้ว; PR #2 MERGED, เวอร์ชันแรก `v0.1.0` ที่ `b05b8fb6821fdaf645db2217ed9ea8c45ba21363`. ยังไม่ผ่านเกตอุปกรณ์ D1–D5. เป้าหมายถัดไปที่ Owner สั่งคือทดลองดึงคลิป SD หนึ่งคลิป
- **ทีม:** Codex และ Claude ใช้ local checkout/branch งานเดียวกันตาม OD-12/13; หนึ่ง writer ต่อครั้ง. พาธจริงอยู่ใน ignored local config; สำเนาเก่า dormant
- **โค้ดที่มีจริง:** `doctor`, local `inventory` และตัวเรียก local Claude `tools/claude_dev.py` ที่ตรวจรับแล้ว; **ยังไม่มี downloader**
- **ผลฝั่งกล้อง:** `BLOCKED_BEFORE_CAMERA_REQUEST`; คำขอกล้อง 0, auth attempts 0, คลิปดาวน์โหลด 0 ตามหลักฐานล่าสุด — ไม่ใช่ทดสอบแล้วกล้องเชื่อมไม่ได้
- **Claude ล่าสุด:** สร้าง launcher/synthetic tests, PO ตรวจแก้และเพิ่ม tripwire กัน unit tests เรียก Claude จริง. ทดสอบ handoff ผ่าน launcher จริงแบบ read/test-only สำเร็จ: COMPLETED_LOCAL, child exit 0, ไม่มี permission denial, ไม่แก้ไฟล์/HEAD/branch และ Claude รายงาน unittest 113/113 PASS. PO รันอิสระ 113/113 PASS. คำแนะนำ Tapo ก่อนหน้ายังเป็น advisory ไม่ใช่ผลกล้อง
- **ไม่มี scheduler/worker เปิดอยู่:** การอัปเดต docs ไม่ทำให้ Claude ทำงานต่อหลังจบแชตเอง
- **Owner instruction:** พัฒนาและอัปเดตสถานะใน local เป็นหลัก; push เมื่อ reviewable/ข้อสรุปหรือ blocker สำคัญ/handoff ที่ต้องใช้ remote/Owner สั่ง. ไม่ sync ทุกข้อความ (supersedes OD-11 cadence); ไม่เผยแพร่ raw transcripts/ข้อมูลลับ

## ข้อมูลยืนยันแล้ว — ไม่ขอซ้ำ

| รายการ | ค่า / สถานะ | หลักฐาน |
| --- | --- | --- |
| กล้อง | Tapo C545D; Hardware 1.0; Firmware 1.1.7 | ภาพ Device Info จาก Owner 2026-10-07; OD-16 |
| เราเตอร์ | ZTE ZXHN F6107A; HW V9.0.09; FW F6107A_PON_4.1 | ภาพ Owner; comments 6013831335 / 6014086882 |
| อินเทอร์เน็ต | AIS Fibre 1000/200 Mbps; เป็นแพ็กเกจ Owner แจ้ง ไม่ใช่ speed test | Owner |
| บ้าน/ร้าน | คนละที่คนละ network แม้ Owner แจ้งอุปกรณ์ยี่ห้อ/แบบเดียวกัน | ไม่พิสูจน์ reachability |
| ต้นฉบับ | microSD; กล้องบันทึกเฉพาะมีคนเดินผ่าน มีช่วงว่างตามเงื่อนไขนี้; รวมยอดคลิปเป็นยอดทั้งวันได้; มือถือที่ร้านดาวน์โหลดได้ | Owner ยืนยัน 2026-10-07; OD-15 |
| Mac/Claude | D0 ตรวจ macOS 14.8.9 x86_64 / Python 3.9.6; `claude-sonnet-5` รันจริงได้ | FT_D0_EVIDENCE / comment 6014447731 |
| พื้นที่/sleep | ผลตรวจเดิมราว 20.8 GiB และ idle sleep=1; ต้องตรวจใหม่ก่อนดึง/รันรายคืน | ไม่ใช่พื้นที่รับรองหรืออนุญาตเปลี่ยนค่า |

## อุปสรรคและผู้รับผิดชอบ

| ID | สิ่งที่ติด | ขั้นถัดไป / ผู้รับผิดชอบ |
| --- | --- | --- |
| B1 | Downloader ยังไม่เขียน | PO + Claude เลือก adapter/release และทำคำสั่งดึงหนึ่งคลิปตาม scope ทดลอง |
| B2 | ไม่พบ endpoint/บัญชีในไฟล์โปรเจกต์ที่ตรวจ ไม่ใช่ค้นทั้ง Mac | ทีมจัด private local input; Owner กรอกเฉพาะในเครื่อง ไม่ส่ง secret ในแชต/GitHub |
| B3 | เส้นทางบ้านไปกล้องร้าน NOT_TESTED | ทีมตรวจเป้าหมายที่ระบุจริง/ทางเข้าถึง ไม่เดา IP หรือสแกนอุปกรณ์อื่น |
| B4 | Auth/adapter compatibility ยัง UNKNOWN; camera version ยืนยันแล้ว | ทีมตรวจวิธีที่เลือกกับ C545D HW 1.0 / FW 1.1.7; Owner แจ้งเฉพาะสถานะบัญชี/เมนูที่ยังขาด ไม่ขอเวอร์ชันซ้ำ |
| B5 | ยังไม่มีคลิปเป้าหมายและเพดานทดลอง | Owner แจ้งวัน/เวลา/มุมหนึ่งคลิป; ทีมเสนอพื้นที่/bytes และตรวจไฟล์หลังดึง |

## รอจาก Owner และงานถัดไป

ยืนยันแล้ว: C545D / Hardware 1.0 / Firmware 1.1.7; ไม่ขอข้อมูลนี้หรือ router version ซ้ำ

1. พบ IP กล้องแล้วหรือยัง; บัญชีเจ้าของ Tapo พร้อมหรือไม่; Camera Account และ Third-Party Compatibility อยู่สถานะใด — ขอเฉพาะสถานะ ไม่ขอค่าลับ/ไม่สั่งให้เปิดเอง
2. วัน/เวลาของหนึ่งคลิปที่ยังเปิดย้อนหลังได้ และมุม/เลนส์ถ้ามีหลายภาพ; ไม่ต้องส่งคลิปเดิมใหม่
3. **ทีมรับผิดชอบ:** private input, adapter, runtime, เส้นทาง, ตัวดาวน์โหลด, ขอบเขต/rollback และผลตรวจ. Owner สั่งให้ทดลองแล้ว ไม่วนขออนุมัติทั่วไปซ้ำหรือบังคับทดลอง 4G/5G/รูปเราเตอร์เพิ่ม
4. ก่อนแตะกล้อง PO บันทึก control ที่ระบุ target/สิทธิ์/bytes/rollback ตามคำสั่งทดลอง; ไม่ตีความรวมสิทธิ์ reset/เปิดพอร์ต/ติดตั้งทั่วเครื่อง/ซื้อ/merge/deploy/schedule. คำสั่ง sync รอบนี้เป็นเอกสารเท่านั้น
5. D3 ดึงรายวัน → D4 นับ/filters → D5 งานประจำ ยังไม่เริ่ม; แต่ละขั้นใช้เกณฑ์ใน PLAN/PREPROJECT ไม่ลดเกณฑ์เพื่อให้ผ่าน

## หลักฐานและการส่งต่อ

D0: [FT_D0_EVIDENCE.md](FT_D0_EVIDENCE.md) — 52 tests และ 7 independent checks ผ่านในรอบเดิม. Roadmap `9698f56` รัน 52 tests ซ้ำแล้ว. ไม่ใช่หลักฐานดึงกล้อง
[ผล inspection ล่าสุดที่เผยแพร่](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6014447731) · [Router version](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6014086882)
ก่อน Claude เริ่มงาน PO ยืนยัน canonical local root/branch/full HEAD และงานค้างที่รับทราบ; ไม่บังคับให้ตรง remote ระหว่างพัฒนา. Claude อ่าน CONTROL/AGENTS/PLAN/STATUS/DECISIONS และสรุป phase/blockers/next action. หลัง publish checkpoint จึงตรวจ branch/PR head ที่ remote

## Local handoff ปัจจุบัน

- Branch: `claude/ft-d0-preflight` เดิม; baseline เวอร์ชันแรก `b05b8fb6821fdaf645db2217ed9ea8c45ba21363` (`v0.1.0`). PO นำผล merge มาใน local ด้วย fast-forward เท่านั้น; config/root เดิม.
- Writer: NONE หลังส่งมอบ; Codex เป็นผู้จัด checkpoint และส่งงานถัดไป. ไม่มี delegated process ถือ tree
- Checkpoint: PR #2 MERGED และ `v0.1.0` เผยแพร่แล้ว ตรวจ GitHub read-back; บันทึกสถานะหลัง merge รอบนี้เป็น LOCAL_ONLY เพื่อรวมใน checkpoint/PR ถัดไป ไม่แก้ main ตรงและไม่สร้าง PR ซ้ำเพื่อบันทึกอย่างเดียว. ผลอ่านกลับและ local HEAD อยู่ใน ignored `.claude/delivery.local.json`.
- Final validation: PO รัน **113/113 unittest PASS**, exit 0 (52 เดิม + 61 launcher/regression); Claude read/test-only ผ่าน launcher รายงาน 113/113 PASS, exit 0. ตรวจ diff/เอกสาร/ขอบเขตก่อน checkpoint; หลักฐาน D0 7 independent checks เป็นประวัติ ไม่ได้รันซ้ำรอบนี้
- Next action: ใช้ local workflow นี้ส่งงาน Dev ย่อยถัดไปตาม acquisition-first plan. Downloader/route/auth/adapter compatibility/clip target ยังเป็น B1–B5; camera version ยืนยันแล้ว; workflow สำเร็จไม่เปิดเกตกล้อง

## บันทึกล่าสุด (ใหม่สุดอยู่บน)

- 2026-10-07 · Owner/PO · OD-15: Owner ยืนยันกล้องบันทึกเฉพาะคนเดินผ่าน จึงรวมคลิปเป็นยอดนับทั้งวันได้; แก้ข้อจำกัดเดิมใน CONTROL/PLAN/PREPROJECT/README. OD-16: อ่านภาพ Device Info ได้ C545D, Hardware 1.0, Firmware 1.1.7; ปิดส่วน version ของ B4 แต่ auth/compatibility ยังไม่ตรวจ. บันทึกเฉพาะข้อความใน local ไม่เก็บภาพ ไม่แตะกล้อง; เกณฑ์ดึงครบ/ความแม่นยำยังอยู่ และไม่อ้าง live PASS. รอบเอกสารนี้ PO รัน unittest 113/113 PASS, exit 0; code/tests ไม่เปลี่ยน, ไม่เรียก Claude รอบใหม่.

- 2026-10-07 · Owner/PO · Owner สั่ง “Merge ก่อนแล้วค่อยทำต่อ เพื่อเป็น version แรก”: merge PR #2 ที่ reviewed head `dc4cf0f`, อ่านกลับยืนยัน merge commit `b05b8fb` และ tag `v0.1.0`. Local branch เดิม fast-forward มาที่ baseline; ตรวจ file tree ตรงกับชุดที่ผ่าน 113 tests จึงไม่ได้รันชุดเดิมซ้ำ. บันทึกหลัง merge เป็น local-only; ไม่ปิด Issue ไม่ deploy ไม่แตะกล้อง และไม่เปิดเกต D1–D5.

- 2026-10-07 · Codex validation · workflow รอบนี้พร้อมส่งมอบ: unittest อิสระ 113/113 PASS (exit 0); handoff ผ่าน launcher จริง COMPLETED_LOCAL/child exit 0 และ Claude รายงาน 113 tests PASS. ไม่เปลี่ยน ft_data/52 tests เดิม/หลักฐาน D0; ไม่มี camera/production/main/merge/deploy. Runtime prompts/results/config ไม่ขึ้น Git.
- 2026-10-07 · PO review fixes · ตรวจพบ test mock แบบเก่าไม่ครอบคลุม Popen ในรอบแก้ของ Claude จึงหยุด delegated process tree และเก็บไฟล์ไว้; ไม่รับ invocation นั้นเป็น PASS. Refactor mock พร้อม tripwire ห้าม real Claude ใน unit tests, ปิด background tasks, รักษา lock เมื่อ timeout/interrupt เพื่อให้ PO audit descendants; harden scope/config/result/policy/error redaction แล้วตรวจ 113 tests สำเร็จ.

- 2026-10-07 · Codex/Owner · เปลี่ยน workflow เป็น local checkout/branch เดียวตาม OD-12/13. PO อัปเดต control/policy, Claude เขียน launcher/tests; invocation รอบแรกถูก interrupt และไม่รับเป็น PASS. PO ทดสอบ initial 86/86 ผ่าน แต่ยังมี review fixes. กล้อง/production/main ไม่เปลี่ยน; local changes รอ final validation/checkpoint.


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
