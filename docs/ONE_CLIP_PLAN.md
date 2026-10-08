# แผนทดลองดึงคลิป SD หนึ่งคลิป (D1 preparation)

BASELINE ตอนเริ่มเขียนแผน 2026-10-07: `0eeeb12296551cb6e887245f60a610a83fdb9765`; อยู่ใน checkpoint PR #4 แล้ว. สถานะงานปัจจุบันดู STATUS/local HEAD
PHASE: FT-D0 merged เป็น `v0.1.0`; เอกสารนี้เตรียม D1 เท่านั้น — ยังไม่เปิดเกตกล้อง/เครือข่าย/ติดตั้ง
BLOCKERS: B1 downloader ยังไม่เขียน · B2 ยังไม่มี private input ใน Mac · B3 เส้นทางบ้าน→ร้าน NOT_TESTED (ไม่มี shop computer/NAS, OD-21) · B4 auth/adapter/Fixed Lens channel mapping UNKNOWN · B5 คลิป/มุมหลักยืนยันแล้ว OD-22/23; metadata/timezone/เพดานยังไม่ยืนยัน
NEXT_ACTION: ดู [ACQUISITION_ROUTE_DECISION](ACQUISITION_ROUTE_DECISION.md): รับหลักฐาน capability ของ router/interface จากผู้ผลิตหรือให้ Owner เลือก local/manual trial แยก; ยังไม่เขียน home downloader โดยเดา route. PO ตรวจ Mac แล้วตาม MAC_READINESS; scope live ยังไม่เปิด

## 1. ข้อค้นพบจากหลักฐาน PO (2026-10-07, ไม่สมมติ live)

- **Candidate pin**: `pytapo==3.4.26` (https://pypi.org/project/pytapo/3.4.26/, 2026-09-28), wheel `pytapo-3.4.26-py3-none-any.whl` sha256 `d69a63c8765de82eae244d46156a9d494bf6233d150d15502b5a8f7adc8f5449`. PO ดาวน์โหลด+ตรวจแฮช+อ่าน source แบบ static ใน temp เท่านั้น **ไม่ได้ install/import/execute**. การ pin นี้เป็น candidate selection ไม่ใช่การอนุมัติติดตั้ง. PyPI metadata `Requires-Python` เป็น null; `dependencies`: requests, urllib3, pycryptodome, rtp, python-kasa. README หลัก (https://github.com/JurajNyiri/pytapo) ระบุ Python 3.13 — เป็นข้อมูล floating README แยกจาก wheel ที่ pin ไว้; ยังไม่มีการรับรอง Python 3.9 สำหรับ downloader
- **Dependency gap**: `media_stream/downloader.py` และ `convert.py` ใน wheel import `aiofiles` ซึ่ง**ไม่อยู่ใน wheel `Requires-Dist`** ที่อ่านได้; `convert.py` constructor ต้องมี ffmpeg **และ** ffprobe แม้ output เป็น `.ts` เพราะ `download()` สร้าง `Convert()` ก่อนเสมอ ต้องทำ dependency audit/pin ทั้งชุดก่อนอนุมัติติดตั้ง — ห้ามเขียน recipe `pip install pytapo` ที่ขาด dependency เหล่านี้
- **Instantiate = network**: `Tapo.__init__` ทำ protocol discovery/auth/`basicInfo`/`presets` ทันทีที่สร้าง object → **ห้าม instantiate ใน preflight/dry-run**; แยก subprocess จริงเฉพาะหลังเกต. ค่า default `controlPort=443`, `streamPort=8800` ไม่ใช่คำสั่งให้เปิดพอร์ตสาธารณะ
- **การเลือกเลนส์ยังไม่ยืนยัน**: `Downloader` ไม่มี argument เลือกเลนส์; request ใช้ `channels[0]` fallback `playback channels[0,1]` — ยังไม่รู้ mapping กับเลนส์คู่ของ C545D ต้อง validate มุมภาพเทียบ app ก่อนรับ `ONE_CLIP_PASS`; ห้ามนับสองเลนส์ซ้ำ
- **เวลา/timezone**: wheel รับ `startTime`/`endTime`/`timeCorrection`; `timeCorrection` คำนวณ clock offset เท่านั้น ไม่ใช่การยืนยัน timezone. `getRecordings(date)` upstream default end_index ใหญ่มาก — wrapper ต้อง list ช่วงสั้นมีเพดานหน้า ห้ามลูปดึงทั้งวันตามตัวอย่าง upstream. timestamp acceptance ต้องมาจาก source metadata + timezone ที่ยืนยันแล้ว ไม่เดาจากชื่อไฟล์
- **ไม่มี quota enforcement**: `download()` มี auto fallback เป็น playback และ internal retry; `stall_timeout` ไม่ใช่ total deadline หรือ byte quota; `Convert` เก็บข้อมูลใน memory/tempfile ก่อน output จึง polling ขนาด output อย่างเดียวไม่จำกัด total bytes/memory/temp data ของทุก retry/fallback ก่อนใช้จริงต้องออกแบบ quota ครอบคลุม buffer/temp/retry/fallback หรือเลือก adapter แก้ตรงจุด — ยังไม่อ้างว่า wrapper พร้อม. MD5 ของ upstream ไม่แทน SHA256 ของโปรเจกต์
- **ช่องทางรับคลิป**: https://github.com/JurajNyiri/pytapo เป็น informal camera API ที่ใช้ HOST กล้องที่เข้าถึงได้จริง + cloud password สำหรับ SD — **ไม่มีหลักฐาน cloud-relay export API ที่ยืนยันแล้ว**. คู่มือผู้ผลิต https://www.tp-link.com/en/support/faq/2905/ อธิบายการถอด SD ไปอ่านที่ PC ด้วยมือ (manual fallback ไม่ใช่เป้าหมาย automated). https://www.tp-link.com/us/support/download/tapo-c545d/v1/ ยืนยันข้อมูลรุ่นแบบ region-specific เท่านั้น ไม่มีหลักฐานตรงกับ HW/FW ของ Owner. https://community.tp-link.com/en/home/forum/topic/862820 เป็นประกาศ remote-SD ใน Tapo app สำหรับบางรุ่น; หน้าเต็ม 403 **ห้ามระบุว่า C545D FW 1.1.7 รองรับแล้ว**. การดูคลิปในแอป/ดาวน์โหลดด้วยมือนอกร้านอาจทำได้ แต่ไม่ใช่หลักฐานช่องทาง API อัตโนมัติจาก Mac
- **Third-party mode**: https://www.tp-link.com/us/support/faq/4416/ ให้ตรวจสถานะเท่านั้น ห้ามเปิดเพื่อบีบให้ workaround ทำงาน. https://github.com/JurajNyiri/HomeAssistant-Tapo-Control/issues/1214 เป็น issue ปิดของผู้ใช้ C545D เรื่อง auth/dual-lens — เป็นประวัติ ไม่ใช่หลักฐานว่าแก้แล้ว/compatible SD

## 2. เส้นทางที่เสนอ

ใช้เส้นทาง private ที่ Owner อนุมัติแล้วก่อน ถ้ายังไม่มี ให้ทีมตรวจความสามารถของ ZTE F6107A/แพ็กเกจ AIS เดิมจากหลักฐานที่มีก่อน **ไม่สมมติว่า router รองรับ VPN**, ไม่เปิด 8800/443/RTSP ออก WAN/DMZ, ไม่ติดตั้ง/ตั้งค่าใดจนกว่ามี scope+rollback ที่ Owner อนุมัติ. ไม่ซื้อฮาร์ดแวร์เพิ่ม. การนำเข้าคลิปด้วยมือเป็น fallback เสริมที่ต้องระบุชัดเจนเท่านั้น ไม่ใช่ automatic acquisition PASS

### ข้อจำกัดเส้นทางล่าสุด (OD-21/22)

ร้านไม่มี computer/NAS จึงไม่ใช้ shop host เป็น gateway. ตรวจความสามารถ VPN/ทางเชื่อมของเราเตอร์ ZTE/AIS เดิมจากหลักฐานเฉพาะรุ่นก่อน; ยังไม่มีหลักฐานรองรับและไม่เปลี่ยนค่า. ช่องทาง remote SD ในแอป (ถ้ามีสำหรับรุ่น/region นี้) ต้องแยกจาก API สำหรับ Mac; Owner เปิด playback ขณะอยู่ร้าน (OD-23) ไม่ยืนยันชนิด network หรือ export จากบ้าน. หากไม่มีเส้นทางอัตโนมัติที่พิสูจน์ได้ ให้เสนอ manual import จากแอป/การใช้ Mac เดิมที่ร้านชั่วคราวเป็น fallback แยกก่อนดำเนินการ ไม่ใช่ automatic acquisition จากบ้านผ่านและไม่ซื้อฮาร์ดแวร์.

## 3. ข้อเสนอ secure input (ยังไม่ implement ใน PR นี้)

ขั้นต่อไปที่ PO ควบคุม: local terminal `getpass` prompt รหัสผ่านที่จำเป็น, host เป็น private local เท่านั้น; ห้าม CLI args/env/echo/raw log/ส่ง secret ให้ coding agent. ให้ credential อยู่ใน process memory เฉพาะรอบรันเดียว, persistence ทำเฉพาะเมื่อ Owner สั่งชัดเจนผ่าน system credential store ที่อนุมัติ. PR นี้ไม่มี credential input tool จริง

## 4. ตารางขั้นตอน (งาน offline เริ่มได้; งาน live รอ prerequisites)

| ขั้น | ใครทำ | รายละเอียด | หยุดเมื่อ |
| --- | --- | --- | --- |
| Research/dependency audit | PO+Dev | pin release, ตรวจ aiofiles/ffmpeg/ffprobe, ตรวจ license, ไม่ install | ขาด dependency ที่ pin ไม่ได้ |
| Synthetic wrapper (offline) | Dev | mock response เท่านั้น ไม่เรียกกล้องจริง, ทดสอบ quota/timeout logic | ต้องใช้ network เพื่อทดสอบ |
| Owner status + เลือกคลิป | Owner | ตอบ §6 | ไม่มี route readiness |
| Scope live ตั้ง control | PO | target, bytes, เวลา, storage, rollback ก่อนแตะกล้อง | Owner ยังไม่ยืนยันเพดาน |
| Route check | PO+Dev | ตรวจ reachability เป้าหมายที่ระบุจริงเท่านั้น | ไม่มีเป้าหมายชัด |
| Bounded listing | Dev | list ช่วงสั้น มีเพดานหน้า บันทึกว่าครบ/ไม่ครบ | ชนเพดานไม่รู้จบ |
| One-clip fetch | Dev | ดึงไฟล์ชั่วคราวนอก git, ตรวจ timestamp/duration/view/SHA256, dedup | เกิน quota/retry=0 ล้มเหลว |
| Repeat idempotent check | Dev | รันช่วงเดิมซ้ำ ต้องไม่ซ้ำรายการ | พบรายการซ้ำ |

## 5. เพดานตัวเลข — PROPOSED เท่านั้น รอ Owner

หนึ่งคลิป max 180s (ประมาณจาก Owner ไม่ใช่การยืนยันการตัดคลิป), payload ทดลอง max 100 MiB, total deadline 300s, reserve พื้นที่ว่าง 10 GiB, retries = 0 สำหรับการทดลองครั้งแรก. ถ้าบังคับ quota เหล่านี้ใน upstream ไม่ได้ (ดู §1 bullet quota) ให้ **STOP** และเสนอ adapter เล็กแก้เฉพาะจุดก่อน ไม่เริ่ม live. ไม่เปลี่ยน background/power/account settings/firmware และไม่ติดตั้ง/ดาวน์โหลดโมเดลใด ๆ

## 6. ข้อมูลยืนยันแล้วและที่ยังรอ Owner

1. ทีมตรวจ Mac แล้ว; Owner ยืนยันร้านไม่มี computer/NAS (OD-21). ไม่ขอซ้ำ ไม่ส่ง IP/รหัส ไม่ต้องตั้งค่าเอง. ทีมตรวจ router-based route/ช่องทางผู้ผลิตตาม §2
2. Owner ยืนยันใช้แอป Tapo ได้แล้ว; Camera Account **On**; ภาพล่าสุดยืนยัน Third-Party Compatibility **On**, แอป **3.21.106** และ Privacy Mode **Off** (OD-20). ไม่ขอซ้ำ ไม่ขอรหัสผ่าน ไม่ต้องเปลี่ยนค่า. UPnP Off; ค่า Network Settings Off ยืนยันเพียงป้ายเมนู ไม่ใช่หลักฐานเส้นทางบ้าน→ร้าน หรือผล auth/SD export
3. ภาพ Owner ระบุคลิป SD วันที่ 2026-10-08 เริ่ม 09:51:53 ความยาว 03:00 (OD-22). Owner เลือก **Fixed Lens เป็นมุมหลัก ไม่ใช้ PT Lens สำหรับการนับ** และเปิดภาพขณะอยู่ร้าน (OD-23); ไม่ถามซ้ำ. UI timestamp ยังไม่ใช่ source metadata/timezone PASS; channel mapping ต้องตรวจจากไฟล์ที่ดึงจริง ถ้าได้ PT อย่างเดียวให้หยุด ไม่ใช้แทน Fixed หรือรวมยอดสองเลนส์

ทีมจะตรวจ quota ที่ใช้จริงอีกครั้งตอนประกอบ live plan; ไม่ขอ Owner ออกแบบ VPN, pin package หรือหารูปเมนูเราเตอร์ซ้ำ

## 7. ผลปัจจุบัน

Source-only review; camera requests = 0, auth attempts = 0, clips ดึง = 0. Downloader ยังไม่ implement. หลัง OD-21 ยืนยันไม่มี shop host ให้ใช้ผล ROUTE_DECISION ก่อนเขียน home downloader; bounded adapter เป็นแบบที่ยังไม่ implement และต้องมี route/interface evidence กับ scoped write paths ก่อนมอบหมาย. Dev ไม่เปิดเกต live เอง

## READY_FOR_REVIEW / PENDING_OWNER_INPUT / NOT_TESTED

- READY_FOR_REVIEW: มีแบบและผล route feasibility สำหรับ Owner review; ยังไม่มี wrapper/tests ใหม่. Home downloader อยู่ HOLD_FOR_ROUTE_EVIDENCE; ไม่ใช่พร้อม live หรือการตัดสินว่าเป็นไปไม่ได้
- PENDING_OWNER_INPUT: readiness ของบัญชีตาม adapter ใน §6; อุปกรณ์ร้าน/คลิป/Fixed Lens/สถานที่เปิด playback ยืนยันแล้ว ไม่ขอซ้ำ. เพดาน §5/rollback ของเส้นทางยังเป็นข้อเสนอ
- NOT_TESTED: reachability บ้าน→ร้าน, auth กับ C545D จริง, dual-lens mapping, timezone ของ metadata ต้นทาง, quota enforcement จริงกับ upstream library

PO review: แผนนี้ตรวจเทียบ source ของ wheel ที่ยืนยัน SHA256 แล้ว; Claude รัน baseline unittest 113/113 PASS, exit 0. Source code/tests เดิมไม่เปลี่ยน. ผล PO อิสระบันทึกใน STATUS; ไม่ใช่ผลทดสอบ downloader/live.
