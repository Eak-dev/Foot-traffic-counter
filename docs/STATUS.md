# สถานะงาน

> ไฟล์นี้คือกระดานความคืบหน้าที่ทุกฝ่ายใช้ร่วมกัน ทำงานเสร็จแล้วติ๊กและเขียนบันทึกในคอมมิตเดียวกัน
> ห้ามใส่รหัสผ่าน, IP ภายนอกของร้าน, หมายเลขซีเรียล หรือข้อมูลส่วนบุคคลในไฟล์นี้
> คำอธิบายเกตและหลักฐานอยู่ที่ [PREPROJECT_PLAN.md](PREPROJECT_PLAN.md)

## เฟส (ตามแผนใหม่ Owner 2026-10-06)

- [ ] D0. เตรียมงาน: เอกสาร + `tools/ft_data.py` + unittest — Claude พัฒนา, PO ทดสอบแล้ว 52/52 และ regression แยก 7/7 ผ่าน — implementation พร้อม review; ยังรอ Owner merge ไม่ถือว่าจบเกต
- [ ] D1. เส้นทางที่ปลอดภัย + อินเทอร์เฟซอ่านอย่างเดียว + นโยบายพื้นที่ — Owner ให้ข้อมูล, PO ตรวจหลักฐาน; การตั้งค่าเส้นทางจริงเป็นขั้นแยกที่ได้รับอนุมัติเป็นรายครั้ง
- [ ] D2. ดึงคลิปเดียวแบบทำซ้ำได้ (แสดงรายการช่วงสั้น → ดึง 1 คลิป → ตรวจ)
- [ ] D3. ดึงรายวัน: resume, dedup (ไบต์เหมือนกัน), manifest, งบ, retry จำกัด
- [ ] D4. นับคนเดินผ่าน + ตัวกรองช่วงเวลา (ต้องมีข้อเสนอและอนุมัติแยก)
- [ ] D5. นำร่องและตั้งงานอัตโนมัติ (ต้องได้รับอนุมัติ Owner เป็นลายลักษณ์อักษร)

## ค่าที่ยืนยันแล้ว

| รายการ | ค่า | ยืนยันโดย |
| --- | --- | --- |
| เข้า shell ระยะไกลของ Mac ที่บ้าน | ผ่าน (macOS 14.8.9 x86_64) | PO |
| Python ของ Mac | 3.9.6 | PO |
| ฮาร์ดแวร์ Mac | 16 GiB RAM, 8 logical CPU | PO |
| Claude CLI บน Mac | 2.1.288 · **PASS** (smoke: READY, exit 0, is_error=false, modelUsage claude-sonnet-5) | PO |
| การตั้งค่าพลังงาน | idle sleep = 1 ทั้ง AC และ battery (อ่านอย่างเดียว ไม่ได้เปลี่ยน) | PO |
| การเปิดเครื่องทั้งคืน (active wake assertions) | UNKNOWN (ยังไม่ได้ตรวจ) | — |
| พื้นที่ว่างที่บ้าน (ค่าณ เวลาตรวจ) | ประมาณ 20.8 GiB | PO |
| ช่องทาง GitHub สำหรับงานนี้ | Connector สร้าง Issue #1 ได้; git push dry-run ผ่าน; gh auth ไม่ได้ตรวจและไม่จำเป็นต้องเปลี่ยน | PO |
| รุ่น/firmware กล้อง | UNKNOWN | — |
| รุ่นเราเตอร์ร้านและความสามารถ VPN | UNKNOWN | — |
| เส้นทางจาก Mac ที่บ้านไปเครือข่ายร้าน | UNKNOWN | — |
| การดึงคลิปอัตโนมัติจาก Mac ที่บ้าน | UNKNOWN (พิสูจน์ใน D2) | — |

## เรื่องที่รอตัดสินใจ

- [ ] รุ่นเราเตอร์ร้าน, ความสามารถ VPN, สรุป ISP routing — คุณ Eak
- [ ] รุ่น/firmware ของกล้องที่แน่นอน และยืนยันว่าเป็น C545D หรือไม่ — คุณ Eak
- [ ] ประเภทการเข้าถึงกล้องในเครื่องที่จะใช้ (ไม่ส่งรหัสผ่านในแชตหรือ Issue) — คุณ Eak + PO
- [ ] นโยบายเก็บรักษาและพื้นที่สำรอง (เกณฑ์เสนอ 10 GiB ยังไม่อนุมัติ) — คุณ Eak
- [ ] เพดานคลิป/ไบต์/ช่วงวันที่ — คุณ Eak (หลังมีตัวอย่างจริงจาก D2)
- [ ] ช่วงเวลาดึงที่ต้องการ — คุณ Eak (D5)
- [ ] ใช้ ffprobe เพื่อตรวจคลิปหรือไม่ — PO/คุณ Eak (ก่อน D2)
- [x] ใช้ทาง A: Owner อนุญาตรีโมต; ChatGPT เรียก Claude CLI บน Mac สำเร็จจริง ไม่ต้องรอ Actions
- [ ] เลือก release ของ candidate downloader (`pytapo`) และ runtime แยก (README ระบุ Python 3.13; ต้อง pin และตรวจก่อนติดตั้ง) — PO + คุณ Eak
- [ ] ยืนยันความหมายของเขตเวลาและแหล่ง timestamp ของดัชนีกล้อง — PO/คุณ Eak (D2)
- [ ] ตรวจ active wake assertions แบบอ่านอย่างเดียวเพื่อประเมินการเปิดเครื่องทั้งคืน — PO เมื่อคุณ Eak ต้องการ (ห้ามเปลี่ยนค่า)
- [ ] ยืนยันเกณฑ์ความแม่นยำ: baseline 80% (aggregate) ยังไม่บรรลุ ต้องมีชุดทดสอบ seated-person negatives และรายงาน FP/FN รายเหตุการณ์ — คุณ Eak + PO (D4)

## บันทึกล่าสุด (ใหม่สุดอยู่บน)

- 2026-10-06 · PO · ตรวจ source ที่ Claude แก้รอบ 2 และรันบน Mac จริง: compile PASS, unittest **52/52 PASS**, independent regression **7/7 PASS**. doctor: preparation PASS แต่ **live_ready=false**. หลักฐาน [FT_D0_EVIDENCE.md](FT_D0_EVIDENCE.md). แก้ WORKFLOW ให้ใช้คำสั่ง restricted file tools ที่ทดสอบจริง ไม่มี Bash/auto-checkout/resume ที่ขัดกับ control. งานพร้อม PR review; main และ Production ไม่ได้เปลี่ยน; Issue ยังเปิด.

- 2026-10-06 · Claude (dev) · FT-D0 รอบ 2 (ตามผล PO อิสระ): แก้ `tools/ft_data.py` ให้ปฏิเสธ root ที่เป็นลิงก์แม้เขียนแบบ `/.` หรือ `/`, ปฏิเสธ `..` ในเส้นทาง root, เปิดรายการย่อยแบบ anchored (`O_NOFOLLOW` จาก fd ของโฟลเดอร์แม่) และนับการสลับเป็นลิงก์เป็น `changed`; อ่านไฟล์แบบจำกัดไม่เกินขนาดตอนเปิด และตรวจ fstat/inode/ขนาด/mtime/ctime กับชื่อไฟล์ก่อนและหลังอ่าน; ทำให้ข้อความ argparse ไม่สะท้อนค่าที่ผู้ใช้พิมพ์ (รหัสคงที่ + `--json`); ปฏิเสธ NUL และอาร์กิวเมนต์ที่ไม่ใช่ข้อความ
- 2026-10-06 · Claude (dev) · FT-D0 รอบ 2: `tests/test_ft_data.py` เพิ่มเทสต์กรณี root `/.` การสลับโฟลเดอร์เป็นลิงก์ก่อนเปิด การเติบโต/การตัดทอน/การเปลี่ยน metadata/การแทนที่ entry ระหว่างอ่าน และการเทสต์ redaction; แก้ลำดับ cleanup ของเทสต์ `unreadable` โดยคืนสิทธิ์ก่อน tearDown (ไม่ข้ามเทสต์) — การทดสอบ **NOT_RUN_BY_DEVELOPER** รอ PO รันใหม่
- 2026-10-06 · PO · ผลรันรอบ 1 บน Mac (Python 3.9.6): 33 เคส — 32 ผ่าน, 1 ERROR (`test_unreadable_clip_marks_incomplete_without_raw_error` จากลำดับ cleanup, ไม่ใช่ความล้มเหลวด้านสิทธิ์) ยังไม่ถือว่า D0 ผ่าน
- 2026-10-06 · PO · ผล smoke Claude CLI: READY, exit 0, is_error=false, modelUsage claude-sonnet-5 → Claude runtime/auth เป็น PASS
- 2026-10-06 · Claude (dev) · FT-D0: เพิ่ม `docs/PREPROJECT_PLAN.md`, `tools/ft_data.py` (doctor/inventory), `tests/` (unittest) และปรับเอกสารให้ตรงกับ PROJECT_CONTROL · การทดสอบ **NOT_RUN_BY_DEVELOPER** รอ PO
- 2026-10-06 · Claude · เปลี่ยนวิธีทำงาน: คุณ Eak คุยกับ ChatGPT ที่เดียว ChatGPT วางแผนและสั่ง Claude CLI (ดู WORKFLOW.md)
- 2026-10-06 · Claude · ตั้ง repo: PLAN.md, AGENTS.md, STATUS.md และไฟล์ตั้งค่าตัวอย่าง (ฉบับ Raspberry Pi ถูกแทนที่แล้ว)
