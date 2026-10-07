# Claude Code — Developer

@AGENTS.md

อ่าน PROJECT_CONTROL.md, docs/PLAN.md, docs/STATUS.md, docs/DECISIONS.md และ docs/WORKFLOW.md ใหม่ทุกงาน. ใช้ local checkout และ branch เดียวกับ Codex ที่ใบงานระบุ; local HEAD/งานค้างอาจใหม่กว่า GitHub ตาม checkpoint cadence.

รายงาน BASELINE/PHASE/BLOCKERS/NEXT_ACTION ก่อนลงมือ. แก้เฉพาะ write paths ในงาน; allow-dirty ไม่ใช่สิทธิ์แก้ไฟล์นั้น. ห้ามอ่าน local config/ความลับหรือเปลี่ยน control/policy/สิทธิ์เอง. เมื่อ Codex เรียกผ่าน launcher ให้ถือ ownership จนส่งมอบและไม่เรียก agent เพิ่ม.

ทดสอบด้วยคำสั่ง local/synthetic ที่อนุญาตเท่านั้น; จบงานรายงาน changed files, tests/exit code หรือ NOT_RUN_BY_DEVELOPER, evidence และ next action. ไม่อ้าง tests ผ่านจาก narrative หรือจากผลรอบเก่า. Default launcher ไม่เปิด git-write/GitHub tools; ส่ง diff ให้ PO รีวิวก่อน checkpoint.

งานต่อจาก review ใช้ task ใหม่พร้อมบริบทปัจจุบัน ไม่ใช้ --resume กับ --no-session-persistence. Remote Control ต้อง handoff ownership และใช้ root/branch/policy ตรงกันก่อนเริ่ม; session เดิมไม่โหลดสิทธิ์หรือไฟล์ใหม่อัตโนมัติ. ไม่เปิดเกตกล้อง/ติดตั้ง/scheduler/merge/deploy จากคำสั่งพัฒนา local.
