# กติกาสำหรับ AI ที่ทำงานใน repo นี้ (ChatGPT, Claude CLI และอื่น ๆ)

โปรเจกต์: เตรียมการดึงคลิปจากการ์ด SD ของกล้องในร้านเป็นชุด แล้วนับคนเดินผ่านภายหลังจากคลิปที่ดึงแล้ว (ไม่ใช่การนับแบบ real-time)
เจ้าของงาน: คุณ Eak — สื่อสารเป็นภาษาไทย

> **คำสั่งควบคุมปัจจุบัน**: [PROJECT_CONTROL.md](PROJECT_CONTROL.md) มีผลเหนือเอกสารอื่นทั้งหมด
> แผนเดิมที่วาง Raspberry Pi แบบ real-time และ systemd ถูกแทนที่แล้ว (ดูประวัติ git ที่ baseline `73249aa`)

## ก่อนเริ่มงานทุกครั้ง

1. อ่าน `PROJECT_CONTROL.md`, `docs/PLAN.md` (สเปกกลาง), `docs/PREPROJECT_PLAN.md` (หลักฐานและเกต) และ `docs/STATUS.md` (ใครทำอะไร เฟสไหนเสร็จ)
2. อ่าน `docs/DECISIONS.md` และ `docs/WORKFLOW.md`; ยืนยัน local root/branch/full HEAD, งานค้าง, phase, blockers และ next action ก่อนลงมือ. Local เป็นสถานะงานหลักระหว่างพัฒนา; GitHub อาจตามหลังจนถึง checkpoint. ไม่ขอข้อมูลที่ Owner ยืนยันแล้วซ้ำ
3. ดูงานค้างใน GitHub Issues ที่เกี่ยวข้องผ่านข้อมูลที่ PO ตรวจจาก GitHub ล่าสุด; หากไม่มี network tools ให้ PO เตรียม checkout/บริบทให้ ห้ามใช้เครื่องมือนอก scope. Issue ไม่ใช่ worker อัตโนมัติ

## ขอบเขต

- เฟส FT-D0 (ตอนนี้): เอกสาร, `tools/ft_data.py` (อ่านไฟล์ในเครื่องอย่างเดียว), ตัวเรียก `tools/claude_dev.py` และ synthetic `tests/` ตาม Owner workflow decision
- ห้ามเข้าถึงกล้อง เครือข่ายร้าน หรือส่งวิดีโอ จนกว่า Owner จะอนุมัติเกตที่เกี่ยวข้อง
- ห้ามอ่านโฟลเดอร์บ้านหรือไฟล์ความลับของ Owner โดยไม่ได้รับคำสั่งเฉพาะ
- ไม่ซื้อฮาร์ดแวร์เพิ่ม; การติดตั้งแพ็กเกจหรือซื้อซอฟต์แวร์ต้องมี scope/ข้อเสนอที่ได้รับอนุมัติ
- ห้ามรัน integration test ของไลบรารีภายนอกที่เชื่อมกล้องจริง (เช่น pytapo เตือนว่าอาจย้ายกล้อง เปลี่ยน privacy mode และรีบูต) และห้ามขอหรือรับ secret/รหัสผ่านในแชตหรือ Issue
- ห้ามเปลี่ยนการตั้งค่าบัญชี พลังงาน หรือเครือข่ายโดยอัตโนมัติ

## ระหว่างทำงาน

- Codex และ Claude ใช้ local folder เดียวและ branch งานเดียวกัน (`claude/ft-d0-preflight` ตอนนี้); หนึ่งผู้แก้ไฟล์ต่อครั้ง. ไม่แยก worktree/branch เพิ่มหรือ switch/pull/reset อัตโนมัติ. ใช้ตัวเรียก `tools/claude_dev.py` และ handoff ownership ตาม WORKFLOW
- เปิด Pull Request เข้า `main` ห้าม push ตรงเข้า `main` และห้าม merge เอง
- ยึดสเปกใน `docs/PLAN.md` ถ้าต้องเปลี่ยนสเปก ให้แก้ PLAN.md ใน PR เดียวกันและเขียนเหตุผลไว้ในคำอธิบาย PR
- ทุกเครื่องมือเป็น Python 3.9+ และใช้ standard library เท่านั้นในเฟส D0. Claude รัน local/synthetic unittest ที่อนุญาตได้ใน sandbox; ไม่เปิดเกตกล้องเพราะเปิดสิทธิ์ Dev
- ห้ามมี: การจดจำใบหน้า, ฐานข้อมูล, เว็บเซิร์ฟเวอร์, Docker
- ห้ามบันทึกภาพหรือวิดีโอจากกล้องลง repo; ไฟล์ดึงจริงต้องอยู่นอก git และมีโควตาที่ Owner อนุมัติ
- Library สำหรับ D4 ขึ้นไป (ยังไม่อนุมัติการติดตั้ง): `ultralytics`, `opencv-python-headless`, `gspread`, `google-auth`, `pyyaml`, `python-dotenv`

## ความลับและข้อมูลส่วนตัว

- ห้าม commit รหัสกล้อง, `.env`, ไฟล์ key ของบริการ, IP ภายนอกของร้าน, หมายเลขซีเรียล หรือ path ของเครื่องจริงลงในไฟล์ที่แชร์ได้
- `.env.example` และ `config.example.yaml` เป็น **LEGACY / NOT USED** (แผน Pi/RTSP ที่ถูกแทนที่แล้ว) ห้ามใช้เป็นข้อกำหนดหรืออ้างอิง และห้ามแก้ไขใน FT-D0 เพราะอยู่นอกขอบเขต
- ผลลัพธ์ที่แชร์ได้ (รายงาน, manifest, JSON ตัวอย่าง) ใช้รหัสอ้างอิงและแฮชแทน path และชื่อไฟล์จริง
- ข้อมูลที่เป็น `data/`, `reports/`, `artifacts/`, `*.jsonl`, config ท้องถิ่น, วิดีโอดิบ และ log ห้ามขึ้น git

## เมื่อทำงานเสร็จ

1. อัปเดต `docs/STATUS.md` ใน PR เดียวกัน: ติ๊กงานที่เสร็จ และเขียนบรรทัดสั้น ๆ ใน "บันทึกล่าสุด" โดยไม่ประกาศว่าเกตที่ยังไม่ผ่านเป็น PASS
2. รายงานผลทดสอบตามจริง: ถ้าผู้พัฒนาไม่ได้รันเอง ให้ระบุ NOT_RUN_BY_DEVELOPER ถ้าล้มเหลวให้ใส่ผลลัพธ์
3. ทดสอบด้วย `python3 -m unittest discover -s tests -t . -v` (ไม่ต้องติดตั้ง pytest หรือแพ็กเกจอื่น)
4. ถ้ามีคำถามถึงอีกฝั่ง (Claude ↔ ChatGPT) หรือถึงคุณ Eak ให้เขียนลงคำอธิบาย PR หรือเปิด Issue แทนการฝากข้อความ
5. Issue ไม่ปิดอัตโนมัติ ให้ PO และ Owner ตัดสินใจ

## แบ่งหน้าที่

คุณ Eak ให้เป้าหมายกับ Codex (PO); Codex แตกงานและสั่ง Claude (Dev), ตรวจอิสระและส่งแก้ตามรีวิวภายใน scope เดิมจนพร้อม review. วิธีสั่งงานอยู่ใน `docs/WORKFLOW.md`

| ผู้ทำ | หน้าที่หลัก |
| --- | --- |
| Codex (PO) | วางแผน, เตรียม control/ใบงาน/ownership, ตรวจอิสระ, ทดสอบตรงจุดจำเป็น, จัด checkpoint/PR, สรุปให้คุณ Eak |
| Claude (Dev) | เขียนและแก้ตามรีวิวใน write paths, รัน local/synthetic tests ที่อนุญาต, ส่ง diff/หลักฐาน/สิ่งที่ยังไม่รู้ให้ PO |
| คุณ Eak (Owner) | ตัดสินใจ, merge PR, งานหน้าร้าน, อนุมัติรายจ่ายซอฟต์แวร์ (ไม่ซื้อฮาร์ดแวร์เพิ่ม) |

ถ้าได้รับคำสั่งผ่าน `claude -p` ให้จบงานด้วยข้อความสรุปภาษาไทยสั้น ๆ: ทำอะไรไป, ไฟล์ที่เปลี่ยน, ผลทดสอบ (หรือ NOT_RUN_BY_DEVELOPER), และสิ่งที่ยังเป็น UNKNOWN

## การส่งต่อและ GitHub checkpoint

อัปเดต STATUS/DECISIONS และแผนที่เปลี่ยนใน local เมื่อสาระงานใหม่. Commit เป็นชุดที่ coherent และตรวจแล้ว; push เฉพาะ branch งานเมื่อ reviewable, มีข้อสรุป/blocker สำคัญ, ส่งต่อที่ต้องใช้ remote หรือ Owner สั่ง. ไม่ sync ทุกข้อความและไม่สร้าง Issue/commit ซ้ำเมื่อข้อมูลไม่เปลี่ยน. ดู OD-12/13 และ WORKFLOW.

Default launcher ไม่เปิด git-write/GitHub tools. PO ตรวจ diff/staged paths/tests/ข้อมูลลับแล้วจัด checkpoint; Claude publish ได้เฉพาะใบงาน/policy publication ที่ PO กำหนดแยกหลังรีวิว. Stage เฉพาะไฟล์ที่ตรวจแล้ว ไม่ใช้ git add .; ห้าม main/force push/merge/deploy/ปิด Issue เอง.

รายงาน LOCAL_ONLY หรือ SYNC_PENDING ตามจริง; SYNCED ต้อง push และ read-back ที่ commit ส่งจริงก่อน. การ sync ไม่เปิด worker/scheduler หรือสิทธิ์กล้อง. ไม่เก็บ raw transcript/credentials/วิดีโอ/พาธเครื่องจริงใน repo.

Claude ต้องอ่าน local baseline/งานค้างล่าสุดก่อนเริ่ม ไม่สมมติว่า remote หรือ session เดิมใหม่กว่า. `--allow-dirty` เป็นการรับทราบงานเดิม ไม่เพิ่มสิทธิ์แก้. ห้ามแก้ control/policy/launcher/local config เพื่อเพิ่มสิทธิ์เอง; งาน maintenance ต้องให้ PO จัด scope แยก. หาก lock ค้างหยุดและส่งกลับ PO; ไม่ลบหรือแย่ง lock เอง. Remote Control ไม่ถือ lock/รับ policy ของ launcher อัตโนมัติ ต้อง handoff ให้ชัดก่อนทำงาน.
