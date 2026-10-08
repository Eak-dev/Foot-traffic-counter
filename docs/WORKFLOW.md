# วิธีทำงาน: Codex วางแผนและรีวิว · Claude พัฒนาใน local

Owner decision 2026-10-07: ใช้ **local folder เดียวและ branch งานเดียวกัน** เป็นหลัก แล้วอัปเดต GitHub ตามจุดส่งงาน. อ่าน [PROJECT_CONTROL](../PROJECT_CONTROL.md), [AGENTS](../AGENTS.md), [PLAN](PLAN.md), [STATUS](STATUS.md) และ [DECISIONS](DECISIONS.md) ก่อนเริ่ม.

## โฟลเดอร์และ branch กลาง

- ใช้ checkout ที่เลือกในโปรเจกต์ Codex เป็นโฟลเดอร์หลัก. ตอนนี้ branch คือ `claude/ft-d0-preflight` เดิม; [PR #2](https://github.com/Eak-dev/Foot-traffic-counter/pull/2) merged ตามคำสั่ง Owner เป็น `v0.1.0` แล้ว. งานชุดถัดไปใช้ branch เดิมและเปิด PR ใหม่เมื่อถึง checkpoint; ไม่ส่งงานใหม่ลง PR ที่ merged แล้ว.
- Codex และ Claude เรียกคำสั่งจาก root เดียวกัน. พาธจริงเก็บเฉพาะ `.claude/workflow.local.json` ที่ Git ไม่ติดตาม; ไม่ใส่พาธเครื่องจริงในเอกสารที่เผยแพร่.
- สำเนาเก่าเก็บไว้แต่ไม่ใช้ส่งงาน. ไม่สร้าง worktree/branch เพิ่มโดยอัตโนมัติ. หลัง Owner merge ให้ PO ตรวจ tree ก่อนตกลง branch งานถัดไป; กติกา branch เดียวไม่ใช่สิทธิ์ push เข้า main.
- ระหว่างพัฒนา **local HEAD และไฟล์ที่ยังไม่ commit** เป็นสถานะงานปัจจุบัน. GitHub อาจตามหลังได้ตามจังหวะ checkpoint. ไม่บังคับ pull หรือให้ HEAD ตรง remote ทุกข้อความ.
- ไม่มีการ switch/main checkout/pull/reset/rebase/merge อัตโนมัติ. งานค้างต้องระบุว่าเป็นของใครและอยู่ใน scope ไหนก่อนทำต่อ.

## หน้าที่และการถือสิทธิ์แก้ไฟล์

**OD-33 PO ownership:** Owner มอบหมายให้ Codex จัดการงานและคุยกับ Claude โดยตรง. PO เตรียมใบงานที่มี acceptance criteria, review อิสระและส่งแก้ใน scope เดิมจนตรวจรับได้ ก่อนจัด checkpoint. ไม่รอ Owner ทำหน้าที่ประสาน Dev หรือค้นคำตอบทางเทคนิค. สิทธิ์นี้ไม่แทนการอนุมัติเกตอุปกรณ์/รายจ่าย/merge และไม่ทำให้ระบบรันต่อเมื่อ Mac/chat offline.

**OD-30 research ownership:** PO/Dev ค้นหา router/VPN/vendor API evidence เอง ไม่รอ Owner ติดต่อ AIS/TP-Link เป็นงานค้นหา. การไม่พบเอกสารให้รายงานเป็น UNKNOWN พร้อมขอบเขตที่ตรวจ ไม่สรุป unsupported จากผลค้นหา และไม่วนส่งคำถามเดิมกลับ Owner. งานหน้างานหรือการเปลี่ยน scope ที่ต้องใช้ Owner ให้เตรียมข้อเสนอเฉพาะก่อน.

**OD-29 communication:** ทำงานที่อนุมัติแล้วต่อเนื่องตามลำดับจนจบหรือพบ blocker ที่ต้องให้ Owner ช่วย; ลดข้อความระหว่างงานและแจ้งเฉพาะปัญหา/คำถามที่จำเป็น พร้อมสรุปเมื่อจบชุดงาน. เก็บรายละเอียดและผลจริงใน local STATUS/evidence; ไม่สร้าง worker/scheduler และไม่ตีความเป็นสิทธิ์ข้ามเกตอุปกรณ์.

**OD-26 (2026-10-08): Owner ใช้ iPhone เป็นหลัก.** Codex เป็นผู้รันงานบน Mac ที่เชื่อมถึงได้และอยู่ใน scope ที่อนุมัติ; ไม่ให้ Owner เปิด Terminal/พิมพ์คำสั่งเป็นเกตบังคับ. งานใน Tapo และการตัดสินใจยังเป็นของ Owner. การรับ private endpoint/credentials ต้องมีช่องทางที่ตรวจแล้วก่อน ไม่ให้ส่งค่าในแชต/Issue และไม่ค้นไฟล์บ้านหรือ secrets ทั้งเครื่อง. iCloud Drive ของ Owner เป็นเพียงทางเลือกที่รอ readiness/ไฟล์เป้าหมายที่ระบุชัด ไม่ติดตั้ง/เปิด sync/เปลี่ยน account อัตโนมัติ. การทำงานจาก iPhone ไม่ได้เปิด scheduler หรือรับรองว่า Mac ที่ offline จะรันงานได้.

**OD-27/28 readiness update:** Owner แจ้ง iCloud Drive เปิดอยู่และทำขั้นตอนส่ง IP เสร็จ; PO พบหนึ่งโฟลเดอร์ว่างที่ส่งใน `FootTrafficSetup` บน Mac แล้ว. ตรวจ RFC1918/ความกำกวม/ไม่ตาม symlink และบันทึกด้วย atomic helper เดิมใน ignored config mode 0600; offline validation PASS. ไม่ต้องส่ง IP ซ้ำ. PO รับเฉพาะจุดที่ Owner ส่งและเก็บ output ที่ redacted ไม่อ่านไฟล์ส่วนตัวเดิมหรือเก็บ raw names ใน Git. ช่องทางนี้ไม่รับ password/account/video; Claude ไม่มีสิทธิ์อ่านค่าจริง. Check ยัง BLOCKED, route/auth/download NOT_TESTED และ camera requests 0.

OD-25 Owner อนุมัติ maintenance/control แยกและ private IP-input/offline check แล้ว. PO เตรียม scope ใน PROJECT_CONTROL; Claude รับเฉพาะ `tools/ft_connect.py`, `tests/test_ft_connect.py`, `docs/MAC_CONNECTION_GUIDE.md` ตามใบงาน. ไม่แก้ launcher/policy ไม่ให้ Dev อ่าน local IP/config/runtime หรือเชื่อมกล้อง; tests ใช้ temporary synthetic config เท่านั้น. สิทธิ์ติดตั้ง OD-24 เป็นของ PO และเสร็จใน ignored runtime แล้ว ไม่ขยายสิทธิ์ shell/เครือข่ายของ Dev.

| ผู้ทำ | หน้าที่ |
| --- | --- |
| Codex / PO | แตกงาน, เตรียม control/ใบงาน, ตรวจ baseline และงานค้าง, เรียก Claude, รีวิวอิสระ, จัด checkpoint และสรุปให้ Owner |
| Claude / Dev | อ่านสถานะล่าสุด, แก้เฉพาะไฟล์ในใบงาน, รันชุดทดสอบ local/synthetic ที่อนุญาต, แก้ตามรีวิวและส่งมอบหลักฐาน |
| คุณ Eak / Owner | ให้เป้าหมายและตัดสินใจธุรกิจ, merge, อนุมัติงานอุปกรณ์/production/รายจ่ายตามเกต |

มีผู้แก้ไฟล์ **หนึ่งรายต่อครั้ง**: PO เตรียมงาน → Claude ถือ tree → Claude ส่งมอบ → PO ตรวจ. ระหว่าง Claude ทำงาน PO ไม่แก้ไฟล์ รันทดสอบ stage/commit/switch หรือ publish. `tools/claude_dev.py` ใช้ `.claude/dev.lock/` กันการเรียกซ้อนและตรวจ scope หลังจบ.
Lock นี้เป็นกติกาความร่วมมือ ไม่บล็อก editor หรือ CLI ที่เรียกเอง. เมื่อ timeout/interrupt/launch-cleanup error ตัวเรียกหยุด process group แต่ **เก็บ lock ไว้** ให้ PO ตรวจ process ที่อาจแยก session แล้วก่อนปล่อย ownership; ไม่อ้างว่า process group ครอบคลุมทุก detached process. ถ้าพบ lock ค้าง หยุด ตรวจว่ากระบวนการเก่าจบจริง และให้ PO ปล่อย ownership ก่อนเริ่ม; ตัวเรียกไม่แย่งหรือลบ stale lock เอง.

## รอบส่งงาน

**OD-37 ปัจจุบัน:** พบ [OnTapo SD relay และ C545D developer research](REMOTE_SD_RESEARCH.md). เลือกตรวจ/ออกแบบ adaptation ของ SD relay ก่อน Tapo Care; คงต้นฉบับ SD และ Mac บ้าน. มี author-reported TC65 download กับ PO static source review แต่ยังไม่มีผล C545D ของเรา จึง CONDITIONAL research ไม่ใช่ live/production PASS. ไม่ต้องเลือกหรือซื้อ Tapo Care ตอนนี้; auth/input/region/Fixed/quota ยังต้องพิสูจน์

**OD-36 ประวัติ — ลำดับ candidate ถูกแทนที่ด้วย OD-37:** ปรึกษา Claude และตรวจ primary sources แล้ว: automatic SD จาก Mac บ้านภายใต้ข้อจำกัดเดิมเป็น NO-GO สำหรับ implementation ตอนนี้ (ไม่ใช่พิสูจน์ว่าเป็นไปไม่ได้ถาวร). พัก acquisition scaffolding เพิ่มและไม่รอ Owner router UI เป็นเกตบังคับของคำตัดสิน. [FEASIBILITY_REVIEW](FEASIBILITY_REVIEW.md) แยก manual SD/local import หนึ่งคลิปกับ Tapo Care cloud-source เป็น CONDITIONAL proposals; cloud ต้องยอมรับ source/privacy/งบและพิสูจน์ auth/Fixed/completeness ใหม่ก่อน. ไม่เปลี่ยน SD spec หรือเปิดเกตวิดีโอ/นับ/ซื้อในงานนี้

ข้อความ OD-34/35/36 ด้านล่างเป็นประวัติ; ไม่ใช่ขั้น Owner ที่ต้องทำตอนนี้. PO ตรวจ SD relay ตาม OD-37 ก่อน; ไม่ผลักงานค้นหาให้ Owner

OD-35 supersedes การนำ Mac ไปที่ร้านเป็น next action: PO รับผิดชอบแก้ home-to-shop ผ่าน gateway ที่ตรวจแล้ว; Owner ช่วยเฉพาะเข้าหน้า router ร้านบน iPhone ที่ PO ยังเข้าถึงไม่ได้. HOME_CONNECTION_PLAN ระบุ capability branches/route/rollback; ไม่ขอสิทธิ์ทดลองทั่วไปซ้ำ และไม่ขยายสิทธิ์ Dev/ติดตั้งโดยเดา

OD-34 เป็น PO private/network diagnostic ตามคำสั่งเชื่อมจริงของ Owner: อ่าน current OS route สำเร็จ พบ IP ร้านทับ LAN บ้าน จึงไม่ส่ง TCP ผิดปลายทาง. ไม่ให้ Claude อ่าน endpoint/credentials หรือเพิ่ม network tools. ขั้นที่ Owner ช่วยคือให้ Mac เดิมต่อ Wi-Fi ร้าน; PO รับผิดชอบคำสั่งทดสอบต่อ. Scope/bounds/ผลดู PROJECT_CONTROL และ STATUS; ไม่วนถามอนุญาตทั่วไปใหม่.

1. Owner บอกเป้าหมายกับ Codex เช่น “ให้ Claude ทำงาน X ตามแผน ตรวจและแก้จนพร้อม review”. ไม่ต้องคัดลอก prompt เอง.
2. PO ตรวจ local root/branch/full HEAD, dirty files, phase และสิทธิ์; เขียนใบงาน local ที่ไม่มีข้อมูลลับ.
3. ใบงานระบุเป้าหมายหนึ่งเรื่อง, baseline, ไฟล์ที่แก้ได้, เกณฑ์เสร็จ, คำสั่งทดสอบ, ข้อห้าม, checkpoint และเงื่อนไขหยุด. แยกการยอมรับไฟล์ค้างจากสิทธิ์แก้ไฟล์นั้น.
4. เรียก Claude ผ่านตัวเรียก. Claude อ่านสถานะปัจจุบันและรายงาน BASELINE/PHASE/BLOCKERS/NEXT_ACTION ก่อนลงมือ.
5. Claude ส่ง changed files, tests/exit code หรือ NOT_RUN_BY_DEVELOPER, evidence, blockers และ next action. ผล JSON ของโมเดลไม่แทนผลทดสอบ.
6. PO ตรวจ diff กับเกณฑ์และหลักฐาน; ทดสอบเพิ่มเติมตรงจุดที่จำเป็น. ส่งคำสั่งใหม่สำหรับแก้ตามรีวิวภายใน scope เดิมได้โดยไม่วนขอ Owner อนุมัติซ้ำ. ถ้า scope/สิทธิ์/เกตต้องเปลี่ยนให้หยุดเฉพาะจุดนั้นและรายงาน.
7. เมื่องาน reviewable ให้ local commit และทำ GitHub checkpoint ตามหัวข้อถัดไป. Owner เป็นคน merge.

## ตัวเรียก local

ใช้ Python 3.9+ standard library และ Claude CLI ที่ล็อกอินอยู่. รุ่นที่ตรวจล่าสุดคือ 2.1.292; หลักฐาน D0 รุ่นเดิมคงไว้ตามประวัติ. ไม่ติดตั้งหรือเปลี่ยนบัญชีอัตโนมัติ.

ตั้งค่าครั้งแรกจาก **root ที่ต้องการใช้จริง** โดย PO; คำสั่งนี้เขียนเฉพาะ local config ที่ไม่ขึ้น Git:

```bash
python3 - <<'PY'
import json
from pathlib import Path
root = Path.cwd().resolve()
(root / '.claude').mkdir(exist_ok=True)
(root / '.claude/workflow.local.json').write_text(json.dumps({
    'root': str(root), 'branch': 'claude/ft-d0-preflight',
    'model': 'claude-sonnet-5', 'max_budget_usd': 6
}, indent=2) + '\n')
PY
python3 tools/claude_dev.py --check
```

ตัวเรียกใช้ effort medium สำหรับงานย่อยและมี timeout 600 วินาที (กำหนด `--timeout` ตาม scope ได้); แบ่งงานใหญ่เป็นงานเล็กที่ตรวจรับได้. เพดาน 6 USD เป็นค่าจำกัดการรันที่ PO ปรับให้ตรงงานใน local config; ไม่ใช่ยอดเรียกเก็บที่ยืนยันแล้ว. ไม่มีการเปลี่ยนโมเดลเองเมื่อเจอปัญหา.

ตัวอย่างงานแก้เอกสารหนึ่งไฟล์ (สร้างใบงานที่ตรวจแล้วก่อนรัน):

```bash
python3 tools/claude_dev.py \
  --task .claude/tasks/task.txt \
  --baseline "$(git rev-parse HEAD)" \
  --write-path docs/STATUS.md
```

- `--check` ตรวจ local อย่างเดียวและไม่เรียก Claude. เมื่อมีไฟล์ค้างจะบล็อก; PO ยอมรับเฉพาะรายการที่ตรวจแล้วด้วย `--allow-dirty docs/STATUS.md` เป็นต้น.
- `--write-path` เป็นไฟล์ที่แก้ได้ในงานนี้; `--allow-dirty` รับทราบงานเดิม ไม่เพิ่มสิทธิ์แก้. ไม่ใช้ wildcard, absolute path, traversal หรือไฟล์ control/policy/local config/ตัวเรียกเอง.
- ตัวเรียกตรวจ root/branch/baseline และถือ lock. ระหว่างรันไม่ switch/commit/push. เก็บ prompt/result เฉพาะ local ใน `.claude/tasks/` และ `.claude/results/` ที่ Git ไม่ติดตาม; ไม่คัดลอก raw output ขึ้น GitHub.
- Claude มี restricted file tools และอนุญาต Bash เฉพาะ `python3 -m unittest discover -s tests -t . -v`. Policy `.claude/dev-policy.json` บังคับ sandbox, ไม่มี network หรือ unsandboxed fallback และบล็อก secrets/protected paths. ตัวเรียก resolve filesystem policy เทียบ root จริงและปิด background tasks ของ Claude ต่อ invocation. `--allowedTools` เป็นสิทธิ์เครื่องมือ ไม่ใช่ sandbox ของ test code.
- Invocation ที่จบปกติและ scope ไม่เปลี่ยนหมายถึงส่งมอบ local สำเร็จ **ไม่ใช่ tests/acceptance ผ่าน**. PO ตรวจหลักฐานก่อนรับงาน; error/permission denial/timeout/ผลไม่ครบไม่ใช่ความสำเร็จ. รักษาไฟล์ที่ทำแล้วไว้เมื่อ failure.
- ใช้ task ใหม่พร้อมเอกสาร/ผลรีวิวปัจจุบันต่อรอบ; `--no-session-persistence` ทำให้ไม่มี `--resume` ใน workflow นี้.
- Sandbox ของ Codex อาจมองไม่เห็น login ของ Claude แม้ host ล็อกอินอยู่. PO ตรวจสถานะและใช้ช่องทางเรียกที่แพลตฟอร์มอนุญาต; ไม่เปิด Full access ทั่วเครื่องหรือเปลี่ยน auth เพื่อแก้อัตโนมัติ. ถ้าการเรียกถูก approval review บล็อก รายงานจุดที่ติดตามจริง.
- การแก้ launcher/control/policy ใช้ใบงาน maintenance แยกที่ PO ตรวจและจัดสิทธิ์เฉพาะ ห้ามให้ launcher เพิ่มสิทธิ์ตัวเอง.

## Local ก่อน · GitHub ตาม checkpoint

อัปเดต STATUS/DECISIONS/แผนใน **local** เมื่อสาระงานเปลี่ยน. Local commit ทำได้เมื่อมีชุดการเปลี่ยนที่ coherent และตรวจแล้ว; ไม่สร้าง commit ทุกข้อความ.

Push เฉพาะ branch งานเมื่อมีงานพร้อม review, ข้อสรุปหรือ blocker สำคัญที่ต้องให้ทีมอ่าน, จุดส่งต่อที่ต้องใช้ remote หรือ Owner สั่ง. จังหวะนี้แทนข้อกำหนด sync ทุกเทิร์นใน OD-11 (ดู OD-12).

ก่อน publish PO ตรวจ branch, diff/staged paths, tests และข้อมูลลับ; stage เฉพาะรายการที่ตรวจ ไม่ใช้ `git add .`. Default launcher ไม่มี git-write/GitHub tools จึงให้ PO ทำ checkpoint. Claude ทำ local commit/push/PR ได้เฉพาะงาน publication ที่ PO จัดคำสั่ง/policy เฉพาะไว้หลังรีวิว; ไม่มีสิทธิ์ทั่วไปจากการเป็น Dev.

- `LOCAL_ONLY`: มีความคืบหน้า local; ยังไม่ถึง checkpoint หรือยังไม่ push.
- `SYNC_PENDING`: ต้อง publish แล้วแต่ push/read-back ไม่สำเร็จ; ระบุสิ่งที่ค้างจริง.
- `SYNCED`: push และอ่าน GitHub กลับแล้ว branch/PR head ตรง commit ที่ส่ง. ไม่ใช้คำนี้แทนสถานะไฟล์ค้างใน local.

อัปเดต PR description ตาม implementation ล่าสุดที่ checkpoint. ไม่ส่ง full transcript, credentials, private endpoints, raw video หรือพาธข้อมูลจริง. ห้าม main push, force-push, reset/rebase ทับงาน, merge/deploy และปิด Issue อัตโนมัติ.

## ช่องทางทำงาน

- **A — Codex → local Claude CLI:** ช่องทางหลัก ใช้ checkout/branch/config/lock ที่กล่าวมา.
- **B — Owner → Claude Remote Control:** ทำบน checkout/branch เดียวกัน หลังส่งมอบ ownership ให้ชัด. เปิด session ในโฟลเดอร์หลักและอ่านสถานะใหม่; interactive session ไม่รับ lock/policy ของ launcher โดยอัตโนมัติ ต้องจัด ownership และสิทธิ์แยกให้ตรงงานก่อนเริ่ม. ไม่ใช้สองช่องทางเขียนพร้อมกัน.
- **C — GitHub:** หลักฐานและคิวงาน. Issue ไม่ปลุก Claude เอง; ไม่มี worker/scheduler เปิดใช้งาน และ Mac ต้องพร้อมจึงรัน local ได้.

สิทธิ์พัฒนา local นี้ไม่เปิดเกตกล้อง D1–D5, ไม่เพิ่มการติดตั้ง/production/merge/deploy. แผน batch acquisition และข้อจำกัดเดิมยังใช้อยู่.

อ้างอิง CLI/permissions: [Claude headless](https://code.claude.com/docs/en/headless), [permissions](https://code.claude.com/docs/en/permissions), [sandbox](https://code.claude.com/docs/en/sandboxing), [Remote Control](https://code.claude.com/docs/en/remote-control).
