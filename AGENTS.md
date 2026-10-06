# กติกาสำหรับ AI ที่ทำงานใน repo นี้ (ChatGPT, Claude CLI และอื่น ๆ)

โปรเจกต์: นับคนเดินผ่านหน้าร้านจากกล้อง Tapo C545D แล้วส่งยอดขึ้น Google Sheets
เจ้าของงาน: คุณ Eak — สื่อสารเป็นภาษาไทย

## ก่อนเริ่มงานทุกครั้ง

1. อ่าน `docs/PLAN.md` (สเปกกลาง) และ `docs/STATUS.md` (ใครทำอะไรอยู่ เฟสไหนเสร็จแล้ว)
2. ดู GitHub Issues ที่เปิดอยู่ ว่ามีคำถามหรืองานค้างที่เกี่ยวกับงานของคุณหรือไม่

## ระหว่างทำงาน

- ทำงานใน branch แยก ตั้งชื่อตามผู้ทำ เช่น `claude/counter`, `claude/fix-rtsp`
- เปิด Pull Request เข้า `main` ห้าม push ตรงเข้า `main` (ยกเว้นแก้เอกสารเล็กน้อย)
- ยึดสเปกใน `docs/PLAN.md` ถ้าต้องเปลี่ยนสเปก ให้แก้ PLAN.md ใน PR เดียวกันและเขียนเหตุผลไว้ในคำอธิบาย PR
- โค้ดต้องเล็ก: ใช้ Ultralytics `ObjectCounter` เป็นแกน ไม่เขียนตัวตรวจจับหรือ tracker เอง
- ไลบรารีที่อนุญาต: ultralytics, opencv-python-headless, gspread, google-auth, pyyaml, python-dotenv
- ห้ามมี: การจดจำใบหน้า ฐานข้อมูล เว็บเซิร์ฟเวอร์ Docker
- ห้ามบันทึกภาพหรือวิดีโอจากกล้องลง repo หรือดิสก์ (ยกเว้นโหมด `--debug` ที่แสดงบนจอเท่านั้น)

## ความลับ

- ห้าม commit รหัสกล้อง, `.env`, ไฟล์ key ของ Google service account หรือ IP ภายนอกของร้าน
- ใช้ `.env.example` และ `config.example.yaml` เป็นแม่แบบเท่านั้น

## เมื่อทำงานเสร็จ

1. อัปเดต `docs/STATUS.md` ใน PR เดียวกัน: ติ๊กงานที่เสร็จ และเขียนบรรทัดสั้น ๆ ใน "บันทึกล่าสุด"
2. ถ้ามีคำถามถึงอีกฝั่ง (Claude ↔ ChatGPT) หรือถึงคุณ Eak ให้เปิด GitHub Issue แทนการฝากข้อความ
3. รันชุดทดสอบ `python -m pytest` ให้ผ่านก่อนเปิด PR

## แบ่งหน้าที่

คุณ Eak คุยกับ ChatGPT ที่เดียว ChatGPT วางแผนแล้วสั่ง Claude เขียนโค้ด วิธีสั่งงานอยู่ใน `docs/WORKFLOW.md`

| ผู้ทำ | หน้าที่หลัก |
| --- | --- |
| ChatGPT | วางแผน แตกงาน สั่ง Claude (ผ่าน `claude -p` หรือ Issue `[claude]`) อ่านผลแล้วสรุปให้คุณ Eak |
| Claude (Claude CLI บน MacBook / claude.ai) | เขียนโค้ด `counter.py`, `draw_lines.py`, `tests/`, `foot-counter.service`, README, รันทดสอบ, เปิด PR, SSH เข้า Pi เพื่อติดตั้งและปรับจูน |
| คุณ Eak | ตัดสินใจ, merge PR, งานหน้าร้านและบัญชีต่าง ๆ |

ถ้าได้รับคำสั่งผ่าน `claude -p` ให้จบงานด้วยข้อความสรุปภาษาไทยสั้น ๆ: ทำอะไรไป, ลิงก์ PR, ผลทดสอบ, และสิ่งที่ต้องให้คุณ Eak ตัดสินใจ
