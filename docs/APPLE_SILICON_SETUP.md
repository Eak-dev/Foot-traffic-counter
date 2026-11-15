# ใช้งาน Foot-traffic-counter บน Apple Silicon

เริ่มจาก checkout เดิมที่ `claude/ft-d0-preflight` และ commit ส่งต่อ
`969a9c0620d1c8af630c94964ed886feffa4e7fd` พรอมป์ remote ตรงกับไฟล์ใน commit
และต้นทางของ PR #4 ตรงกับ branch เมื่อเริ่มย้ายเครื่อง

เครื่องทดสอบ Apple M1, RAM 8 GiB, macOS 26.0.1, arm64 native, เวลาตรวจเริ่มต้น
เหลือพื้นที่ 60 GiB ใช้ Xcode Command Line Tools ที่มีอยู่ (clang 14.0.3),
Git 2.39.2, ripgrep และ Codex ที่มีอยู่แล้ว

## เวอร์ชันและหลักฐานติดตั้ง

| รายการ | รุ่นและที่เก็บ |
| --- | --- |
| uv | 0.12.23 arm64 ใน `.venv/ft-bin` |
| CPython | 3.13.16 arm64 จาก uv ภายใน `.venv` ทุก environment |
| CPU | `.venv/ft-counting` 29 packages จาก `requirements-counting.lock` |
| CoreML | `.venv/ft-accel` 32 packages รวม ONNX 1.19.1, ml-dtypes 0.5.4, typing-extensions 4.15.0 |
| Acquisition | `.venv/ft-acquisition` 24 packages จาก `docs/migration/requirements-acquisition.lock` |
| Claude Code | 2.1.325 arm64 ใน `.venv/ft-bin` ตรวจ checksum จาก manifest; launcher preflight READY, sign-in ยังขาด |
| GitHub CLI | 2.104.0 arm64 ใน `.venv/ft-bin` ตรวจ checksum จาก release |
| FFmpeg และ FFprobe | 9.0.2 arm64 ใน `.venv/ft-media-bin` |
| Keychain helper | Objective-C arm64 ที่ path ตาม [คู่มือเซสชัน](SESSION_48H_GUIDE.md) ตรวจ ad-hoc signature ด้วย `codesign --verify --strict` |

ทุก environment ผ่าน `uv pip check` พร้อม hash verification ตอน sync ติดตั้ง wheel
จาก lock ใน repo และสร้าง CoreML lock ด้วย `uv pip compile` จาก counting pins,
counting lock เป็น constraints และ `docs/migration/requirements-coreml-extra.in` ตาม
[พรอมป์ส่งต่อ](NEW_MACHINE_PROMPT.md) ไฟล์ใหม่เป็น `.venv/requirements-coreml-arm64.lock`
SHA-256 ที่ตรวจครั้งนี้

| ไฟล์ | SHA-256 |
| --- | --- |
| Counting lock | `08f37190c3db54ea17f3a2a413141db0165125c6f6d66af946297e7a8be3851a` |
| CoreML arm64 lock | `a1bddd9d929df829af6f756e2bd033e2a52e12e87a308d7166b0f7b98403984b` |
| Acquisition lock | `82bbbe790b998f9ce080fb36749cd304a60044428bdd867da9ab40603afc8243` |
| YOLOX_s ONNX (35,858,002 bytes) | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` |
| CoreML person-output FP32 batch 2 derivative | `6539d8b047fe00009cc5c1a562840e426513d27e355bb734288ba1b833c8dd46` |

เก็บ ONNX ที่ `.venv/ft-models/yolox_s.onnx` จาก
[OpenCV Zoo commit ที่ตรึงไว้](https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox)
ตัวช่วย repo สร้างโมเดลอนุพันธ์และ compile cache ใหม่บนเครื่องนี้
`pytapo` และ `aiofiles` ผ่าน import-only check

FFmpeg/FFprobe 9.0.2 อยู่ที่ `.venv/ft-media-bin` คอมไพล์จาก
[source ของ FFmpeg](https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz) SHA-256
`8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e` แบบ
arm64 และปิด network protocols เครื่องมือรายวันใช้ MPEG-TS, MOV/MP4, H.264,
`filter_units` และ `h264_mp4toannexb`; เครื่องมือรีวิวใช้ `libx264`
จาก Homebrew bottle arm64 Tahoe (`r3222`, SHA-256
`b631667b5ad55c6c3ae383484f658c5b4ba14da8a2fbb1d537975695852529ca`) ลิงก์แบบ
static ใน build นี้ ทดสอบ encode H.264 → MPEG-TS → remux พร้อมกรอง SEI → MP4
ผ่าน FFprobe และ strict decode ครบ 5 เฟรม

## Checkpoint ที่แก้

การทดสอบแบบ daytime-first รันทีละหนึ่งคลิปและมีช่วงเวลาทับซ้อน ผ่าน cursor 1→4
แต่ล้มที่เปิด worker รอบ 5 ก่อนแก้ ตัวขับงานใช้รหัสกลุ่มจากรายการต้นฉบับ ขณะที่
CoreML worker ตรวจรหัสจาก ledger ที่มี status, hashes และ events หลัง commit
ตอนนี้ทั้งสองมุมมองใช้เฉพาะ ref และขอบเขตเวลาจาก inventory รหัสกลุ่มของรายการ
ต้นฉบับยังคำนวณได้เหมือนเดิม ทดสอบผ่านทั้งหกรอบและ reset tracker เฉพาะตอนเปลี่ยนกลุ่ม
รายการ `completed_groups` ที่ผิดถูกปฏิเสธก่อนอ่าน target หรือเปิด session
พร้อม diagnostic แบบค่าคงที่จากโปรแกรม

บั๊กนี้อธิบายอาการ batch 4→5 ได้ ข้อมูล OD-71 ที่เหลือเป็นรายงานสรุป
จึงยืนยันย้อนหลังไม่ได้ว่ามีสาเหตุอื่นร่วมด้วยหรือไม่ ใช้ root ใหม่และ hash reference
ที่ตรวจจริง ส่วน snapshot เก่าผูกกับ runtime เดิมก่อนการแก้

## ผลทดสอบและความเร็ว

- Python ระบบ: 933 ผ่าน, 136 ข้ามตาม dependency, 0 ล้มเหลว
- CPython arm64 ที่ลง dependencies: 1,069 ผ่าน, 0 ข้าม, 0 ล้มเหลว
- ชุดคลิป lossless สร้างจากภาพ [OpenCV basketball sample](https://github.com/opencv/opencv/blob/4.11.0/samples/data/basketball1.png)
  และฉากสังเคราะห์ ตรวจ hash พิกเซลและเวลา 100 เฟรมตรงกันระหว่าง 20 วินาทีรวดเดียว
  กับ 10+10 วินาที ใช้ acquisition stub และผ่าน day driver จริงโดย worker ปิดเครือข่าย
  ตอนกึ่งกลาง checkpoint มี active tracks 4 รายการ ผลนับ 1 เหตุการณ์และ encoded
  tracker/counter state ของ CoreML ตรงกันทุกค่าระหว่าง split ใน worker เดิม
  กับเปิด process ใหม่ เหตุการณ์ตรงกับ full clip และ CPU
  ค่า clock `owned_begin` ของ split คือจุดเริ่มคลิปที่สอง ส่วน full clip คือจุดเริ่มคลิปเดียว
  สถานะเชิงตัวเลขของ CPU ต่างจาก CoreML จึงตรวจการต่อ state ภายใน backend เดียวกัน
  ตัวเลือก backend/reference ที่ผิดถูกปฏิเสธก่อนเรียก target/session/inventory/download
  และ hash ของไฟล์ที่มีอยู่ตรงเดิม
- ORT profile ของ synthetic batch 2 พบการประมวลผล 1 partition บน
  `CoreMLExecutionProvider` ตรวจ output shape `[2, 8400, 85]`
  ยังไม่มีหลักฐานว่า CoreML แบ่งงานภายในระหว่าง CPU กับ GPU อย่างไร

เทียบคลิปทดสอบ 20 วินาทีบน M1 ใช้ YOLOX_s และ geometry ของ fixture เดียวกัน
ที่ 5 fps สุ่มตัวอย่าง 100 เฟรมต่อรอบ วอร์มหนึ่งรอบต่อ backend แล้ววัดซ้ำฝ่ายละ
3 รอบสลับลำดับ ใช้ worker ทีละตัว event rows ตรงกันทุกประการทั้งหกรอบ

| ค่ามัธยฐาน (ต่ำสุด–สูงสุด) | CPU baseline | CoreML FP32 batch 2 |
| --- | ---: | ---: |
| ประมวลผลคลิป (วินาที) | 26.934 (26.615–27.683) | 4.778 (4.772–4.831) |
| setup โมเดลและ reference (วินาที) | 0.106 (0.106–0.116) | 0.430 (0.399–0.437) |
| ขั้นตรวจจับ (วินาที) | 26.792 (26.474–27.539) | 4.504 (4.489–4.526) |
| wall time ของ worker (วินาที) | 27.679 (27.433–28.481) | 5.897 (5.872–5.962) |
| CPU core-seconds ของ worker | 107.442 (106.371–108.847) | 2.372 (2.338–2.425) |
| peak RSS ของ worker (MiB) | 327.500 (326.484–327.828) | 456.375 (452.172–492.547) |

CoreML ใช้เวลาประมวลผลสั้นลง 82.3% ใน fixture นี้ หรือประมาณ 5.64 เท่าของ
throughput CPU ค่า residual รวม frame decode, tracker และ counter ผล timing
ไม่รวมการดึงคลิป, remux, checkpoint และรายงานรายวัน การตรวจ remux ทดสอบแยก
ไม่วัดพลังงาน, อุณหภูมิ หรือ GPU counters ค่าเก่าบน Intel มาจากคลิปร้าน 6 คลิป
รวม 858 วินาทีและลดเวลาประมวลผล 25.931% เทียบ CPU ของเครื่องเดิม
จึงใช้เป็นประวัติและยังไม่มีการเปรียบเทียบข้ามเครื่องด้วยสื่อเดียวกัน

ความแม่นยำกับ manual labels, geometry จริง, อัตราการประมวลผลของคลิปร้าน
และเป้าหมายต่ำกว่า 10 ชั่วโมงต่อวันยังรอการวัดจากสื่อจริง

## คำสั่งใช้งาน

รันจาก root ของ repo ใช้ private folders นอก repo และนอกพื้นที่ sync สำหรับ
สื่อ/config/ledger/cache เลือก parent directory ที่มีอยู่แล้วและจำกัดสิทธิ์
directory เป็น 0700 และไฟล์เป็น 0600

ตรวจเครื่องและทดสอบในเครื่อง

```sh
git status --short --branch
python3 tools/claude_dev.py --check
PATH="$PWD/.venv/ft-media-bin:$PATH" python3 tools/ft_data.py doctor --json
python3 -m unittest discover -s tests -t . -v
.venv/ft-accel/bin/python -m unittest discover -s tests -t . -v
.venv/ft-media-bin/ffmpeg -version
.venv/ft-media-bin/ffprobe -version
shasum -a 256 .venv/ft-models/yolox_s.onnx
```

สำหรับ Claude ให้คุณ Eak ลงชื่อเข้าใช้บัญชีเดิมผ่าน
`.venv/ft-bin/claude auth login` ในเครื่อง ขั้นทดสอบงาน Dev ที่ PO ทำหลัง sign-in
ให้ใส่ `PATH="$PWD/.venv/ft-bin:$PATH"` เฉพาะ invocation ของ
`tools/claude_dev.py` ใช้ใบงานใหม่และ full HEAD ตาม [WORKFLOW](WORKFLOW.md)
ไฟล์ตั้งค่าเครื่องนี้อ้าง Sonnet รุ่นที่ใช้ใน workflow เดิม แพ็กเกจของบัญชีและสิทธิ์
ใช้โมเดลต้องยืนยันจากผลการเรียกจริง

GitHub checkout อ่าน remote ได้ ส่วน HTTPS push ต้องมีบัญชีที่มีสิทธิ์เขียน
ใช้ `.venv/ft-bin/gh auth login --hostname github.com --web` เพื่อทำขั้นยืนยัน
ในเบราว์เซอร์เมื่อจำเป็น แล้วให้ PO ส่งเฉพาะ branch งานและอ่านหัว branch/PR กลับ

สำหรับคลิป Fixed ที่มีอยู่ในเครื่อง ตั้งค่า shell variables
`FT_CLIP`, `FT_CONFIG`, `FT_REFERENCE`, `FT_BENCH_ROOT`
เป็น path ที่ตรวจแล้ว `FT_BENCH_ROOT` เป็น private directory นอก repo และ
`cpu`/`coreml` เป็น output ใหม่ใต้โฟลเดอร์นั้น

```sh
.venv/ft-accel/bin/python -m tools.ft_perf_accel --backend ort --kernel legacy \
  --threads 4 --input "$FT_CLIP" --config "$FT_CONFIG" --reference "$FT_REFERENCE" \
  --seconds 20 --output "$FT_BENCH_ROOT/cpu"
.venv/ft-accel/bin/python -m tools.ft_perf_accel --backend coreml --kernel cached \
  --person-output --batch-size 2 --precision fp32 --threads 4 \
  --input "$FT_CLIP" --config "$FT_CONFIG" --reference "$FT_REFERENCE" \
  --seconds 20 --output "$FT_BENCH_ROOT/coreml"
```

ก่อนทดลองกับกล้อง รอบใหม่ต้องมีวัน Bangkok ที่สิ้นสุดแล้ว, geometry v4 และ
reference Fixed ที่ตรวจแล้ว, ขอบเขต acquisition ของรอบนั้น และ session
ที่พร้อมผ่านขั้นตอนส่วนตัว เมื่อเกตครบจึงใช้คำสั่งด้านล่าง โดยตั้ง
`FT_DATE` เป็น YYYYMMDD, `FT_JOB_ROOT` เป็น path ใหม่, และ `FT_REFERENCE_HASH`
เป็น SHA-256 ที่คำนวณจาก `FT_REFERENCE` ในเครื่อง

```sh
python3 -m tools.ft_day_job --run --date "$FT_DATE" --root "$FT_JOB_ROOT" \
  --config "$FT_CONFIG" --reference "$FT_REFERENCE" --backend coreml \
  --reference-sha256 "$FT_REFERENCE_HASH"
```

หยุด foreground job ที่เปิดเองด้วย Ctrl-C ใน Terminal เดิม ตรวจว่า supervisor
และ worker สิ้นสุดแล้วจึงตรวจหรือสร้างรายงานใหม่ คำสั่งด้านล่างอ่าน ledger
ที่ commit ล่าสุด แสดงความครบและเขียนรายงานตัวเลข HTML/CSV/JSON ใน private root

```sh
python3 - "$FT_JOB_ROOT" <<'PY'
import json, sys
from pathlib import Path
from tools.ft_day_summary import read_ledger, write_reports
root = Path(sys.argv[1]).resolve()
ledger = read_ledger(root / "ledger.json")
print(json.dumps(write_reports(root, ledger), ensure_ascii=False, indent=2))
PY
```

`job-status.json` มี PID, batch, reason และ diagnostic ล่าสุด

```sh
python3 -m json.tool "$FT_JOB_ROOT/job-status.json"
ps -p "$FT_DRIVER_PID" -o pid=,command=
```

ตั้ง `FT_DRIVER_PID` จากไฟล์สถานะ ตรวจคำสั่งกับ root/date/backend
ในเครื่องก่อนสรุปว่ากำลังรัน รายงานบางส่วนให้ดูจำนวน
คลิปค้างและช่วงเวลาที่มีสื่อจริง `NO_RECORDINGS` หมายถึงไม่มีคลิปให้ยืนยัน
`COMPLETE_RECORDINGS` หมายถึงประมวลผลครบตามรายการที่พบ
`original_day_complete=null` ยังไม่ยืนยันว่าต้นฉบับครบวัน ดูนิยามรายชั่วโมงและ
ช่วงเช้า–กลางวัน–เย็นใน [DAY_COUNTING](DAY_COUNTING.md)
