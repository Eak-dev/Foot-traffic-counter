# foot-traffic-counter

โปรเจกต์เตรียมการดึงคลิปเหตุการณ์จากการ์ด SD ของกล้องในร้านเป็นชุด แล้วนับคนเดินผ่านภายหลังจากคลิปที่ดึงแล้ว
ตอนนี้อยู่ในเฟส **FT-D0 (เตรียมงาน)** ยังไม่มีการเข้าถึงกล้องหรือเครือข่ายร้าน

> **LEGACY / NOT USED:** ไฟล์ `.env.example` และ `config.example.yaml` เป็นของแผน Raspberry Pi + RTSP แบบ real-time เดิม
> ที่ถูกแทนที่แล้ว **CLI ใน FT-D0 นี้ไม่ได้อ่านไฟล์เหล่านี้** ห้ามนำไปใช้หรืออ้างอิงเป็นข้อกำหนดปัจจุบัน และยังไม่ได้ตรวจทาน (อยู่นอกขอบเขตที่แก้ได้ใน FT-D0)

- คำสั่งควบคุมปัจจุบัน: [PROJECT_CONTROL.md](PROJECT_CONTROL.md)
- แผนงาน: [docs/PLAN.md](docs/PLAN.md) · แผนก่อนโครงการและเกต: [docs/PREPROJECT_PLAN.md](docs/PREPROJECT_PLAN.md)
- ความคืบหน้าและจุดส่งต่อ: [docs/STATUS.md](docs/STATUS.md) · ข้อตัดสินใจ Owner: [docs/DECISIONS.md](docs/DECISIONS.md)
- วิธีทำงานร่วมกัน: [docs/WORKFLOW.md](docs/WORKFLOW.md)
- กติกาสำหรับ AI: [AGENTS.md](AGENTS.md)

## เครื่องมือ FT-D0 (`tools/ft_data.py`)

Python 3.9+ standard library เท่านั้น ไม่ติดตั้งแพ็กเกจเพิ่ม และไม่เข้าถึงเครือข่ายหรือกล้อง

```bash
# ตรวจความพร้อมของเครื่องแบบอ่านอย่างเดียว (ไม่รันโปรแกรมภายนอก)
python3 tools/ft_data.py doctor
python3 tools/ft_data.py doctor --json --min-free-gib 10 --disk-path .

# แฮชไฟล์ .mp4 ในโฟลเดอร์ที่ระบุ (ไม่ตามลิงก์สัญลักษณ์ ไม่แก้ไขไฟล์)
python3 tools/ft_data.py inventory /path/to/clips --json
```

- `doctor` ออกด้วยรหัส 0 เมื่อการเตรียมตัวผ่าน **ไม่ได้หมายความว่าพร้อมใช้งานจริง** (`live_ready` เป็น `false` เสมอใน FT-D0)
- `inventory` ไม่อ่านเวลาเหตุการณ์จากชื่อไฟล์หรือ mtime และไม่ตัดสินความครบของวัน (`complete_day` เป็น `false`)
- ผลลัพธ์แบบ `--json` ไม่มี path จริงหรือชื่อไฟล์ ใช้รหัสอ้างอิงแทน
- ค่า `--min-free-gib` เป็นค่าเสนอที่ยังไม่ได้รับอนุมัติจาก Owner

### ขอบเขตของ `inventory`

- **root** ที่ระบุ: ถ้าเป็นลิงก์สัญลักษณ์จะถูกปฏิเสธ (`INPUT_IS_SYMLINK`) แม้เขียนเป็น `link/.` หรือ `link/` ก็ตาม
  เส้นทางที่มี `..` ถูกปฏิเสธ (`INPUT_AMBIGUOUS_PATH`) เพราะความหมายขึ้นกับลิงก์ที่อยู่ระหว่างทาง
- **รายการย่อยทุกระดับ**: ลิงก์สัญลักษณ์ถูกนับและข้าม ไม่ตาม โฟลเดอร์ย่อยถูกเปิดซ้ำแบบ `O_NOFOLLOW` จากตัวอธิบายไฟล์ของโฟลเดอร์แม่
  ถ้าโฟลเดอร์ถูกสลับเป็นลิงก์หลังการแสดงรายการ จะถูกนับเป็น `changed` และสถานะเป็น `INCOMPLETE`
- **ส่วนแม่ของ path** (เช่น `/tmp` หรือ `/var` บน macOS ซึ่งเป็น alias ของระบบ) ยังใช้ได้ ไม่ได้ตรวจทุกชั้น
- นี่**ไม่ใช่ sandbox ของระบบไฟล์ทั้งหมด** และไม่อ่านโฟลเดอร์อื่นนอกที่ระบุ
- ไฟล์ที่อ่านระหว่างสแกนแล้วเปลี่ยน (ขนาด, mtime, ctime, inode หรือถูกแทนที่) จะไม่มีรายการแฮช และนับเป็น `changed`
  การตรวจทำในช่วงที่อ่านเท่านั้น ไม่ใช่ snapshot แบบอะตอมิกของระบบไฟล์ และอ่านไม่เกินขนาดตอนเปิดไฟล์
- **dedup ด้วย SHA256** ตรวจได้เฉพาะไฟล์ที่ไบต์เหมือนกันทุกประการ ไม่ตรวจวิดีโอที่ทับซ้อนกันหรือถูกเข้ารหัสใหม่ หรือฉากที่เหมือนกัน
  การจัดการช่วงเวลาทับซ้อนเป็นงานของ D3/D4

### ข้อผิดพลาดของการเรียกใช้

- ข้อผิดพลาดของ argument แสดงรหัสคงที่ เช่น `UNRECOGNIZED_ARGUMENT`, `INVALID_COMMAND`, `INVALID_MIN_FREE_GIB` และ **ไม่แสดงค่าที่ผู้ใช้พิมพ์** (รวมชื่อคำสั่ง, path และ token)
- ถ้าใส่ `--json` จะได้ผลเป็น JSON บน stdout ส่วนโหมดข้อความไปที่ stderr ทั้งสองกรณี exit code เป็น `2`
- ข้อความที่มีอักขระ NUL หรือ argument ที่ไม่ใช่ข้อความ ถูกปฏิเสธด้วย `INVALID_ARGV`

## ทดสอบ

```bash
python3 -m unittest discover -s tests -t . -v
```

ใช้ข้อมูลจำลองที่เป็นไบต์สังเคราะห์เท่านั้น ไม่ใช่วิดีโอจากกล้องจริง
หลักฐาน D0 เดิม: ผู้พัฒนาไม่ได้รันทดสอบเอง (NOT_RUN_BY_DEVELOPER); PO รัน 52/52 tests และตรวจแยก 7/7 ตาม [หลักฐาน D0](docs/FT_D0_EVIDENCE.md). Workflow ปัจจุบันอนุญาตให้ Claude รัน unittest แบบ local/synthetic ใน sandbox. ผลรอบใหม่และการทดสอบตัวเรียกดู [STATUS](docs/STATUS.md); ไม่ใช่ผลดึงคลิปจากกล้อง.

## ยังไม่มี

- การดึงข้อมูลจากกล้อง (เฟส D1–D3 รอเกตและการอนุมัติ)
- การนับคน (เฟส D4)
- การตั้งงานอัตโนมัติ (เฟส D5)

## พัฒนา local กับ Codex และ Claude

ใช้ local checkout และ branch งานเดียวกัน (`claude/ft-d0-preflight` ตอนนี้), หนึ่งผู้แก้ไฟล์ต่อครั้ง. Codex เตรียมงานและเรียก Claude เป็น Dev, Claude ส่ง diff/ผลทดสอบ, Codex review และส่งแก้จนพร้อมให้ Owner ตัดสินใจ.

```bash
python3 tools/claude_dev.py --check
```

ตั้งค่า canonical root ครั้งแรกและส่งงานพร้อม baseline/write paths ตาม [WORKFLOW](docs/WORKFLOW.md). ตัวเรียกตรวจ tree/branch/HEAD/งานค้างและ lock, จำกัดเครื่องมือและ sandbox ของ tests. Local config, prompts และ raw results ไม่ขึ้น Git. ผล invocation สำเร็จไม่แทน tests หรือ acceptance.

อัปเดต STATUS/DECISIONS ใน local ระหว่างพัฒนา; commit/push ที่ checkpoint ที่ตรวจแล้วแทนการ sync ทุกข้อความ. Default launcher ไม่เปิด git-write/GitHub tools; PO จัด checkpoint บน branch งานและตรวจ remote read-back. ไม่มี auto merge/deploy/worker/scheduler หรือสิทธิ์กล้องใหม่.
