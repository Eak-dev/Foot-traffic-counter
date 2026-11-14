# Prompt ส่งต่อ Foot traffic counter ไปเครื่องใหม่

คัดลอกตั้งแต่ “เริ่ม prompt” ถึง “จบ prompt” ไปวางใน Codex ที่เปิดโฟลเดอร์โปรเจกต์บนเครื่องใหม่ได้เลย หรือแนบไฟล์นี้แล้วสั่งให้ Codex อ่านและทำตามทั้งหมด เอกสารนี้ไม่มีรหัสผ่าน token ภาพ วิดีโอ หรือค่าตั้งกล้องจริง

## เริ่ม prompt

คุณคือ Codex ทำหน้าที่ PO และผู้รับผิดชอบย้ายโปรเจกต์ Foot-traffic-counter มายังเครื่องนี้ เจ้าของงานชื่อคุณ Eak สื่อสารภาษาไทย เป้าหมายคือจัดเตรียมเครื่องใหม่ ติดตั้งสิ่งที่จำเป็น ตรวจและแก้ปัญหาที่ค้าง ทำงานกับ Claude Code แล้วทดสอบการนับคนด้วยหลักฐานว่าถูกต้องและเร็วขึ้น ใช้ข้อมูลใน prompt นี้เป็นบริบทส่งต่อ แต่ตรวจไฟล์และสถานะจริงอีกครั้งก่อนลงมือ

Owner ยืนยันแล้วว่าเครื่องใหม่เป็น **Mac ชิป Apple Silicon** ให้เลือก arm64 native เป็นหลัก ตรวจรุ่นชิป/RAM/macOS จริงเอง ไม่ต้องถาม OS ซ้ำ และไม่ใช้สเป็ก Intel ของเครื่องเดิมเป็นสเป็กปลายทาง

ทำงานที่เตรียมได้ต่อเนื่องจนพร้อมใช้งาน อย่าจบแค่เสนอแผนหรือรายชื่อคำสั่ง คุณได้รับมอบหมายให้จัดสภาพแวดล้อม local ติดตั้งซอฟต์แวร์ฟรีที่จำเป็นในขอบเขตโปรเจกต์ แก้โค้ดเพื่อรองรับเครื่องใหม่และแก้ blocker ทดสอบ และจัดคู่มือใช้งาน ไม่ซื้อบริการ/สมัครแพ็กเกจเสียเงิน ไม่เปลี่ยนบัญชี เครือข่าย router การตั้งค่ากล้อง หรือ power settings โดยอัตโนมัติ ใช้สิทธิ์พัฒนาที่มีอยู่ตาม control ล่าสุด และรักษาขอบเขตข้อมูลส่วนตัว

ถ้าขาดข้อมูลที่จำเป็น ให้ถามเฉพาะรายการนั้นพร้อมอธิบายว่าจะใช้ทำอะไร แล้วทำงานส่วนที่ไม่ติดข้อมูลต่อ อย่าขอรหัสผ่าน OTP token หรือไฟล์ key ในแชต ขั้นที่ต้องให้ Owner ยืนยันตัวตน ให้ใช้ browser/native dialog/terminal ที่ Owner ป้อนเองในเครื่อง ไม่เปิดใช้งานกล้องหรือเริ่มวันใหม่โดยตีความสิทธิ์ติดตั้งเป็นสิทธิ์เข้าถึงกล้อง

### 1. รับ checkout และตรวจสถานะก่อนแก้

- Repository: https://github.com/Eak-dev/Foot-traffic-counter
- Branch งานที่ตรวจไว้: `claude/ft-d0-preflight`
- HEAD ที่ตรวจทั้งเครื่องเดิมและ remote เมื่อ 2026-11-14 ก่อนจัดชุดส่งต่อนี้: `32f889c7aa9ea30902a5f1d9381179f29542c6d3`
- Commit โค้ด CoreML ที่เริ่ม OD71: `0d53c5a8da07c9593e97ca1666443c7062bc5bb6`
- PR ที่เกี่ยวข้อง: https://github.com/Eak-dev/Foot-traffic-counter/pull/4 ตรวจสถานะปัจจุบันเอง อย่าสมมติว่ายังเปิดอยู่
- Remote อาจมี commit เอกสารส่งต่อเพิ่มจาก HEAD ข้างต้น ให้ตรวจ ancestry/diff และใช้สถานะล่าสุดที่ตรวจแล้ว ไม่ reset กลับ hash เก่าโดยอัตโนมัติ

ถ้าไม่มี checkout ให้ clone branch งานลงโฟลเดอร์ใหม่ที่ไม่มีไฟล์เดิมและอยู่นอกโฟลเดอร์ sync สื่อส่วนตัว เช่นเลือกโฟลเดอร์ Projects ของผู้ใช้ คำสั่งตัวอย่างสำหรับปลายทางว่าง:

```sh
git clone --branch claude/ft-d0-preflight https://github.com/Eak-dev/Foot-traffic-counter.git Foot-traffic-counter
cd Foot-traffic-counter
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short --branch
```

ถ้ามี checkout แล้ว ให้ตรวจงานค้างก่อน ห้าม clone ทับ switch/pull/reset/clean หรือแยก worktree/branch เพิ่มเอง ใช้ checkout และ branch เดียวกันกับ Claude หนึ่งผู้แก้ไฟล์ต่อครั้ง

อ่านตามลำดับ: `AGENTS.md`, `docs/PO_OPERATING_BRIEF.md`, `PROJECT_CONTROL.md`, `docs/PLAN.md`, `docs/PREPROJECT_PLAN.md`, `docs/STATUS.md`, `docs/DECISIONS.md`, `docs/WORKFLOW.md` จากนั้นอ่าน `docs/DAY_COUNTING.md`, `docs/EXACT_RESUME.md`, `docs/PERFORMANCE.md`, `docs/ZONE_COUNTING.md`, `docs/FRONT_LANES.md`, `docs/THIRD_PARTY_NOTICES.md` ตามงาน

อ่าน `.claude/delivery.local.json` เฉพาะส่วนที่จำเป็นถ้ามีไฟล์ส่งต่อที่ Owner เตรียมไว้ ห้ามพิมพ์ทั้งไฟล์ออกมาเพราะอาจมีข้อมูลส่วนตัว ไฟล์นี้ถูก ignore จึงไม่มาจาก Git clone และ prompt นี้สรุปสถานะสำคัญไว้แล้ว เอกสารเก่าบางส่วนยังเขียน FT-D0/READY_TO_START/48h ให้ดู Owner decision และลำดับเวลาล่าสุด ไม่ใช้ประวัติเก่าลบล้างผลจริง

### 2. ระบบนี้ทำอะไร

- ดึงคลิปบันทึกจาก SD ของกล้อง Tapo ที่ร้านแบบเป็นชุด ผ่านเส้นทางที่โปรเจกต์ตรวจแล้ว แล้วประมวลผลในเครื่อง ไม่ใช่ระบบนับ live/RTSP
- ใช้เฉพาะ Fixed Lens; PT Lens ไม่ใช่มุมทดแทน ต้องตรวจ lens/geometry/timezone ของสื่อจริง
- หน้าร้านมี near lane, far lane, accepted รวม และ `front_review`; ข้างร้านมี `shop_side` และ `shop_side_review`
- นับเหตุการณ์เดินผ่าน/เข้าโซนตามกฎเดิม ไม่ใช่จำนวนคนไม่ซ้ำ ไม่บวกสองโซนเป็นคนไม่ซ้ำ ไม่ใช้ face recognition, appearance embeddings, ฐานข้อมูล, เว็บเซิร์ฟเวอร์ หรือ Docker
- Baseline คือ YOLOX_s ONNX + ONNX Runtime + OpenCV + supervision ByteTrack, sample 5 fps และ geometry/counters เดิม
- CoreML ตัวใหม่ใช้ FP32, person-output, batch 2 โดยรวม crop ของสองโซนจาก sampled frame เดียวกัน แต่เก็บ tracker/history แยก ใช้ `tools.ft_day_count_accel` และตัวเลือก backend ใน day driver; CPU ยังเป็นค่า default
- Source ปัจจุบันตั้ง CoreML `MLComputeUnits=CPUAndGPU` และ MLProgram FP32 ไม่ได้เลือก Neural Engine ให้คงตัวเลือกนี้เป็นการเทียบ baseline ก่อน การลอง ALL/ANE/FP16 เป็น candidate แยกที่ต้องวัดและตรวจคุณภาพ ไม่เปลี่ยนเงียบ ๆ
- ห้ามลด fps, ลด resolution, เปลี่ยนโมเดล, threshold, geometry หรือกฎนับแล้วอ้างว่าความเร็วดีขึ้นโดยไม่มีการเปรียบเทียบเหตุการณ์และคุณภาพ

### 3. สถานะค้างที่ต้องรู้

OD71 ทดลองวันที่คลิป 2026-10-17 บน Mac เดิม Intel i7-4870HQ / RAM 16 GB / macOS 14.8.9 x86_64:

- เริ่ม 2026-10-20T13:25:56.576623Z; หยุด 2026-10-20T17:36:30.597870Z หลัง 4:10:34
- สถานะสุดท้าย `BLOCKED`, `reason=CHECKPOINT_MISMATCH`, `diagnostic=null` ตอนเข้าสู่ batch 5 หลัง commit 48 คลิป
- นับแล้ว 48/503 คลิป เหลือ 455; วิดีโอที่ประมวลผลรวม 7,444 วินาที = 2:04:04
- ช่วงหลักฐานเวลาไทย: 07:06:01–08:43:43 และ 11:29:23–11:55:45
- near 363; far 372; front accepted 735; front_review 113; side accepted 615; side_review 0
- ตอนตรวจหยุดไม่พบ supervisor/driver/worker เหลือ; แฮช source 18 ไฟล์ตรง และ `read_checkpoint` ตรวจ checksum/runtime/reference ผ่าน แต่ยังไม่ได้พิสูจน์ว่าส่วนใดทำให้เกิด `CHECKPOINT_MISMATCH` ห้ามเดาว่าไฟล์เสียหรือ token หมดอายุ
- Automation 10 ของเครื่องเดิม PAUSED แล้ว อย่าคัดลอก automation/thread ID นี้มาเปิดบนเครื่องใหม่
- เวลาเฉลี่ยรวมทั้งรอบประมาณ 5:13 ต่อคลิป; คลิปยาวเฉลี่ย 2:35 ตัวเลขนี้รวม overhead/download/process/report ไม่ใช่เฉพาะเวลา inference และใช้ทำนายทั้งวันตรง ๆ ไม่ได้
- Benchmark ก่อนหน้านี้ 6 คลิปรวม 858 วินาที: 4,290 sampled frames ต่อ backend, 143 event semantics ตรงกัน CPU processing 2735.515s → CoreML 2026.157s ลด 25.931%; worker CPU core-seconds 10380.292 → 719.858 ตัวเลขนี้ไม่ใช่พลังงานทั้งเครื่องหรือความแม่นยำที่คนตรวจ
- Inventory เดิมที่ตรวจ 2 รอบจนหน้าว่าง: 503 คลิป, 63,929 วินาที (17:45:29), 166 ช่วงต่อเนื่อง ขอบเขต 00:04:05–23:51:53 แต่ยังไม่พิสูจน์ว่าคลิปต้นฉบับครบ 24 ชั่วโมง
- บั๊ก pagination ที่เคยหยุดเมื่อหน้ามีรายการน้อยกว่า 20 ถูกแก้แล้ว ต้องอ่านต่อจนหน้าว่างพร้อม guard ไม่เอารอบเก่า 58 คลิปหรือ CPU 64/503 มารวมกับ CoreML

ค่าอ้างอิงประวัติ OD71 เท่านั้น:

```text
reference_sha256 = 8beb7a4286247ba808f042fad3cb0f79e7cf49a41d696b6a50a1c83211d71b59
count_runtime = 6d48e2f40a75238e5b6cd094a9586db9472109114f63696dac47be96cb4ef401
count_backend = coreml
```

เมื่อ 2026-11-14 ตรวจพบว่าโฟลเดอร์งานชั่วคราวชื่อ `ft-day-20261017-coreml-501`, log ของงานนี้ และชุดสื่อ/validation ชั่วคราว OD69–OD71 ที่บันทึก path ไว้ ไม่อยู่ที่เดิมแล้ว ไม่ทราบสาเหตุที่หาย ห้ามสร้าง ledger/checkpoint ขึ้นจากยอดสรุป หรืออ้างว่ามีสื่อครบ 503 คลิปพร้อมรันต่อ หาก Owner มี backup ให้ใช้สำเนาเพื่อวิเคราะห์เท่านั้น; หากไม่มี ให้สร้าง reproducer แบบ synthetic และเริ่ม lineage ใหม่เมื่อ input ที่จำเป็นพร้อม

### 4. ตรวจเครื่องใหม่และเลือกการติดตั้ง

ตรวจ OS/version, CPU architecture, RAM, พื้นที่ว่าง, Python, Git, compiler, ffmpeg/ffprobe, uv, Claude CLI และ Codex ที่มีอยู่ บันทึกเฉพาะข้อมูลที่จำเป็น ไม่สำรวจโฟลเดอร์บ้านหรือ secret stores โดยกว้าง

- macOS Apple Silicon: ใช้ Python และ binary แบบ arm64 native ตรวจ `platform.machine()`/ชนิด executable อย่าใช้ x86_64 ผ่าน Rosetta โดยไม่ตั้งใจ
- macOS Intel: ใช้ x86_64 native ทดสอบ CoreML provider จริงอีกครั้ง ไม่ถือว่าชื่อ provider รับรอง GPU/ANE ที่ใช้งาน
- Windows/Linux: โค้ดปัจจุบันพึ่ง macOS Keychain, `sandbox-exec`, native helper, `fcntl` และคำสั่งเฉพาะระบบ จึงไม่ใช่การติดตั้งแล้วรันเต็มระบบได้ทันที ทำงานเอกสาร/ทดสอบส่วนที่รองรับต่อได้ แต่ระบุงานพอร์ตที่ต้องทำและทดสอบ อย่าปิด network sandbox เพื่อให้ผ่าน และอย่ารับรอง CoreML บนระบบที่ไม่รองรับ

ติดตั้งเฉพาะรายการที่ขาด ตรวจเอกสารทางการล่าสุดและความเข้ากันได้ ไม่อัปเกรดทุกอย่างพร้อมกันจนเทียบ baseline ไม่ได้:

1. **Codex**: ถ้ากำลังรับ prompt นี้ใน Codex ที่ใช้งานได้แล้ว ไม่ต้องลงซ้ำ ใช้ desktop หรือ CLI ตามเครื่อง; CLI เป็นตัวเลือก ไม่บังคับติดตั้งทั้งคู่ เจ้าของลงชื่อเข้าใช้เอง เอกสาร https://learn.chatgpt.com/docs/codex/cli และ https://learn.chatgpt.com/docs/quickstart
2. **Git**; **GitHub CLI `gh`** เป็นเครื่องมือช่วยตรวจ PR/publish ใช้บัญชีที่ Owner มีอยู่ ไม่สร้างบัญชีหรือรับ token ในแชต
3. **Claude Code CLI** สำหรับงาน Dev ตาม workflow ติดตั้งจาก https://code.claude.com/docs/en/quickstart ตรวจ `claude --version` และสถานะบัญชีผ่านช่องทางทางการ เจ้าของ sign in เองหากจำเป็น ไม่อ้างว่า Claude ทำงานเมื่อไม่ได้เรียกจริง
4. **Xcode Command Line Tools บน Mac** สำหรับ git/compiler/native Keychain helper ตรวจ `xcode-select -p`, `xcrun --find clang`, `codesign` ก่อน ถ้าต้องติดตั้งและมีหน้าต่างยืนยันของ OS ให้ Owner ทำเฉพาะขั้นที่เครื่องมือทำแทนไม่ได้
5. **uv** จาก https://docs.astral.sh/uv/getting-started/installation/ เครื่องเดิมใช้ 0.12.23; ติดตั้งเวอร์ชันที่รองรับเครื่องและบันทึก version ไม่ติดตั้ง package ลง system Python
6. **Python**: เครื่องมือควบคุมเป็น Python 3.9+ standard library แต่ inference ที่ตรวจจริงใช้ CPython **3.13.16** ทั้งสาม environment เริ่มด้วยเวอร์ชันนี้แบบ native ถ้าหา distribution/wheel ไม่ได้ ให้เลือกเวอร์ชันที่เข้ากันได้พร้อม lock ใหม่และทดสอบ ห้ามแอบเปลี่ยน version แล้วใช้ checkpoint เก่า
7. **FFmpeg และ FFprobe**: เครื่องเดิม 9.0.2; แหล่ง binary ผ่าน https://ffmpeg.org/download.html ตรวจ architecture/provenance/version/capabilities และวางให้พบที่ `.venv/ft-media-bin/ffmpeg` กับ `.venv/ft-media-bin/ffprobe` ซึ่ง source ปัจจุบันอ้างตรง ๆ ห้ามคัดลอก binary Intel ไปใช้กับ ARM โดยไม่ตรวจ ใช้ binary/symlink ที่ชี้ของเครื่องใหม่นี้เท่านั้น
8. **ripgrep `rg`** ช่วยค้นโค้ด; **Homebrew** เป็นตัวเลือกติดตั้งเครื่องมือเมื่อเหมาะสม ไม่ใช่ข้อบังคับของ runtime; **Node/npm** ต้องมีเฉพาะเมื่อเลือก installer ที่ใช้ npm ไม่ใช่ dependency ของโปรแกรมนับคน

### 5. Python libraries และ environments

อย่าคัดลอก `.venv` หรือ compiled CoreML cache จากเครื่องเดิม สร้าง environment ใหม่และ pin packages แยก ใช้ชื่อ environment ตามที่ day driver อ้าง:

| Environment | จุดประสงค์ | รายการหลัก |
| --- | --- | --- |
| `.venv/ft-counting` | CPU reference | `opencv-python==4.11.0.86`, `numpy==2.2.6`, `supervision==0.26.1`, `scipy==1.15.3`, `onnxruntime==1.23.2` |
| `.venv/ft-accel` | CoreML FP32 batch2 | counting baseline + `onnx==1.19.1`, `ml_dtypes==0.5.4`, `typing_extensions==4.15.0` |
| `.venv/ft-acquisition` | ไลบรารีเส้นทางดึง/งานเดิมที่จำเป็นต้องใช้ | `pytapo==3.4.26`, `aiofiles==25.1.0` และ transitive packages ใน acquisition lock |

`requirements-counting.in` และ `requirements-counting.lock` อยู่ใน Git; lock มี 29 packages พร้อม hashes ใช้ lock เต็ม ไม่ติดตั้งเฉพาะ 5 ชื่อแล้วถือว่าครบ ตรวจ resolver และ `uv pip check` ทุก environment

ตัวอย่างการสร้าง CPU environment ใหม่เมื่อ path ยังไม่มี:

```sh
uv python install 3.13.16 --no-bin
uv venv --python 3.13.16 .venv/ft-counting
uv pip sync --require-hashes --only-binary :all: --python .venv/ft-counting/bin/python requirements-counting.lock
uv pip check --python .venv/ft-counting/bin/python
```

บนเครื่องใหม่ให้ตรวจคำสั่ง/version จาก `uv --help` ก่อน ถ้า environment มีงานอยู่ ห้ามลบทิ้งหรือ sync ทับโดยไม่ตรวจ เนื่องจาก sync ลบ package ที่ไม่อยู่ใน lock ได้ [อ้างอิง uv](https://docs.astral.sh/uv/pip/compile/)

สำหรับ CoreML สร้าง `.venv/ft-accel` ด้วย Python native เดียวกัน สร้าง requirements/lock รวม counting pins และ 3 packages เพิ่มโดยใช้ counting lock เป็น constraints; ตรวจ compatibility และ generate hashes สำหรับ platform เป้าหมายก่อน sync ไม่ sync เฉพาะไฟล์ 3 packages จน counting dependencies ถูกลบ เก็บ input/lock/provenance ที่สร้างอย่างชัดเจน

ตัวอย่างเมื่อ `.venv/ft-accel` ยังไม่มี และใช้ชื่อ lock ใหม่ที่ไม่ทับงานเดิม:

```sh
uv venv --python 3.13.16 .venv/ft-accel
uv pip compile requirements-counting.in docs/migration/requirements-coreml-extra.in --constraint requirements-counting.lock --python .venv/ft-accel/bin/python --only-binary :all: --generate-hashes --output-file .venv/requirements-coreml-arm64.lock
uv pip sync --require-hashes --only-binary :all: --python .venv/ft-accel/bin/python .venv/requirements-coreml-arm64.lock
uv pip check --python .venv/ft-accel/bin/python
```

เครื่องเก่ามี `openvino==2025.4.1` และ `openvino-telemetry==2025.2.0` เพิ่มสำหรับการทดลอง รวม accel เดิม 34 packages แต่ **ไม่ใช่สิ่งจำเป็นสำหรับเส้นทาง CoreML** ลงเฉพาะเมื่อจะทดสอบ OpenVINO และมี wheel รองรับเครื่อง; wheel เดิมเป็น cp313/macOS/x86_64 ห้ามนำไปใช้บน ARM จำนวน packages และ runtime digest ใหม่อาจต่างจากเดิมโดยชอบธรรม ต้องบันทึก ไม่ปลอมให้ตรงของเก่า

ในชุดเอกสารส่งต่อนี้มี `docs/migration/requirements-acquisition.lock` เป็นสำเนา lock ของเครื่องเดิมและ `docs/migration/observed-environments.txt` เป็นรายการ package/version ที่ตรวจจริง ข้อมูลเหล่านี้เป็น baseline ไม่รับประกันว่ามี wheel สำหรับทุก OS/architecture ถ้า lock ใช้ไม่ได้ ให้ทำ lock ใหม่จาก pins ที่จำเป็นโดยบันทึกความต่างและทดสอบ ไม่ถอด hash verification เพื่อเลี่ยงปัญหา

โปรเจกต์ปัจจุบันใช้ native vendor relay helpers สำหรับ day acquisition; ไม่ต้องเรียก constructor/integration tests ของ pytapo เพียงเพื่อพิสูจน์การติดตั้ง เพราะอาจเปลี่ยนค่ากล้อง ตรวจ dependency/import ตาม scope ที่ไม่มี network เท่านั้น ไม่ต้องเพิ่ม `torch`, `ultralytics`, `gspread`, `google-auth`, `coremltools`, CUDA, Docker หรือเว็บเซิร์ฟเวอร์เพื่อทำให้ baseline นี้รัน

### 6. โมเดลและไฟล์ส่วนตัวที่ Git ไม่มี

โมเดลหลักที่ source ตรวจ hash ก่อนใช้:

```text
path in repo ignored runtime: .venv/ft-models/yolox_s.onnx
size: 35858002 bytes
sha256: c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063
source: OpenCV Zoo commit 47534e27c9851bb1128ccc0102f1145e27f23f98
license: Apache-2.0; see docs/THIRD_PARTY_NOTICES.md
```

ดาวน์โหลด ONNX จากแหล่ง/commit ที่เอกสารระบุหรือใช้สำเนาที่ Owner จัดเตรียม ตรวจ byte size และ SHA256 อย่านำ Git LFS pointer มาใช้เป็น model และไม่เปลี่ยนเป็นรุ่นชื่อคล้ายกัน สร้าง person-output/batch2 derivative ด้วย helper ของ repo แล้วบันทึก hash ใหม่ อย่าย้าย compiled CoreML cache ข้ามเครื่อง

ทำรายการ private inputs ที่ต้องใช้ แล้วตรวจเฉพาะโฟลเดอร์ที่ Owner ระบุ:

- zones/count config จริงตามกฎ v4 และ reference ภาพ Fixed Lens ที่ตรวจ hash/geometry แล้ว
- คลิป Fixed ที่ Owner มีสิทธิ์ใช้ และสื่ออ้างอิง/expected events สำหรับ benchmark; แยกจากผลรายงานตัวเลข
- config target/connection เช่น `config.local.cloud-target.json` และ `config.local.connection.json` เฉพาะถ้าต้องทดสอบ acquisition
- ledger/checkpoint/log redacted ของงานเก่า ถ้ามี backup; เก็บเป็นหลักฐานอ่านอย่างเดียว ไม่ใช้เป็น state ของ backend/เครื่องใหม่
- `.claude/delivery.local.json` หรือสรุปสถานะที่ตัดข้อมูลส่วนตัวแล้ว; `.claude/workflow.local.json` ต้องสร้างใหม่ตาม root เครื่องนี้
- `FootTraffic-Day-2026-10-17-COREML-PARTIAL.html` และ `.csv` ถ้า Owner ต้องการเก็บรายงานเก่า ผลเดิมอยู่ใน iCloud Drive/FootTrafficReports ณ วันหยุดงาน แต่ตรวจว่ามีจริงในเครื่องใหม่เอง

ห้ามถือว่า Git clone จะได้ไฟล์เหล่านี้ ห้ามสร้าง geometry/hash/label ปลอมจาก prompt ถ้าขาด reference/config/media ต้องระบุรายการที่ขาดตรง ๆ และทำ synthetic/setup/debug ต่อได้ ค้น backup เฉพาะที่ Owner ชี้ ไม่ค้นทั้งเครื่อง/Cloud ของ Owner เอง

Owner เป็นผู้ย้าย private files ผ่านช่องทางที่ควบคุมเอง ไม่แนบภาพ วิดีโอ config state หรือ credentials เข้า Codex/Claude chat, GitHub, plugins หรือ third-party upload ให้ agent ประมวลผลบน disk และส่งกลับเฉพาะตัวเลข/แฮช/diagnostic ที่ redacted

ใช้โฟลเดอร์ข้อมูลถาวร private อยู่นอก Git และ cloud sync พร้อม directory0700/files0600 อย่าใช้ `/tmp` เป็นที่เก็บหลักของผลที่ต้องอยู่ข้ามวัน ไม่ทิ้ง retention/quota เดิม: ตรวจพื้นที่สำรองอย่างน้อย10GiB, ขอบเขต staging/job ตาม source และแผน retention ที่ Owner อนุมัติ ถ้าจะปรับที่เก็บ/โควตาต้องทำอย่างชัดเจนพร้อม tests ไม่เลี่ยง guard

### 7. Keychain และ session บนเครื่องใหม่

การติดตั้ง/development/offline benchmark ไม่ต้อง login กล้อง ส่วน acquisition จริงต้องผ่านขั้น private session ของโปรเจกต์ ตรวจ `docs/SESSION_48H_GUIDE.md`, `tools/ft_session.py`, `tools/native/ft_keychain.m` โดยใช้ OD65 ล่าสุดเหนือชื่อเอกสารเก่า

- เก็บ token ใน macOS login Keychain ผ่าน native helper ไม่เขียน plaintext `.env`/JSON และไม่ export ทั้ง Keychain เพื่อย้ายเครื่อง
- ไม่คัดลอก session/token ของเครื่องเดิมโดยสมมติว่า ACL/device binding ใช้ต่อได้
- สร้าง helper บน Mac ใหม่ด้วย clang/Foundation/Security และตรวจ signature/permissions ตามคู่มือ ที่อยู่ runtime เป็น `~/.local/share/foot-traffic-counter/bin/ft-keychain` สร้างให้ตรง source; ห้ามสั่ง helper load แล้วพิมพ์ secret ออกมา
- ถ้า helper ใหม่ยังไม่มี session และขั้น live ที่ Owner อนุมัติต้อง login ให้เตรียม private native flow และให้ Owner ป้อนเองในเครื่อง ถ้า Keychain ถูกปฏิเสธ ให้รายงานจริง ไม่ปลดล็อก/เพิ่มสิทธิ์ทั้งระบบอัตโนมัติ
- ใช้ vendor-managed bounded auto refresh ตามโค้ดเดิม ไม่มีเพดาน token48h/7d/30d ที่เราตั้งเอง อายุจริง vendor ยังไม่ทราบ; explicit401-only/one-refresh/one-replay และ guard อื่นต้องคงอยู่
- เพดาน supervisor72h/2cycles/1000windows เป็นขอบเขตงาน ไม่ใช่อายุ token; แยกจาก deadline ของ driver/clip อื่นตาม source
- อย่าสรุป token หมดอายุจากเวลา/timeout/network error และไม่สั่ง refresh/login เพียงเพื่อทดสอบการติดตั้ง

### 8. ตั้งค่า Codex กับ Claude และ plugins

Codex ทำ PO: ตรวจ control/แตกงาน/จัด ownership/ทดสอบอิสระ/ส่ง checkpoint; Claude ทำ Dev ตามใบงาน ผ่าน `tools/claude_dev.py` ไม่ใช่เปิดสอง agent แก้ไฟล์เดียวกันพร้อมกัน

1. สร้าง `.claude/workflow.local.json` จาก canonical root ของเครื่องนี้ตาม schema ใน `docs/WORKFLOW.md` ใช้ branch จริง เลือก model ที่บัญชี Claude มีสิทธิ์ใช้งานจริงและอยู่ในขอบเขตค่าใช้จ่ายที่ Owner ยอมรับ ไม่คัดลอก path เครื่องเก่า ตัวอย่างเดิมใช้ `claude-sonnet-5`, `max_budget_usd:6` แต่ไม่ใช่สิทธิ์สมัคร/เพิ่มวงเงินใหม่
2. ตรวจ tracked `.claude/dev-policy.json`; `.env.example`/`config.example.yaml` เป็น LEGACY/NOT_USED ไม่ใช่ setup template
3. ใช้ `python3 tools/claude_dev.py --check` และ `--help` ตั้ง task baseline/full HEAD/write paths/tests/timeout ตาม workflow; รับทราบ dirty files แยกจากสิทธิ์แก้ ไม่เพิ่ม scope ด้วย `--allow-dirty`
4. ไม่คัดลอก `dev.lock`, task execution/session IDs หรือ raw results จากเครื่องเก่ามาเป็นงานที่กำลังรัน หาก lock ค้าง ให้ตรวจ ownership ก่อน ไม่แย่ง lock
5. ถ้า Claude CLI/login/model/permission ติด ให้รายงานสถานะจริงและทำส่วน PO ที่ทำได้ต่อ ไม่แต่งว่าได้ร่วมกับ Claude แล้ว และไม่ปิด permission guard เพื่อหลบ error

**Plugins/MCP:** runtime นับคนและ launcher นี้ไม่ต้องมีปลั๊กอินภายนอก Claude launcher ใช้ strict empty MCP config และปิด slash commands/Chrome ตาม policy ไม่แก้ข้อจำกัดนี้เพื่อ setup

- GitHub connector เป็นทางเลือก; Git/gh ก็ตรวจโค้ด/PR ได้
- OpenAI Docs skill หรือ docs MCP เป็นทางเลือกสำหรับค้นคู่มือสาธารณะ ไม่ใช่ dependency ของระบบนับคน ถ้าต้องใช้ CLI และยังไม่มี สามารถตั้งตาม https://developers.openai.com/learn/docs-mcp แล้วตรวจ `codex mcp list`; ห้ามติดตั้งซ้ำโดยไม่ตรวจ
- ไม่ต้องติดตั้ง Adobe, Higgsfield, Cloudflare, Google Drive, Notion, Pages, Remotion, Sites, Work Pets หรือ spreadsheet plugins เพื่อรันโปรเจกต์นี้
- ไม่คัดลอก Codex/Claude global config หรือ credentials ทั้งโฟลเดอร์จากเครื่องเก่า; ใช้บัญชี/การตั้งค่าอย่างเป็นทางการของเครื่องใหม่

### 9. แก้ blocker และตรวจ portability ก่อนทดสอบจริง

อย่ากด resume งานเก่าทันที Runtime identity ผูก source/model/config/reference/Python/packages/platform การเปลี่ยนเครื่องหรือแก้ source ต้องใช้ lineage/root/cache/ledger ใหม่; ห้ามแก้ hash ใน checkpoint ให้ guard ยอมรับ

วิเคราะห์ `CHECKPOINT_MISMATCH` จาก `tools/ft_day_run.py`, `tools/ft_day_state.py`, `tools/ft_day_count.py`, `tools/ft_day_count_accel.py`, `tools/ft_state_codec.py` และ tests ที่เกี่ยวข้อง โดยแยก integrity/readability ออกจากความสอดคล้องทาง semantic/coverage/source/ref/backend

สร้าง reproducer local/synthetic ที่ครอบคลุมหลาย batch โดยเฉพาะการจบ batch4→เริ่ม batch5 และการสลับ continuous group ในลำดับ daytime-first ตรวจ cursor/prefix coverage/group boundary/clock/tracker carry/snapshot pruning/atomic commit/runtime identity โดยถือเป็นจุดตรวจ ไม่ใช่สาเหตุที่พิสูจน์แล้ว ถ้ามีสำเนา checkpoint จริง ให้ตรวจบนสำเนา; ถ้าไม่มี ให้บอกว่าการพิสูจน์สาเหตุของเหตุการณ์เดิมยังมีข้อจำกัด

ทำ regression tests ก่อน/พร้อมแก้ ให้เหตุผลและ diagnostic ที่ redacted ชัดขึ้นโดยไม่แสดง state/path/token รักษาการปฏิเสธ runtime/backend/ref ที่ผิด และตรวจว่าการปฏิเสธไม่แตะ session/download/ledger เก่า

ทุกการแก้ต้องอยู่ในใบงาน/write paths ชัดเจน source ที่กำลังใช้โดยงานจริงต้อง frozen; ถ้าพบงานกำลังรันในเครื่องนี้ ให้แยกงานอ่าน/เอกสารก่อน ไม่แก้ runtime ขณะนับ

### 10. ลำดับทดสอบและเกณฑ์พร้อมใช้งาน

ทำทีละขั้นและเก็บ exit code/version/hash/result จริง ไม่ถือว่าติดตั้งสำเร็จเพราะ import ผ่านอย่างเดียว:

1. ตรวจ binary architecture, Python dependencies, `uv pip check`, FFmpeg/FFprobe capabilities และ ONNX model size/hash
2. ตรวจ ORT providers และทำ CPU/CoreML smoke test จริงภายใต้ network sandbox โดยไม่มีสื่อส่วนตัวออกนอกเครื่อง แยก provider available ออกจาก provider ที่ถูกใช้; ห้าม fallback เงียบแล้วเรียกว่า CoreML
3. รัน baseline ที่ repo กำหนด:

```sh
python3 -m unittest discover -s tests -t . -v
```

   แล้วรัน suite ใน dependency-backed environment ที่จำเป็นเพื่อครอบคลุม optional modules ที่ถูก skip เช่น `.venv/ft-accel/bin/python -m unittest discover -s tests -t . -v` ใช้ `tests/test_ft_day_count_accel.py`, `tests/test_ft_day_state.py`, `tests/test_ft_day.py`, `tests/test_ft_day_job.py`, `tests/test_ft_count_runtime.py`, `tests/test_ft_state_codec.py` และ perf tests ตามสิ่งที่แก้ ตรวจชื่อจริงก่อนเรียก ไม่รัน integration tests ของ external SDK ที่ต่อกล้อง

4. หลักฐานเก่า OD71: 1067 stdlib tests =931PASS/136optionalSKIP; dependency-backed201PASS/0SKIP และ Python3.9 AST/diff checks ผ่าน เป็นประวัติ ไม่ใช่ผลของเครื่องใหม่ รายงานจำนวน PASS/FAIL/SKIP ที่ได้จริง
5. Synthetic split/resume/new-process/crash/atomicity/overlap/time-gap/midnight และ multi-batch tests ต้องผ่าน รวม cross-runtime/backend/reference rejection แบบไม่ทำลายหลักฐาน
   จากนั้นต้องทดสอบ native runtime และ actual day-driver path บน arm64 ด้วย local lossless fixture ที่ตรวจว่า decoded pixels/clock เทียบกันได้ เช่น 20 วินาทีแบ่งเป็นสองส่วน 10 วินาที เทียบสองส่วนใน worker เดียวกับสองส่วนที่เขียน checkpoint แล้วเปิด process ใหม่: event fields และ encoded active tracker/counter state ต้องตรงกัน เทียบกับ full fixture ตาม semantics/time และอธิบาย boundary-clock exceptions ที่ตรวจพบ; ทดสอบ wrong-backend/reference rejection ว่าไม่แก้ไฟล์และไม่เรียก session/download ใช้ local fixtures/stub acquisition โดยไม่ติดต่อกล้อง หากไม่มี media/config/reference ที่ใช้ทำ native proof ให้คงเกตนี้เป็น PENDING ไม่ใช้ synthetic PASS แทนความพร้อมรันเต็มวัน
6. ถ้ามี private clips/config/reference ที่ Owner เตรียมพร้อม ให้ benchmark offline คลิปเดียวกัน CPU เทียบ CoreML บนเครื่องใหม่ โดย input/model/config/5fps เหมือนกัน ใช้ harness `tools/ft_perf_accel.py`, `tools/ft_perf_compare.py`, `tools/ft_perf_metrics.py` ตาม `--help` และ PERFORMANCE; รันทีละ worker มี warm-up และวัดซ้ำในภาวะใกล้กัน ห้ามดาวน์โหลดคลิปใหม่โดยไม่ผ่าน live scope

   ตัวอย่าง synthetic smoke commands หลัง model/environment พร้อม ให้แทน output ด้วย path ใหม่ใน private root ที่เลือกไว้:

```sh
.venv/ft-accel/bin/python -m tools.ft_perf_accel --backend ort --kernel legacy --threads 4 --synthetic --iterations 12 --output <fresh-private-cpu-output>
.venv/ft-accel/bin/python -m tools.ft_perf_accel --backend coreml --kernel cached --person-output --batch-size 2 --precision fp32 --threads 4 --synthetic --iterations 12 --output <fresh-private-coreml-output>
```

   Synthetic smoke มีหน้าที่ตรวจ runtime ไม่ใช่หลักฐานความแม่นยำหรือความเร็วการนับคนในคลิปจริง อย่า execute เครื่องหมาย `<...>` ตรง ๆ ให้เลือก path จริงและ quote ให้ถูกก่อน
7. เทียบ event-level: near/far/front accepted/front_review/side accepted/review, direction, timestamps, review reasons, checkpoint/active state ที่ควรต่อเนื่อง ไม่ดูเพียงยอดรวมเท่ากัน เลือกคลิปเช้า/กลางวัน/เย็น คนหนาแน่น/บังกัน/ไม่มีคนตามสื่อที่มี
8. รายงาน download/remux/model setup/inference/tracking/checkpoint/report/end-to-end แยกกัน; wall time, CPU core-seconds, peak RSS, input duration, frames, repeats, median/range บอกถ้า GPU/energy/temperature ยังไม่ได้วัด ห้ามเรียก worker CPU ว่าไฟทั้งเครื่อง
9. ความตรงกับ CPU เป็น compatibility ไม่ใช่ human accuracy ถ้าไม่มี manual labels ให้ระบุ NOT_VERIFIED และเตรียมวิธีให้ Owner ตรวจเหตุการณ์ในเครื่อง
10. ก่อนรันเต็มวัน ต้องผ่าน blocker/resume tests, native environment, geometry/media/reference checks และมีวันที่/แหล่งสื่อ/ขอบเขต live ที่ชัดเจน ถ้า Owner เตรียมสื่อทั้งวันไว้แล้วให้ใช้ local ก่อน วันที่เก่าอาจไม่มีบน SD แล้ว ห้ามอ้างว่าปัจจุบันยังมี503คลิปจาก inventory ประวัติ
11. การใช้กล้องจริงให้ตรวจสิทธิ์ล่าสุดก่อน: prompt ส่งต่อนี้อนุญาต setup/dev/offline testing แต่ไม่ได้เปลี่ยนคำสั่งห้าม restart/auth/new-day ของ monitor เก่าให้เป็นสิทธิ์ live อัตโนมัติ เตรียม invocation ที่ตรวจแล้วให้พร้อม และถามเฉพาะวันที่/สื่อหรือขั้น private sign-in ที่ขาด ไม่ขออนุมัติติดตั้ง/แก้โค้ดซ้ำ
12. เมื่อมี scope live พร้อม ใช้ `tools.ft_day_job`/`tools.ft_day_run` ตาม CLI จริงพร้อม explicit `--date`, new private `--root`, verified `--config`/`--reference`; CoreML ต้อง `--backend coreml --reference-sha256 <hash ที่ตรวจจริง>` เลือกถูก interpreter/worker, `--day-ledger` ภายใน driver และไม่มี backend fallback อย่าส่งคำสั่ง `--run` ก่อนพร้อม
13. เฝ้าดู PID + actual command/root/date/backend และ ledger ไม่เชื่อ running flag อย่างเดียว นับเป็นครั้งเดียวตามวันที่ ไม่มี recurring new-day scheduler ถ้าต้องสร้าง follow-up ให้ผูก job ใหม่และปิดหลัง complete/blocker ไม่ reuse automation10 ของเครื่องเก่า

### 11. รายงานและการใช้งานต่อ

ใช้ `tools.ft_day_summary.read_ledger/query` สำหรับยอด/คลิป/ช่วงเวลา แยก expected/processed/unprocessed_clips, union recorded/processed/unprocessed-recorded/gap_seconds และสถานะ partial/complete ถ้า `expected_clips=0` ให้แสดง “ไม่มีคลิปให้ยืนยัน”; ถ้ามีคลิปแต่ยังไม่ประมวลผล ให้แสดง “ยังไม่ได้ประมวลผล” ไม่ใส่ศูนย์คนแทนข้อมูลที่ขาด `original_day_complete=null` หมายถึงยังไม่มีหลักฐานความครบของต้นฉบับ แม้ `full_day_complete=true` จะหมายถึงนับครบรายการที่ค้นพบ

รายงานภาษาไทยมี near/far/front accepted/front_review, side accepted/review, รายชั่วโมงและเช้า/กลางวัน/เย็นพร้อมนิยามช่วง, ช่วงเวลาที่นับได้จริง, เวลารันจริง, ข้อผิดพลาดจริง และชื่อไฟล์ที่มีอยู่ ส่งออก HTML/CSV แบบ offline ไปโฟลเดอร์ตัวเลขที่ Owner เลือก; iCloud เป็นทางเลือก ไม่ใช่ dependency ของ inference ห้าม sync media/config/state ไปกับรายงาน และอย่าอ้าง cloud sync สำเร็จเพราะเขียนไฟล์ local สำเร็จ

เมื่อพร้อม ส่งมอบ:

- รายการติดตั้งพร้อมเวอร์ชัน/architecture/lock/model hashes และรายการที่ยังขาด
- หลักฐานแก้ blocker/regression กับขอบเขตสิ่งที่ยัง UNKNOWN
- ตารางเทียบ CPU/CoreML และเครื่องเดิมเฉพาะหลักฐานที่เทียบกันได้ ไม่มีคำรับรองความเร็ว/ความแม่นยำที่ยังไม่ได้วัด
- คำสั่งหรือ launcher ใช้งานจริงที่ตรวจแล้วสำหรับ preflight/run/status/report/stop พร้อม input ที่ไม่ใช่ secret, ขอบเขตและวิธีจัดการ partial result
- docs/STATUS.md, แผน/decision ที่เปลี่ยน และ ignored delivery record ของเครื่องใหม่ตามจริง
- checkpoint บน branch งานเมื่อ reviewable; stage เฉพาะไฟล์ที่ตรวจ ป้องกันข้อมูลส่วนตัว ไม่ push main/force push/merge เอง อ่าน remote กลับก่อนรายงาน SYNCED
- ถ้ารันเต็มวันยังติดสื่อ/geometry/auth ให้รายงาน “ติดตั้งและทดสอบ offline ผ่าน; live ยังติดรายการ…”, ไม่เรียกว่าพร้อมใช้งานเต็มระบบ

เริ่มตอนนี้ด้วยการตรวจเครื่องและ checkout อ่าน control แสดงสถานะสั้น ๆ แล้วลงมือทำส่วนที่ได้รับอนุญาตต่อจนเสร็จ ใช้ Claude จริงตาม workflow เมื่อ CLI พร้อม หลีกเลี่ยงคำถามซ้ำและรักษาหลักฐานเดิม

## จบ prompt

เอกสารทางการที่ตรวจประกอบการติดตั้งเมื่อ 2026-11-14: [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), [Codex/desktop quickstart](https://learn.chatgpt.com/docs/quickstart), [Claude Code](https://code.claude.com/docs/en/quickstart), [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [uv locking](https://docs.astral.sh/uv/pip/compile/), [FFmpeg download](https://ffmpeg.org/download.html), [OpenAI Docs MCP](https://developers.openai.com/learn/docs-mcp). Source/version ใน repository และผลบนเครื่องปลายทางต้องตรวจอีกครั้งเมื่อเริ่มงาน
