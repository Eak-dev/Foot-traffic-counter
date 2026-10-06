# วิธีทำงาน: ChatGPT เป็น PO/PM · Claude เป็น Developer

คุณเอกคุยกับ ChatGPT จุดเดียว งานปัจจุบันคือ Issue #1, branch `claude/ft-d0-preflight`.
อ่าน `PROJECT_CONTROL.md`, `AGENTS.md`, `docs/PLAN.md`, `docs/PREPROJECT_PLAN.md` และ `docs/STATUS.md` ก่อนทำงานทุกครั้ง.
Owner Decision มีอำนาจสูงสุด; ผู้พัฒนาห้ามเปลี่ยน control หรือขยาย scope เอง.

## ทางที่พิสูจน์แล้วใน FT-D0

ChatGPT → Remote Desktop Commander → MacBook ที่บ้าน → Claude Code → ไฟล์บน branch → PO ทดสอบและตรวจ diff → PR ให้ Owner ตรวจ.
การเรียก Claude Sonnet 5 ผ่าน CLI สำเร็จจริง; ไม่ใช่เพียงตรวจว่าติดตั้งอยู่.
การเข้าถึง Mac ไม่ได้แปลว่าเข้าถึงกล้องร้านได้. ไม่มี worker ของ GitHub Actions หรือ scheduler เปิดใช้งาน.

| ผู้รับผิดชอบ | ทำอะไร | ขอบเขต |
| --- | --- | --- |
| ChatGPT / PO | วางแผน, ส่งงาน, ตรวจผลแยก, รันทดสอบ, commit/push เฉพาะ branch งาน, เปิด PR | ไม่ merge, ไม่เปลี่ยนกล้องหรือเครือข่ายโดยไม่มีเกตที่อนุมัติ |
| Claude / Dev | เขียนและแก้เอกสาร/โค้ด/ทดสอบภายในรายการไฟล์ที่อนุญาต | ใน D0 มีเครื่องมือไฟล์เท่านั้น ไม่มี Bash/MCP/เครือข่าย/ไฟล์ลับ; ถ้าไม่ได้รันทดสอบให้รายงาน NOT_RUN_BY_DEVELOPER |
| Owner | ตัดสินใจธุรกิจ, อนุมัติสิทธิ์เฉพาะงานและรายจ่ายซอฟต์แวร์, merge และ deploy | โครงการนี้ไม่ซื้อฮาร์ดแวร์เพิ่ม |

## คำสั่งแบบจำกัดขอบเขตที่ใช้จริง

PO ตรวจ repository, branch, commit และสถานะไฟล์ก่อนสั่งงาน. ห้าม checkout/pull/reset โดยอัตโนมัติทับงานที่ยังไม่ commit; ไม่ต้องสลับไป main เพื่อเริ่มงาน.
ตัวอย่างนี้ใช้บน branch ที่ PO เตรียมและตรวจแล้วเท่านั้น; ไฟล์คำสั่งต้องไม่มีข้อมูลลับหรือวิดีโอ.

```bash
cd ~/Foot-traffic-counter
git branch --show-current
git rev-parse HEAD
git status --short

# หลังตรวจว่าตรง PROJECT_CONTROL และไม่มีงานอื่นถูกทับแล้ว
claude -p --model claude-sonnet-5 --effort high   --restricted --permission-mode dontAsk --permission-prompts none   --tools 'Read,Glob,Grep,Write,Edit'   --allowedTools 'Read,Glob,Grep,Write,Edit'   --strict-mcp-config --mcp-config '{"mcpServers":{}}'   --disable-slash-commands --no-chrome --no-session-persistence   --max-budget-usd 6 --output-format json   < "$TASK_FILE" > "$RESULT_FILE"
```

`TASK_FILE` และ `RESULT_FILE` เป็นพาธไฟล์งานที่ PO กำหนดไว้นอก repo ก่อนรัน ไม่ใช่คำสั่งพร้อมรันโดยไม่ตั้งค่า. เพดาน 6 USD เป็นตัวอย่างจำกัดการรันครั้งเดียว ไม่ใช่งบรายเดือนหรือการยืนยันยอดเรียกเก็บ; ตรวจบัญชีจริงแยกต่างหาก.

- ตรวจ exit code, `is_error`, `result`, `modelUsage` และ permission denials. ข้อความว่าสำเร็จจากผู้พัฒนาไม่แทนผลทดสอบ.
- `--allowedTools` อนุมัติการเรียกเครื่องมือล่วงหน้า ไม่ใช่ sandbox ด้วยตัวเอง. ในคำสั่งนี้ตัด Bash และ MCP ออก และใช้ restricted mode กับรายการไฟล์ในงาน.
- ไม่ใช้ bypass permissions, ไม่เปิด Bash(git *), Bash(gh pr *) หรือ shell ทั่วไปให้ Claude ใน D0.
- คำสั่งนี้ใช้ `--no-session-persistence` จึงไม่เสนอ `--resume`; งานแก้ตาม review เป็นคำสั่งใหม่พร้อมหลักฐานและขอบเขตเดิม.
- ไม่ใช้ `--bare`: โหมดนั้นเปลี่ยนการโหลดกติกาและวิธียืนยันตัวตน; ไม่ต้องเปลี่ยนการล็อกอินที่ทำงานอยู่.
- PO รันทดสอบด้วย stdlib: `python3 -m unittest discover -s tests -t . -v` และตรวจ `git diff --check` ก่อน publish.
- หยุดเมื่อพบงานนอกขอบเขต; ไม่มีการยกระดับสิทธิ์ ติดตั้ง dependencies เปลี่ยนรุ่นโมเดล หรือเริ่มกล้องจริงอัตโนมัติ.

## GitHub คือหลักฐานและคิวงาน ไม่ใช่ตัวรันโดยตัวเอง

Issue ใช้เก็บ scope/เกณฑ์รับงาน; PR ใช้เก็บ diff และหลักฐาน. การเปิด Issue ไม่ได้ทำให้ Claude ทำงานเมื่อ Mac ปิด.
ยังไม่ต้องเพิ่ม Actions หรือ agent platform เพราะช่องทางรีโมตปัจจุบันใช้สั่งงานได้แล้ว.
การรันรายคืนเป็นเฟส D5 ต้องตรวจไฟเลี้ยง การพักเครื่อง งานค้าง การรันซ้ำ และนโยบายพื้นที่ ก่อน Owner อนุมัติ scheduler.
ไม่มีการรับรองว่าแชตหรือ Claude จะทำงานต่อเองหลังจบการสั่งงานครั้งนี้.

## งานที่ส่งให้ Claude ต้องมี

Model/Effort, baseline/branch, Issue/phase, allowed/forbidden paths, Definition of Done, validation, deployment permission และเงื่อนไขหยุด.
ไม่ใส่รหัสผ่าน token IP ส่วนตัว serial รูปหรือวิดีโอลูกค้าใน prompt/Issue/log ที่แชร์ได้.
รายละเอียดที่ลงเครื่องจริงต้องให้ Owner กรอกในช่องทางเฉพาะเมื่อมีการอนุมัติขั้นเชื่อมต่อแล้ว.

อ้างอิงการใช้ CLI: https://code.claude.com/docs/en/headless และ https://code.claude.com/docs/en/model-config.
