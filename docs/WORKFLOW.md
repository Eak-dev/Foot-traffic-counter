# วิธีทำงาน: ChatGPT เป็น PO/PM · Claude เป็น Developer

คุณเอกคุยกับ ChatGPT จุดเดียว งานปัจจุบันคือ Issue #1, branch `claude/ft-d0-preflight`.
อ่าน `PROJECT_CONTROL.md`, `AGENTS.md`, `docs/PLAN.md`, `docs/PREPROJECT_PLAN.md` และ `docs/STATUS.md`, `docs/DECISIONS.md` ก่อนทำงานทุกครั้ง.
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

## Conversation-to-GitHub sync

Owner ให้บันทึกข้อสรุปและความคืบหน้าระหว่างสนทนาลง GitHub เพื่อให้ทีมใช้ข้อมูลเดียวกัน; ทำในเทิร์นที่มีสาระงานเปลี่ยน ไม่ใช่ background monitoring

1. ก่อนแก้ อ่าน Issue/PR/สถานะ remote และตรวจ local branch/HEAD/dirty state. ไม่ overwrite งานผู้อื่นหรือ pull/reset โดยอัตโนมัติ
2. ทุก requirement, decision, ข้อมูลอุปกรณ์, ผลทดสอบ, blocker หรือ next action ใหม่ ให้ PO อัปเดต `docs/STATUS.md` และ `docs/DECISIONS.md` ตามประเภทข้อมูลก่อนตอบสรุป ไม่รอจบเฟส. ไม่มีข้อมูลเปลี่ยนไม่สร้าง commit ซ้ำ
3. STATUS ระบุ phase, สิ่งที่ทำจริง, สิ่งที่ยังไม่ได้ทำ, evidence, blocker/ผู้รับผิดชอบ, รอ Owner อะไร และ next action. DECISIONS แยก OWNER_DECISION, PROPOSED และ OBSERVED; ไม่ลบประวัติ ให้ระบุสิ่งที่ถูกแทนที่
4. ถ้าแผน/กติกาเปลี่ยน อัปเดต PLAN/PREPROJECT/AGENTS/WORKFLOW ที่เกี่ยวข้องใน commit เดียวกัน. PR comment เป็นหลักฐานเสริม ไม่ใช่ที่เดียวที่เก็บสถานะล่าสุด
5. push เฉพาะ branch review ที่ตรวจแล้ว และอ่านกลับจาก GitHub ที่ commit ใหม่พร้อมตรวจ PR head ก่อนรายงานว่า SYNCED; อัปเดต PR summary ถ้าข้อมูลเก่า. ไม่ merge/main push/ปิด Issue เพื่อให้การ sync ผ่าน
6. หากแก้/push/read-back ไม่สำเร็จ ให้แจ้ง SYNC_PENDING พร้อมสิ่งที่ค้างจริง; ไม่อ้างว่า Claude มีข้อมูลล่าสุด. ก่อนลองใหม่ต้องตรวจสถานะ remote ไม่ทับงานใหม่
7. ทุกครั้งที่ส่งงาน Claude ระบุ Issue/PR/branch/commit ให้ชัด และให้อ่าน PROJECT_CONTROL, AGENTS, PLAN, STATUS, DECISIONS และ PREPROJECT/WORKFLOW ส่วนที่เกี่ยวข้อง. ก่อนเริ่มต้องยืนยัน baseline/phase/blockers/next action; เมื่อจบรายงาน changed files/tests/evidence/blockers/next step
8. Claude ไม่มี network/Bash ใน D0: PO อ่าน GitHub และเตรียม checkout ที่ตรง commit ให้ ไม่สั่งให้ Claude ใช้เครื่องมือที่ไม่มีสิทธิ์. การมีไฟล์ใน GitHubไม่ใช่หลักฐานว่า session เดิมของ Claude โหลดข้อมูลใหม่แล้ว ต้องอ่านใหม่เมื่อมอบหมายงาน
9. ไม่คัดลอก full transcript, รูปลูกค้า/อุปกรณ์, raw video, password, token, OTP, IP จริง, SSID, serial, MAC address หรือพาธข้อมูลลับ. เก็บเฉพาะข้อสรุปและ readiness ที่จำเป็น
10. Standing permission นี้คือการบันทึกเอกสารระหว่างที่ทำงานในบทสนทนา ไม่ต้องขออนุมัติ docs-only sync ซ้ำ. ไม่เปิด scheduler/worker ไม่ปลุก Claude เอง และไม่ขยายสิทธิ์อุปกรณ์/production/merge/deploy

### สรุปส่งต่อที่ Claude ต้องรายงานก่อนลงมือ

```text
BASELINE: repo / branch / commit ที่ได้รับและอ่านจริง
PHASE: เฟสและ action ที่อนุญาตในงานนี้
CONFIRMED: ข้อมูลที่ยืนยันแล้ว ไม่ถาม Owner ซ้ำ
BLOCKERS: สิ่งที่ติด พร้อม evidence และผู้รับผิดชอบ
NEXT_ACTION: งานเล็กที่สุดที่ทำได้ภายใน scope
NOT_AUTHORIZED: สิ่งที่จะไม่ทำในงานนี้
```

หาก baseline หรือสิทธิ์ขัดกันให้หยุดเฉพาะจุดและแจ้ง PO ไม่ขยาย scope เอง. คำสั่ง sync เอกสารไม่ใช่คำสั่งให้ทดลองกล้องรอบใหม่
