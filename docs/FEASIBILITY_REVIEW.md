# Claude Feasibility Review — OD-36 (revision 2)

> **OD-37 ปัจจุบัน:** พบ [OnTapo SD relay และ C545D developer research](REMOTE_SD_RESEARCH.md). เลือกตรวจ/ออกแบบ adaptation ของ SD relay ก่อน Tapo Care; คงต้นฉบับ SD และ Mac บ้าน. มี author-reported TC65 download กับ PO static source review แต่ยังไม่มีผล C545D ของเรา จึง CONDITIONAL research ไม่ใช่ live/production PASS. ไม่ต้องเลือกหรือซื้อ Tapo Care ตอนนี้; auth/input/region/Fixed/quota ยังต้องพิสูจน์
> OD-36/older next actions ด้านล่างเป็นประวัติและถูกแทนเฉพาะลำดับ candidate; ไม่เปิดเกตอุปกรณ์

BASELINE: `e62a9ac31c5a238b705ff827dd9c99efad7f8168` · branch `claude/ft-d0-preflight`
สถานะงาน: เอกสารคำปรึกษาเท่านั้น ไม่มีการเข้าถึงกล้อง/เครือข่าย/SDK/credentials ในงานนี้ NOT_RUN_BY_DEVELOPER — ไม่ได้รัน unittest ตามใบงาน (เอกสารล้วน)

หมายเหตุกระบวนการที่ PO ตรวจ: Claude รอบแรก COMPLETED_LOCAL (155.3s); รอบแก้ถัดมา TIMEOUT (180.6s) ไม่ใช่ผลสำเร็จ. PO ตรวจ process แล้วปล่อย empty retained lock ก่อนรอบสุดท้าย COMPLETED_LOCAL / child exit 0 (120.2s). PO แก้ถ้อยคำด้านกระบวนการ/CGNAT/token และเพิ่มหลักฐานเว็บด้านล่างหลังรับ ownership; ไม่ใช่ผลทดลองอุปกรณ์

## คำตัดสิน 3 ข้อ (แยกตามเป้าหมาย)

**(1) SD อัตโนมัติจากบ้าน ภายใต้ข้อจำกัดเดิม (ไม่ซื้อฮาร์ดแวร์/ไม่ย้าย Mac/ไม่เดา router):**
**NO-GO ตอนนี้** — ไม่ใช่ "เป็นไปไม่ได้ตลอดกาล" แต่ **ไม่มีหลักฐานเส้นทางใดเลยที่พิสูจน์ว่าใช้งานได้จริง** ภายใต้เงื่อนไขปัจจุบัน ให้ถือว่า **เลิกพึ่งพาเส้นทาง router ที่ยังไม่ยืนยันเป็นแผนหลัก** ตามข้อสรุป PO — ไม่ต้องรอ router UI ของร้านอีกเพื่อสรุปข้อนี้

**(2) ทางเลือก cloud source (Tapo Care):** **CONDITIONAL — เสนอให้ทำ research/one-clip experiment เท่านั้น ถ้า Owner ยอมรับ source/cloud และ trial ที่ใช้ได้จริงหรือสมาชิกตามงบที่อนุมัติ** การใช้งานจริง (production) ยังเป็น **NO-GO จนกว่าจะมีหลักฐาน** auth/MFA ที่ปลอดภัย, license/compliance ของ tool, และ completeness ของ cloud history เทียบกับ SD

**(3) Manual SD export (iPhone ที่ร้าน) + local import/counting บน Mac:** **CONDITIONAL GO สำหรับการพิสูจน์ด้วยคลิปเดียว (one-clip validation) เท่านั้น** ไม่ใช่ "พิสูจน์ความแม่นยำรายวันแล้ว" และไม่ใช่ "ทำได้แน่นอน" ตามที่ draft เดิมเขียนเกินจริง — ต้องมีคลิปจริง 1 คลิป, โอนย้ายแบบ local (ไม่ผ่าน cloud/git), ตรวจ Fixed track/เวลา/duration/ground truth ก่อนจึงนับว่าผ่านขั้นนี้ ยอดรวมทั้งวันต้องมี batch คลิปครบวันก่อน ไม่ใช่สรุปจากคลิปเดียว

**การนับคน (counting) ยังคง UNTESTED แยกจาก acquisition เสมอ** — ไม่ว่าไฟล์มาจากทางใด ความแม่นยำการนับยังไม่พิสูจน์

## ทางเลือกที่พิจารณา (รวม pytapo+router เป็นข้อเดียว, ไม่เกิน 6 ทาง)

### A. Router-native gateway/VPN + pytapo (รวมเดิม #1+#3) — **excluded จากแผนหลักตอนนี้**
Dependency: ต้องมี VPN Server จริงบน F6107A ของร้าน + endpoint ที่รับ protocol นั้นได้จากบ้าน. CGNAT ขัดขวาง inbound IPv4 โดยตรงเมื่อไม่มี mapping/relay ไม่ได้พิสูจน์ว่า IPv6/overlay ทุกแบบใช้ไม่ได้. หลักฐาน: เอกสาร AIS ไม่ยืนยัน VPN Server — **ไม่เท่ากับไม่มี**. pytapo ต่อ host กล้องโดยตรง ไม่มี relay ใน media transport ที่ตรวจ และความเข้ากันได้กับ C545D ยังไม่พิสูจน์. OD-34 พบ route ทับ home LAN ไม่ผ่าน shop tunnel. **PO เลิกใช้ candidate นี้เป็นแผนหลัก ไม่รอ router UI เพื่อให้คำตัดสินรอบนี้**

### B. Tapo Care cloud (NEW, ประเมินแยกจาก SD) — CONDITIONAL research เท่านั้น
PO ให้ลิงก์ผลิตภัณฑ์/ราคา Thai (99/129 บาทต่อเดือน) เป็นข้อเท็จจริงที่ PO จัดหามา ไม่ใช่สิ่งที่ฉันยืนยันเอง — ฉันไม่เปิด URL เหล่านี้ในงานนี้ (ไม่มีสิทธิ์เครือข่าย) การประเมินอิสระของฉัน: **cloud ≠ SD** — cloud history เป็นแหล่งข้อมูลคนละแหล่ง ไม่ควรสมมติว่าครอบคลุมเหตุการณ์เท่า SD หรือ MFA/auth จะใช้ง่ายกว่า ยังไม่มีหลักฐาน trial eligibility, API เข้าถึงจาก Mac, หรือ Fixed-lens mapping บน cloud clip จึงเป็นเพียง **ข้อเสนอให้วิจัย** ไม่ใช่แผนที่พร้อมทำ

### C. tapo-cli (community batch-cloud tool, งานรองรับข้อ B) — evidence เท่านั้น ห้ามรันทันที
PO ตรวจ commit `8bb5f6d2f231cec55d43465f3169ac58f3d4c219` แล้วพบ: ไม่พบไฟล์ license ในทรี, `verify=False` ปิด TLS validation พร้อมปิด warning, เขียน token/ผล login เป็น JSON plaintext โดยไม่ได้พิสูจน์ว่าเก็บ password, มีการเดา MFA endpoint และไม่มี byte/deadline quota ของงานนี้. เป็น **static review ของ PO**. ฉันประเมินอิสระว่า tool เป็นหลักฐานแนวทาง community batch-cloud ไม่ใช่ผลทดสอบ C545D/Mac หรือ vendor-supported API. ต้องตรวจสิทธิ์ใช้โค้ด, TLS, secure credential/token storage และ quota/audit ก่อนทดลองจริง; ไม่รัน upstream ตรง ๆ

### D. Manual iPhone export + local import (ทางสำรองสำหรับ counting)
ไม่มี dependency เพิ่มที่ร้าน ใช้แอป Tapo ที่มีอยู่ ข้อแก้ไขจาก draft เดิม: นี่คือ **CONDITIONAL** ไม่ใช่ "ทำได้แน่" — ต้องพิสูจน์ด้วยคลิปจริง 1 คลิปก่อน (ดูคำตัดสิน (3)) ไม่ scale เป็น batch อัตโนมัติรายวันเพราะต้องมีคนทำซ้ำทุกรอบ เป็นคำถามเรื่องยอมรับ manual workflow ไม่ใช่คำถามเชิงเทคนิคล้วน

### E. Vendor partner API / Android emulator — excluded จากขั้นต่อไป (high-cost, ไม่พิสูจน์)
PO ดึง Open API landing page ไม่ได้; marketing PDF ปี 2024 กล่าวถึง partner SDK/กล้องบางรุ่น ไม่ใช่เอกสาร public C545D remote-SD endpoint. ไม่อ้างว่าอ่าน API portal สำเร็จ. Emulator บน Intel Mac (i7-4870HQ, 16GiB RAM, เหลือ 18.1GiB disk) ยังไม่ทดลอง ABI/OS acceleration; Intel ระบุ CPU รองรับ VT-x/EPT แต่ไม่รับรอง Tapo APK. Studio+emulator ระบุพื้นที่ขั้นต่ำ 16GB จึงไม่ติดตั้งโดยเดา. เกณฑ์ทดลองต้อง export ไฟล์ต้นฉบับได้ ไม่ใช่แค่ playback. ไม่เลือกสองทางนี้เป็นขั้นต่อไป

**ไม่รวมในตาราง:** privacy VPN เดี่ยว, DDNS เดี่ยว, cloud VPS เดี่ยว, Tailscale (ต้อง node ที่ร้านซึ่งไม่มี), renumber subnet, reverse tunnel ฝั่งบ้านอย่างเดียว, custom firmware/router feature ที่ไม่มีเอกสาร — ไม่สร้าง gateway ที่ร้านขึ้นมาเอง

## คำแนะนำของ Claude และ stop rule

**ทำทางเดียวต่อไป: ข้อ D (manual export 1 คลิปจริง + local import) เพื่อพิสูจน์ one-clip validation ก่อนอื่นใด** เพราะใช้เวลา/ทรัพยากรน้อยสุด ไม่ต้องรอ cloud auth หรือ router UI และให้หลักฐาน ground-truth ชุดแรกสำหรับงานนับคนซึ่งเป็นปัญหาที่แยกจาก acquisition อยู่แล้ว

**Stop rule:**
1. หลังอนุมัติ scope/storage: ได้คลิปจริง 1 คลิป ตรวจ Fixed track/เวลา/duration และนับมือไว้ → เป็นหลักฐาน acquisition หนึ่งคลิปเท่านั้น. งานนับจริง/phase ถัดไปยังต้องผ่านเกตและทดสอบตาม PLAN; ไม่เปิดเกตอัตโนมัติ. ยอดรายวันต้องมี source ครบวัน
2. ตรวจแล้วไม่ตรง/track ผิด/เวลาไม่ถูก → หยุดที่ adapter/mapping ไม่เดา config อื่นต่อ และไม่สรุปว่า manual path ใช้ไม่ได้ทั้งหมดจากความล้มเหลวครั้งเดียว
3. **ไม่ทำ:** offline scaffolding เพิ่มเติม (core/bridge ใหม่), รัน tapo-cli แบบไม่ตรวจ, ติดตั้ง emulator, สมัคร partner API — ก่อนขั้น 1 เสร็จ

**Fallback ถ้า cloud auth/download/Fixed/completeness ล้มเหลว (ข้อ B/C):** กลับไปใช้ข้อ D เป็นแหล่งเดียวสำหรับพัฒนา/ทดสอบระบบนับคนต่อไป และพักเรื่อง automation (ทั้ง router และ cloud) ไว้จนกว่า assumption ใดข้อหนึ่งจะเปลี่ยนจริง ไม่เสนอซื้อฮาร์ดแวร์ร้านหรือย้าย Mac เป็นทางแก้

## UNKNOWN ที่ยังไม่มีหลักฐาน (ไม่ใช่สมมติว่าทำไม่ได้)

- F6107A มี VPN Server feature จริงหรือไม่ (ไม่ใช่สิ่งที่ต้องรอตรวจเพื่อปิดคำตัดสิน (1) อีกแล้ว)
- Tapo Care trial/eligibility, MFA flow, และว่า cloud history ครอบคลุมเท่า SD หรือไม่
- pytapo กับ C545D ตัวจริง (ยังไม่ทดสอบกับอุปกรณ์จริง)
- TP-Link public remote-SD endpoint สำหรับ C545D ตาม region/build ของ Owner
- Android emulator บน Intel Mac รัน Tapo APK ได้จริงหรือไม่

## สรุปภาษาไทยสำหรับ Owner

ตอนนี้ไม่มีทางดึงคลิปอัตโนมัติจากบ้านที่พิสูจน์แล้ว. Manual SD export/local import เป็นข้อเสนอให้พิสูจน์หนึ่งคลิปก่อน ส่วน Tapo Care เป็นทางทดลองที่ตรงเป้าหมาย Mac อยู่บ้านเมื่อ Owner ยอมเปลี่ยน source/ใช้คลาวด์/งบสมาชิก. ยังไม่ใช่ระบบที่ทำงานแล้ว และความแม่นยำการนับยังไม่ทดสอบ

## PO source verification และข้อเสนอสำหรับเป้าหมายบ้าน→ร้าน

- [C545D ประเทศไทย](https://www.tp-link.com/th/home-networking/cloud-camera/tapo-c545d/) ยืนยัน Tapo Care ระดับรุ่น. [ตารางราคาไทย](https://www.tapo.com/th/faq/367/) ระบุ Basic 1 กล้อง 99 บาท/เดือน, Premium 129 บาท/เดือน; ต้องตรวจราคาจริง/สิทธิ์ trial ในบัญชีก่อนจ่าย ไม่ซื้อในงานนี้
- [tapo-cli README/source ที่ pin](https://github.com/dimme/tapo-cli/tree/8bb5f6d2f231cec55d43465f3169ac58f3d4c219) ระบุ batch-cloud download บน Debian; ไม่ใช่หลักฐาน Mac/C545D ผ่าน. [FAQ ผู้ผลิต](https://www.tp-link.com/sg/support/faq/2945/) ยืนยันกล้องบันทึก cloud ได้เมื่อแอปปิดหาก internet เสถียร และเตือนคลิปอาจขาดเมื่อ upload มีปัญหา
- [คำตอบผู้ผลิตปี 2025](https://community.tp-link.com/en/business/forum/topic/817966) อธิบาย SD/cloud มีช่วงท้ายคลิปต่างกันในบริบทกล้องเสียบไฟ; ไม่ใช้คำตอบนี้รับรองตัวเลขของ C545D. ไม่สมมติว่า SD เดิมย้อนหลังถูกส่ง cloud หรือ cloud ครบทุกเหตุการณ์ตาม OD-15
- PO เสนอศึกษาทาง **กล้อง → Tapo Care → Mac บ้าน → นับ local** เป็นตัวเลือกอัตโนมัติถัดไปเมื่อ Owner ยอมรับข้อเปลี่ยนแปลง; Claude แนะนำ manual หนึ่งคลิปเป็นการพิสูจน์ที่ต้นทุนต่ำกว่า. ทั้งสองยังเป็น PROPOSED ไม่เปลี่ยน SD spec เงียบ ๆ
- ข้อเสนอทดลอง cloud: ตรวจสิทธิ์ tool/auth/TLS ก่อน, หนึ่งคลิปใหม่ Fixed, ไม่เกิน 1 GiB และ 10 นาที, storage นอก git/นอกโฟลเดอร์ sync, retention 24 ชั่วโมง; ค่า subscription สูงสุด 129 บาทสำหรับหนึ่งเดือนเฉพาะเมื่ออนุมัติและราคาจริงไม่เกินเพดาน. ไม่มี auto-renewal ที่อนุมัติ; ไม่เปลี่ยน settings อัตโนมัติ. หากดึง/ตรวจ Fixed ไม่ผ่านให้หยุด ไม่ลอง MFA endpoint ที่เดาหรือซื้อเพิ่ม. One-clip ผ่านจึงเสนอ complete-day comparison กับ SD/ground truth แยก; ก่อนครบยังไม่รายงานยอดทั้งวันจาก cloud

## สรุปสำหรับนักพัฒนา (developer summary)

- งานที่ทำ: อ่านเอกสาร project ที่ไม่ลับและ primary-source packet ที่ PO ตรวจแล้ว เขียนบันทึก feasibility ใหม่แทน draft เดิม
- ไฟล์ที่เปลี่ยน: `docs/FEASIBILITY_REVIEW.md` เท่านั้น
- ผลทดสอบ: NOT_RUN_BY_DEVELOPER
- ข้อแตกต่างจาก draft เดิม: ปิดการพึ่งพา router route เป็นแผนหลัก, เพิ่มทางเลือก cloud (B/C) ตามข้อมูลที่ PO จัดหา, แก้ข้อสรุป manual export จาก "ทำได้แน่" เป็น CONDITIONAL one-clip only
