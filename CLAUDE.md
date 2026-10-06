# Claude Code

กติกาของ repo นี้อยู่ใน AGENTS.md (ใช้ร่วมกับ ChatGPT) ให้ทำตามไฟล์นั้น
คำสั่งควบคุมปัจจุบันอยู่ใน PROJECT_CONTROL.md และมีผลเหนือเอกสารอื่น โดยเฉพาะในเฟส FT-D0 ที่ให้ผู้พัฒนาใช้เครื่องมือไฟล์เท่านั้น

@AGENTS.md

## เริ่มงานจากสถานะเดียวกับ PO

ก่อนลงมือให้อ่าน `docs/STATUS.md`, `docs/DECISIONS.md`, `docs/PLAN.md` และ `docs/WORKFLOW.md` ร่วมกับ PROJECT_CONTROL/AGENTS แล้วรายงาน baseline/phase/blockers/next action. อ่านจาก checkout ของ branch/commit ที่ PO ยืนยัน ไม่สมมติว่า main มีข้อมูลใหม่หรือ session เดิมจำอัปเดตเอง
ถ้าไม่มี GitHub/Bash tools ให้ PO ส่งบริบทที่อ่านจาก remote ล่าสุด ไม่ยกระดับสิทธิ์เอง. จบงานรายงานสิ่งที่ทำจริง tests/evidence สิ่งที่ไม่ได้ทำ และงานถัดไปให้ PO อัปเดต GitHub. ไม่ใส่ข้อมูลลับ และไม่ถามรุ่นกล้อง/เราเตอร์ที่ STATUS ยืนยันไว้แล้วซ้ำ
