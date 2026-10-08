# ทางดึงคลิปจากบ้านเมื่อร้านมีเฉพาะกล้อง

BASELINE: `ee89a5102ead18022cc5104502dd742b18f3c0f1` · branch `claude/ft-d0-preflight` · root = checkout ปัจจุบัน (ไม่ระบุพาธจริง)
PHASE: D1 preparation เอกสารเท่านั้น; ยังไม่เปิดเกตกล้อง/เครือข่าย
BLOCKERS: B3 เส้นทางบ้าน→ร้าน NOT_TESTED · B4 auth/adapter/Fixed Lens mapping UNKNOWN (ดู [ONE_CLIP_PLAN](ONE_CLIP_PLAN.md))
NEXT_ACTION: Owner ใช้ข้อความ §3 สอบถาม capability; PO ประเมินคำตอบก่อนเขียน downloader บ้าน. ยังไม่ได้ติดต่อผู้ผลิต/ISP จริง และ PO ไม่มีสิทธิ์ส่งข้อความแทน Owner จากใบงานนี้
TEST_RUN: Claude รายงาน baseline unittest 113/113 PASS, exit 0; result JSON ไม่เก็บ stdout ของ test จึงเป็น DEVELOPER_REPORTED. PO ตรวจอิสระตาม STATUS; ไม่ใช่ route/device test

## สรุปผล

ตอนนี้ยังไม่มี automatic SD route จาก Mac บ้านที่พิสูจน์ได้ด้วยหลักฐานที่ตรวจแล้ว — **ไม่ใช่การตัดสินว่าเป็นไปไม่ได้**ถาวร เพียงยังขาดหลักฐานเฉพาะรุ่น/region ของ Owner ครบตามเกณฑ์ รอบนี้ไม่มีการตั้งค่า, ส่งคำขอ หรือดึงคลิปจากกล้องจริง.

## 1. ตาราง 4 ทางที่พิจารณา

| ทาง | สถานะ | เหตุผล/หลักฐาน |
| --- | --- | --- |
| Router-native private route (เช่น VPN server/gateway บน ZTE F6107A) | UNKNOWN | คู่มือ AIS ([KM1099952](https://aiscallcenter.ais.co.th/ikm/acc/index.php?kmid=KM1099952)) ระบุ LAN/DDNS/Port Forwarding/Wi-Fi แต่ไม่พบหลักฐาน VPN server บน firmware ของ Owner; ไม่สรุปว่าไม่รองรับเพราะคู่มือไม่พูดถึง. DDNS ไม่ใช่ secure tunnel. ต้องตรวจหลักฐานเฉพาะรุ่น + LAN reachability จริงก่อนใช้ |
| Vendor cloud / remote SD API สำหรับ Mac | UNVERIFIED | Release note C545D(EU)_V1_1.1.7 Build 260421 ([TP-Link download](https://www.tp-link.com/kr/support/download/tapo-c545d/v1/)) พูดถึงความเสถียร/ความปลอดภัย/tracking เท่านั้น ไม่มีข้อความ remote SD export; region/build ของ Owner ยังไม่ยืนยันและไม่ขอซ้ำเป็นเงื่อนไขแรก. PO อ่าน [ประกาศผู้ผลิต remote SD](https://community.tp-link.com/en/smart-home/forum/topic/862820) ได้แล้ว 2026-10-08 (แทนผล 403 เดิม): ยืนยัน rollout สำหรับบางรุ่นผ่าน firmware แต่รายการ April 2026 ไม่มี C545D และผู้ผลิตระบุรายการไม่อัปเดต real-time. ยังไม่ใช่หลักฐานว่า C545D ไม่รองรับ; ไม่พบ API สำหรับ Mac ในหน้าที่ตรวจ |
| นำ Mac เดิมไปต่อ Wi-Fi ร้านชั่วคราว | PROPOSED | ข้อเสนอ local trial ที่ร้าน ไม่ใช่ automation จากบ้าน; ต้องมี control/scope แยกก่อนเริ่ม |
| Export จากแอป + import local บน Mac | OWNER_REPORTED / PROPOSED_IMPORT | Owner รายงานก่อนหน้าว่าโทรศัพท์ที่ร้านดาวน์โหลดได้ (ดู PROJECT_CONTROL); OD-23 ยืนยันเพียงสถานที่เปิด playback รอบนี้. ยังไม่ได้ export/import คลิปเป้าหมายรอบนี้; เป็น manual fallback ไม่ใช่ automatic acquisition |

เส้นทางที่ไม่อยู่ใน scope นี้ (ไม่เสนอ): ซื้อ host/hub เพิ่ม, เปิดพอร์ตกล้องตรงสู่ public/DMZ, flash/custom firmware, VPN เฉพาะฝั่งบ้านอย่างเดียวโดยไม่พิสูจน์ปลายทาง. ไม่มีข้อเสนอให้ซื้อ cloud service แล้วถือว่า SD export ได้โดยอัตโนมัติ.

## 2. หลักฐานประกอบ (SOURCE_CHECKED)

- PO source refresh 2026-10-08: [TP-Link FAQ 3610](https://www.tp-link.com/us/support/faq/3610/) อธิบายการ export detection events/clip ผ่าน Tapo app; ส่วนใหญ่ต้องอยู่ Wi-Fi เดียวกับกล้องและข้อยกเว้นขึ้นกับรุ่น/firmware. ไม่ใช้ manual record หรือ screen recording แทน SD source โดยไม่แยกหลักฐาน. [ประกาศ remote SD](https://community.tp-link.com/en/smart-home/forum/topic/862820) ระบุให้ตรวจ regional firmware release notes หรือถาม support เพื่อยืนยันรุ่น; ไม่อ้าง April list เป็นข้อสรุปปัจจุบันเชิงลบ. [คู่มือ AIS F6107A](https://aiscallcenter.ais.co.th/ikm/acc/index.php?kmid=KM1099952) อ่านซ้ำแล้วไม่พบ VPN server evidence. ข้อสรุป: ยังต้องมี capability evidence ของ shop route หรือ Mac export interface; private endpoint configured (OD-28) ไม่แก้ blocker นี้. ไม่มี vendor contact/device requests.

- pytapo 3.4.26 wheel (SHA256 `d69a63c8765de82eae244d46156a9d494bf6233d150d15502b5a8f7adc8f5449`, [PyPI](https://pypi.org/project/pytapo/3.4.26/), [source](https://github.com/JurajNyiri/pytapo)) — ตรวจแบบ static เท่านั้น ไม่ install/import. `HttpMediaSession.start` เรียก `asyncio.open_connection(self.ip, self.port)` ตรง ไม่มี cloud relay transport ในชั้นนี้; `cloud_password` เป็นชื่อ credential ไม่ใช่เส้นทาง relay. Downloader ต้องมี `self.tapo.host`/`streamPort` ที่เข้าถึงได้จริงจาก Mac — SDK candidate ไม่สร้างเส้นทางบ้าน→ร้านให้เอง
- ผูกกับ [ONE_CLIP_PLAN](ONE_CLIP_PLAN.md): `aiofiles` ไม่อยู่ใน wheel `Requires-Dist`; ต้องมีทั้ง ffmpeg และ ffprobe แม้ output เป็น `.ts`; quota/retry/fallback ของ upstream ไม่ถูกบังคับโดย wrapper polling output อย่างเดียว — ยังไม่พร้อม live trial ตรงจาก example upstream

## 3. คำถามเสนอให้ Owner ใช้สอบถามผู้ผลิต/ISP (ยังไม่ติดต่อจริง)

**ถาม AIS** (ZTE F6107A HW V9.0.09 / FW F6107A_PON_4.1): เราเตอร์รุ่นนี้รองรับ authenticated VPN server/gateway ที่ Mac เข้าถึง LAN ร้านได้โดยไม่ต้องเปิดพอร์ตกล้องหรือไม่? (VPN passthrough/client-only ไม่ใช่คำตอบที่ต้องการ) ถ้ารองรับ ขอเอกสารวิธีตั้งค่าและข้อจำกัด WAN/CGNAT ตามวิธีนั้น — ไม่ขอ IP/password/account ของ Owner

**ถาม TP-Link** (Tapo C545D HW 1.0 / FW 1.1.7 ใน region ของ Owner): รุ่นนี้รองรับ SD playback/download จากนอก LAN หรือไม่ และมี PC/Mac API หรือ export interface ที่มีเอกสารรองรับ สำหรับดึงหลายคลิป เลือก Fixed Lens และอ่าน metadata/timestamp หรือไม่? (app-only feature ไม่เท่ากับ API) — ไม่รับรองคำตอบเชิงลบที่ยังไม่พิสูจน์

## 4. ทางทดลองที่เร็วกว่า ถ้า Owner เลือก (PROPOSED เท่านั้น)

นำ Mac เดิมไปต่อ Wi-Fi ร้านชั่วคราว หรือ export คลิปผ่านแอปแล้วนำเข้า local นอก repo — เป็นข้อเสนอ ยังไม่ดำเนินการ. ก่อนทีมอ่าน/รับวิดีโอต้องมี control ด้าน storage/permissions ผ่านเกตก่อน ไม่ขอ raw video upload ในแชต. route/auth/Fixed-lens mapping/timezone/quota/runtime เป็น check แยกกันคนละรายการ ยังไม่มีการประกาศ PASS ใดในเอกสารนี้

## 5. Next action และเกต

Owner ใช้คำถาม §3 สอบถามผู้ผลิต/ISP; PO ประเมินเอกสาร/คำตอบเรื่อง capability ก่อนเลือกวิธีและเสนอ control สำหรับ route/live ตามเกต D1→D2 ใน [PLAN](PLAN.md)/[PREPROJECT_PLAN](PREPROJECT_PLAN.md). ถ้า Owner เลือก local/manual trial แทน ให้จัด scope/พื้นที่/runtime ที่จำเป็นแยก ไม่ถือเป็นความสำเร็จของ automatic acquisition จากบ้าน. ไม่มี downloader/script ใหม่รอบนี้, ไม่ติดต่อผู้ผลิต/ISP แทน Owner, ไม่มี merge/deploy/scheduler. เอกสารผ่าน PO review โดยยังไม่ลดเกต.

---
BASELINE_CHECK: PO launcher ตรวจ HEAD เต็ม/branch ก่อนและหลัง invocation; baseline ตามบรรทัดบน. ไม่มีหลักฐาน stdout ว่า Dev รัน git เอง จึงเป็น NOT_VERIFIED_BY_DEVELOPER; ไม่ใช้ข้อความสรุปของโมเดลแทน command evidence
