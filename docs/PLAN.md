# แผนงาน: ดึงคลิปจากกล้องเป็นชุด แล้วนับคนเดินผ่านภายหลัง

> สเปกกลางฉบับปัจจุบัน ทั้ง ChatGPT และ Claude อ่านไฟล์นี้ก่อนทำงาน
> รายละเอียดข้อเท็จจริง หลักฐาน และเกต: [PREPROJECT_PLAN.md](PREPROJECT_PLAN.md) · ความคืบหน้า: [STATUS.md](STATUS.md)
> กติกาควบคุมงาน: [PROJECT_CONTROL.md](../PROJECT_CONTROL.md) (มีผลเหนือเอกสารอื่น)

## สถานะการเปลี่ยนแผน

แผนเดิมที่ baseline `73249aabf9d413325c4a772cd68a3ebc5890415e` วาง Raspberry Pi 5 ในร้านให้นับแบบ real-time ผ่าน RTSP
และตั้ง systemd ให้รันถาวร **แผนนั้นถูกแทนที่แล้วตามคำสั่งของ Owner วันที่ 2026-10-06**
เนื้อหาเดิมยังดูได้จากประวัติ git ที่ baseline ข้อกำหนดที่ยังใช้อยู่คือส่วน "ข้อกำหนดที่ยังใช้ต่อ" ด้านล่าง

> **LEGACY / NOT USED:** `.env.example` และ `config.example.yaml` (ตั้งค่า RTSP/Pi) **ไม่ได้ใช้โดย `tools/ft_data.py`** ห้ามอ้างอิงเป็นข้อกำหนด และยังไม่ได้ตรวจทาน อยู่นอกขอบเขตที่แก้ได้ใน FT-D0

## เป้าหมาย

1. **FT-D0 baseline เสร็จแล้ว / เตรียม D1 local ตอนนี้**: เอกสาร, เครื่องมืออ่านไฟล์ (`tools/ft_data.py`), ช่องกรอก IP ในเครื่องและตรวจ offline (`tools/ft_connect.py` ตาม OD-25), synthetic tests
2. **D1–D3**: ออกแบบและพิสูจน์เส้นทางเข้าถึงกล้องอย่างปลอดภัย แล้วดึงคลิปทีละชุดแบบทำซ้ำได้ ตามเกตใน PREPROJECT_PLAN
   การตั้งค่าเส้นทางจริงทำเป็นขั้นแยกที่ Owner อนุญาตเป็นรายครั้ง โดยระบุเป้าหมาย สภาพแวดล้อม และแผนย้อนกลับ
3. **D4**: นับคนเดินผ่านจากคลิปที่ดึงแล้ว พร้อมตัวกรองตามช่วงเวลา (ต้องมีข้อเสนอและการอนุมัติแยก)
4. **D5**: นำร่องและตั้งงานอัตโนมัติ เมื่อ Owner อนุมัติเท่านั้น

สิ่งที่ไม่ทำ: การจดจำใบหน้า, ฐานข้อมูล, เว็บเซิร์ฟเวอร์, Docker, การเก็บวิดีโอหรือภาพลงใน repo, การส่งวิดีโอขึ้นคลาวด์

## ข้อกำหนดที่ยังใช้ต่อ

- นับเฉพาะคน ไม่แยกเพศหรืออายุ และไม่เก็บภาพจากกล้องใน repo
- ความลับ (รหัสกล้อง, `.env`, key ของบริการ, IP ของร้าน) ไม่เข้า git
- **ยอดนับทั้งวัน:** Owner ยืนยัน 2026-10-07 ว่ากล้องบันทึกเฉพาะตอนมีคนเดินผ่าน ช่องว่างระหว่างคลิปเป็นเงื่อนไขปกติของกล้อง จึงรวมยอดจากคลิปเหตุการณ์ของวันเป็นจำนวนการเดินผ่านทั้งวันได้ (OD-15). ใช้คลิปของวันครบตามรายการต้นทางและเกณฑ์นับที่ตรวจแล้ว; การดาวน์โหลดขาด/ล้มเหลวต้องรายงานตามจริง ไม่ปะปนกับช่วงที่กล้องไม่ได้บันทึกเหตุการณ์
- ความแม่นยำ: เป้าเดิม **80% (aggregate) เทียบการนับด้วยมือ** คงไว้เป็น **baseline ชั่วคราวสำหรับการนับในอนาคต — ยังไม่บรรลุ**
  ก่อนยอมรับต้องมี (ก) ชุดทดสอบแยกที่มีกรณีคนนั่งเป็น negative และ (ข) รายงาน false positive / false negative รายเหตุการณ์
  ห้ามลดหรือลบเกณฑ์เดิมโดยไม่มีการอนุมัติจาก Owner
- เวลาเริ่มของคลิป: ใช้ metadata เวลาจากต้นทาง (เช่นดัชนีของกล้อง) เมื่อมี และต้องยืนยันความหมายของเขตเวลาก่อนใช้
  ห้ามแปลง UTC เป็นเวลาไทยโดยเดาหรือแค่เปลี่ยนป้ายกำกับ หากดัชนีไม่มี timestamp ให้เสนอแหล่งเวลาที่ตรวจสอบได้ ห้ามอนุมานจากชื่อไฟล์หรือ mtime
- dedup ด้วยแฮช SHA256 ตรวจได้เฉพาะไฟล์ที่ไบต์เหมือนกันทุกประการ ไม่ใช่ dedup ของวิดีโอที่ทับซ้อนหรือถูกเข้ารหัสใหม่ การจัดการช่วงเวลาทับซ้อนเป็นงาน D3/D4
- ไม่มีฮาร์ดแวร์ใหม่ เป็นข้อจำกัดแน่นอนของ Owner ไม่ใช่ตัวเลือกที่แผนนี้จะเสนอให้ซื้อ
- ตัวเลือก downloader ภายนอก (`pytapo`) เป็นเพียง candidate: README ของโครงการระบุ Python 3.13, ตัวอย่างดาวน์โหลด SD ใช้ ffmpeg,
  การยืนยันตัวตนขึ้นกับรุ่นและ firmware, และตัวอย่างบันทึกใช้ credential ของบัญชีคลาวด์ (แหล่ง: https://github.com/JurajNyiri/pytapo ; PO ตรวจ 2026-10-06)
  ก่อนติดตั้งต้องเลือกและ pin release และตรวจใน runtime แยก **ยังไม่ประกาศว่า Python 3.9 พร้อมสำหรับ downloader**
- **ห้ามรัน integration test ของ upstream** เพราะ README ของไลบรารีเตือนว่าอาจย้ายกล้อง เปลี่ยน privacy mode และรีบูตกล้อง
- Library ที่อนุญาตสำหรับเฟส D4 ขึ้นไป (ยังไม่อนุมัติการติดตั้ง): `ultralytics`, `opencv-python-headless`, `gspread`, `google-auth`, `pyyaml`, `python-dotenv`
  - ข้อควรระวังเรื่องสัญญาอนุญาตของ Ultralytics (AGPL-3.0) ต้องตรวจก่อนนำไปให้ผู้อื่นใช้
- เครื่องมือใน FT-D0 ใช้ Python 3.9+ และ **standard library เท่านั้น**

## ขอบเขต FT-D0

- ไม่มีการเข้าถึงกล้อง เครือข่ายร้าน หรือวิดีโอจริง
- OD-24 อนุญาต PO ติดตั้งโปรแกรม acquisition ฟรีใน runtime แยกแล้ว; OD-25 อนุญาต maintenance/control และ private IP-input/offline check. ไม่มีการซื้อหรือเปลี่ยนการตั้งค่า router, กล้อง, VPN, OS หรือความปลอดภัยของเครื่อง
- ไม่มี schedule, service, GitHub Actions หรือ worker เบื้องหลัง

## เกณฑ์เสร็จของ FT-D0

- เอกสารทั้งหมดตรงกับ PROJECT_CONTROL และไม่มีคำแนะนำ Pi/systemd/real-time เป็นข้อกำหนดปัจจุบัน
- `tools/ft_data.py` ผ่านการทดสอบ unittest ที่ PO รัน (ผู้พัฒนาไม่ได้รันเอง)
- PO ตรวจ PR และ Owner merge — Issue #1 ไม่ถูกปิดอัตโนมัติ

## Execution Roadmap และงานของ Owner

รายละเอียด: [Owner Execution Roadmap](PREPROJECT_PLAN.md#12-owner-execution-roadmap) และ [Owner Checklist](PREPROJECT_PLAN.md#13-owner-checklist).
ลำดับ: D0 เตรียม/Owner review → D1 วิธีรับข้อมูลและสิทธิ์ → D2 หนึ่งคลิป → D3 คลิปรายวัน → D4 นับ/กรอง → D5 งานตามเวลาและ pilot.
อุปกรณ์ยืนยันแล้ว: Tapo C545D Hardware 1.0 / Firmware 1.1.7 (ภาพ Owner 2026-10-07); ZTE F6107A HW V9.0.09/FW F6107A_PON_4.1; AIS Fibre 1000/200. รอเฉพาะ readiness ของ endpoint/บัญชี, สถานะเมนูที่เกี่ยวข้อง และเวลาหนึ่งคลิป. ไม่ขอรูปเราเตอร์หรือทดลอง 4G/5G เพิ่มเป็นเงื่อนไขแรก; ทีมรับผิดชอบทางเชื่อม/private input/downloader.
ยังไม่ต้องซื้อซอฟต์แวร์หรือติดตั้งระบบทีม AI เพิ่ม. Python/pytapo/ffmpeg prerequisites ใน runtime แยกติดตั้งแล้วตาม OD-24; ยังไม่มี downloader. OD-25 เพิ่มงาน private IP-input/offline check ซึ่งไม่พิสูจน์ route/auth/SD.
การเขียน Roadmap นี้ไม่เปิดสิทธิ์ D1–D5 และไม่อนุมัติ merge/deploy โดยอัตโนมัติ.

## การตัดสินใจและสถานะต่อเนื่อง

Owner ให้ sync GitHub ระหว่างสนทนา: [DECISIONS](DECISIONS.md) เก็บข้อสรุป/ข้อเสนอแยกกัน; [STATUS](STATUS.md) เก็บเฟส/ผลจริง/blockers/next action. PO ปรับเอกสารและ PR ที่เกี่ยวข้องพร้อม read-back ตาม WORKFLOW. คำสั่งให้ทดลองหนึ่งคลิปได้รับแล้ว แต่ไม่มี implementation/endpoint/auth/route ที่พร้อม ไม่ใช่ขาดคำสั่งทั่วไปซ้ำ; ก่อนใช้สิทธิ์นั้น PO ต้องระบุ target/ขอบเขต/rollback ใน control. รอบ sync นี้ไม่เปลี่ยนสิทธิ์หรือเปิดงานจริง

## การพัฒนา local (Owner decision 2026-10-07)

Codex และ Claude ใช้ checkout/branch งานเดียวกัน มีหนึ่ง writer ต่อครั้ง. ใช้ `tools/claude_dev.py` ตรวจ baseline/งานค้าง/ownership ก่อนมอบหมายงาน; Claude ทดสอบ local/synthetic ได้ตาม policy. อัปเดตสถานะใน local และเผยแพร่ GitHub ตาม checkpoint ใน [WORKFLOW](WORKFLOW.md), [DECISIONS OD-12/13](DECISIONS.md). สิทธิ์ Dev นี้ไม่เปลี่ยนสเปก batch acquisition หรือเปิดเกตอุปกรณ์ D1–D5.

## งานถัดไป: หนึ่งคลิปจาก SD

ข้อมูลล่าสุด 2026-10-08 (OD-20–23): แอป 3.21.106 / Third-Party Compatibility On; ร้านไม่มี computer/NAS จึงไม่ใช้ shop host เป็น gateway. คลิปเป้าหมายใน UI วันที่ 2026-10-08 เริ่ม 09:51:53 ยาว 03:00; Owner เลือก **Fixed Lens เป็นมุมหลัก ไม่ใช้ PT Lens สำหรับการนับ** และเปิด playback ขณะอยู่ร้าน. ไม่ขอข้อมูลเหล่านี้ซ้ำ. ทีมตรวจทางเชื่อมของเราเตอร์เดิม/ผู้ผลิตก่อนเลือกวิธี; UI playback ไม่พิสูจน์ remote export API สำหรับ Mac และไม่เปิดเกต live. ยังต้องยืนยัน source metadata/timezone/channel mapping และเพดานทดลอง; หากไฟล์มี PT อย่างเดียว ห้ามใช้แทน Fixed.

[ONE_CLIP_PLAN](ONE_CLIP_PLAN.md) เป็นแบบ D1 offline preparation ที่ตรวจจาก candidate release และข้อจำกัดจริง. ทำ dependency audit/แบบ adapter ที่คุมขอบเขตก่อน; รับสถานะ route/app และคลิปเป้าหมายจาก Owner แล้ว PO จัด control เฉพาะการทดลองหนึ่งคลิป. แผนนี้ยังไม่มี downloader, credential input หรือ live PASS และไม่ติดตั้ง/เปลี่ยนเครือข่ายอัตโนมัติ.

[ACQUISITION_ROUTE_DECISION](ACQUISITION_ROUTE_DECISION.md) เป็นผลตรวจเส้นทางล่าสุด: ไม่มี shop host; `pytapo` ต้องมีทางเข้าถึงกล้องจริง. คู่มือ AIS ที่พบยังไม่ยืนยัน VPN server และหลักฐาน remote SD ในแอปไม่ยืนยัน API สำหรับ Mac. ชะลอ home downloader จนมี route/interface evidence; เตรียมข้อความถาม capability และทาง local/manual trial แยกให้ Owner เลือก ไม่อ้างว่าเป็นไปไม่ได้หรือเปลี่ยนเป้าหมายโดยอัตโนมัติ.

## OD-25 — private input และ offline check

Owner อนุมัติ maintenance แยกแล้ว 2026-10-08. Claude ทำ `tools/ft_connect.py`, synthetic `tests/test_ft_connect.py` และ `docs/MAC_CONNECTION_GUIDE.md` ผ่าน launcher เดิม. รับ literal RFC1918 IPv4 ผ่าน masked interactive input เท่านั้น ไม่รับรหัสผ่านหรือ IP ใน command arguments. เก็บเฉพาะ ignored `config.local.connection.json` mode 0600 แบบไม่เขียนทับ ไม่ตาม symlink. Offline check ตรวจ schema/สิทธิ์ไฟล์และแสดงสถานะที่ไม่เผย IP/path; valid config ไม่ใช่ connection PASS. ไม่มี DNS/socket/route inspection/import pytapo/auth/SD/video. Live ยังต้องมี exact endpoint/private route และใบงานจำกัดเป้าหมายก่อน. ผู้ใช้ไม่ต้องส่ง IP หรือ credentials ในแชต/GitHub.
