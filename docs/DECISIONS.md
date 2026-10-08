# Owner Decisions — Foot-traffic-counter

อัปเดต 2026-10-08 · บันทึกข้อสรุปที่มีผลต่องาน ไม่ใช่สำเนาแชตหรือข้อมูลลับ
อ่านร่วมกับ PROJECT_CONTROL, PLAN และ STATUS; หากเปลี่ยนข้อสรุปให้เพิ่มรายการ supersedes ไม่ลบประวัติ

| ID | ข้อสรุป | แหล่ง / สถานะ | ผลต่อทีม |
| --- | --- | --- | --- |
| OD-01 | ไม่ซื้อฮาร์ดแวร์เพิ่ม; ซอฟต์แวร์ซื้อได้เมื่อเสนอเหตุผลและค่าใช้จ่ายเฉพาะ | Owner 2026-10-06 | ยกเลิกแผนบังคับซื้อ Pi; ไม่อนุมัติสมาชิก/ซื้ออัตโนมัติ |
| OD-02 | ใช้ MacBook เดิมที่บ้าน กล้องอยู่ร้านคนละเครือข่าย | Owner | รีโมต Mac ได้ไม่เท่ากับเข้าถึงกล้องได้ |
| OD-03 | วิเคราะห์ย้อนหลังเป็นชุดได้ ไม่ต้อง real time; เที่ยงคืนเป็นตัวอย่าง ไม่ใช่เวลาที่ล็อกแล้ว | Owner | ยังไม่ตั้ง scheduler |
| OD-04 | นับคนเดินผ่าน ไม่นับคนนั่งเก้าอี้; ต้องกรองวันที่และช่วงเวลาได้ | Owner requirement | ทดสอบ seated negatives และช่วงเวลารายงาน |
| OD-05 | ต้นฉบับอยู่ microSD ในกล้อง เป็น event clips ความยาวต่างกัน ราวไม่เกิน 3 นาที มีช่วงว่าง | Owner | จำนวนคลิปไม่เท่าจำนวนคน; ไม่มีคลิปไม่ยืนยันว่าไม่มีคน |
| OD-06 | ให้ Claude ทำส่วนดึงข้อมูลก่อนระบบนับคน พร้อมแผนและรายการที่ติด | Owner | acquisition-first ไม่สลับไปทำ ML/dashboard ก่อน |
| OD-07 | อนุญาตให้ PO สั่ง Claude ผ่านรีโมต Mac | Owner + ผลรันจริง D0 | ไม่ต้องให้ Owner คัดลอก prompt เอง |
| OD-08 | Tapo C545D; AIS Fibre 1000/200; ZTE F6107A, HW V9.0.09, FW F6107A_PON_4.1 | Owner/ภาพและ PR comments | ไม่ขอข้อมูลนี้ซ้ำ; camera firmware ยังไม่ทราบ |
| OD-09 | ไม่ต้องวนทดลองผ่านมือถือ/ขอรูปเราเตอร์เพิ่ม ให้ Claude ทดลองดึงจริง | Owner + comment 6014447731 | รับคำสั่งทดลองแล้ว; ยังติด implementation/endpoint/auth/route ไม่ใช่ขาดคำสั่งทั่วไปซ้ำ |
| OD-10 | ให้ Claude แจ้งข้อมูลที่ต้องใช้และวิธีตั้ง Tapo | Owner; Claude advisory ตอบแล้ว | เป็นคำแนะนำ ไม่ใช่การเปลี่ยนค่า/ผลทดลองกล้อง |
| OD-11 | อัปเดต GitHub ตลอดที่คุยกันเพื่อให้ Claude รู้เฟสและ blocker | Owner standing workflow บันทึก 2026-10-07 | ทุกการเปลี่ยนสาระงานให้อัปเดต docs/PR และตรวจ read-back ในเทิร์นนั้น ไม่ต้องขออนุมัติ docs-only sync ซ้ำ |

## Owner workflow decisions — 2026-10-07

| ID | ข้อสรุป | แหล่ง / สถานะ | ผลต่อทีม |
| --- | --- | --- | --- |
| OD-12 | Codex และ Claude ใช้ local folder เดียวและ branch งานเดียวกัน; พัฒนา local เป็นหลักและอัปเดต repo ตามสมควร | OWNER_DECISION: Owner สั่ง “ปรับตามที่คุณแจ้งเลย … folder local และ Branch เดียวกัน … local เป็นหลัก … อัปเดท repo ตามสมควร” | Supersedes จังหวะ remote sync ทุกเทิร์นของ OD-11. อัปเดตสถานะ local; push ที่ reviewable milestone/ข้อสรุปหรือ blocker สำคัญ/handoff ที่ต้องใช้ remote/Owner request. สำเนาเก่า dormant ไม่ลบ; main ยังรอ Owner merge |
| OD-13 | ให้ Codex ออกแบบและปรับ workflow เพื่อสั่ง Claude เป็น Dev ตามข้อเสนอที่รีวิวแล้ว | OWNER_DECISION: คำสั่งเดียวกับ OD-12 | อนุญาต scoped local launcher/เอกสาร/synthetic tests และ Claude รัน unittest ใน strict sandbox; หนึ่ง writer ต่อครั้ง. PO review/checkpoint; git-write ของ Claude ต้องมี publication task/policy แยก. Supersedes D0 file-only developer restriction แต่ไม่เปิดเกตกล้อง/ติดตั้ง/production/merge/deploy/scheduler |
| OD-14 | Merge PR #2 ก่อนทำต่อ เพื่อเป็นเวอร์ชันแรก | OWNER_DECISION: Owner สั่งโดยตรง 2026-10-07; GitHub ยืนยัน MERGED | อนุญาต PO merge PR #2 ครั้งนี้; baseline `b05b8fb` / `v0.1.0`. ใช้ folder/branch เดิมต่อและบันทึกหลัง merge ใน local. ไม่ใช่สิทธิ์ merge อัตโนมัติครั้งถัดไปหรือเปิดเกตอุปกรณ์/deploy; replaces สถานะรอ merge ใน OD-12 |
| OD-15 | กล้องบันทึกเฉพาะเมื่อมีคนเดินผ่าน; รวมยอดจากคลิปเหตุการณ์เป็นยอดนับทั้งวันได้ | OWNER_CONFIRMED / OWNER_DECISION 2026-10-07: Owner แก้ความเข้าใจข้อ 4 โดยตรง | Supersedes ข้อห้ามรายงานยอดทั้งวันและการตีความช่องว่างเดิมใน PLAN/CONTROL รวมถึง OD-05; คงเกณฑ์ดึงคลิปครบตามต้นทางและทดสอบความแม่นยำ ไม่ใช่ผลทดสอบกล้องหรือระบบนับที่สำเร็จแล้ว |
| OD-16 | Tapo C545D, Hardware Version 1.0, Firmware Version 1.1.7 | OWNER_IMAGE 2026-10-07: หน้า Device Info ในภาพแนบ | Supersedes camera Hardware/Firmware UNKNOWN ใน OD-08 และสถานะปัจจุบัน; ไม่ขอซ้ำ. Adapter/auth/route ยังต้องตรวจ. บันทึกเฉพาะค่าที่อ่านได้ ไม่เก็บภาพหรือพาธไฟล์แนบใน git |
| OD-17 | ให้เริ่มงานถัดไปและแจ้งส่วนที่ต้องให้ Owner ช่วย | OWNER_INSTRUCTION 2026-10-07 | ทีมเริ่ม research/source review และส่ง Claude ทำแผนทดลองหนึ่งคลิปแบบ offline; ใช้ spec OD-15/16. ยังไม่มีข้อมูล target/route/คลิป/เพดาน live ครบ ไม่ตีความเป็นสิทธิ์เปลี่ยนกล้อง/เครือข่าย/ติดตั้งทั่วเครื่อง |
| OD-18 | Advanced Settings: Camera Account On; Network Settings Off; Powerline Frequency Auto; UPnP Off; Diagnostics Off | OWNER_IMAGE 2026-10-08 | ยืนยันเฉพาะค่าหน้าจอ; ไม่ขอ Camera Account ซ้ำ. Third-Party Compatibility ไม่ปรากฏในภาพจึงยัง UNKNOWN; ไม่อนุมาน internet/route จาก Network Settings Off และไม่อ้าง SD auth PASS. ไม่เปลี่ยนการตั้งค่า ไม่รับรหัสผ่าน และไม่เก็บภาพใน git |
| OD-19 | ให้ PO ตรวจคอมพิวเตอร์โดยตรงว่าต้องเตรียมอะไร; Owner ยืนยันใช้แอป Tapo ได้แล้ว | OWNER_INSTRUCTION / OWNER_CONFIRMED 2026-10-08 | อนุญาต local read-only runtime/พื้นที่/power/VPN presence/status inspection; ไม่อ่านความลับหรือเปลี่ยนค่า. ไม่ขอ Owner ตรวจ Mac/ยืนยัน app readiness ซ้ำ; ข้อมูลหน้างานที่ Mac ตรวจไม่ได้ให้แจ้งเฉพาะที่จำเป็น |

OD-05/08 เก็บข้อสรุปเดิมเป็นประวัติ; เรื่องยอดทั้งวันใช้ OD-15 และ camera version ใช้ OD-16 ตั้งแต่รอบนี้. OD-11 เก็บเป็นประวัติการตัดสินใจเดิม; ส่วนจังหวะ GitHub ใช้ OD-12 ตั้งแต่รอบนี้. Model service ของ Claude ใช้รับเฉพาะ context งาน/โค้ดที่ไม่ลับตามคำสั่งมอบหมาย ไม่ส่ง secrets หรือข้อมูลกล้อง. พาธ canonical checkout เก็บเฉพาะ local config ที่ Git ไม่ติดตาม.

## Owner evidence — 2026-10-08

- **OD-32 — OWNER_IMPLEMENTATION_APPROVAL:** Owner ตอบ “จัดการได้เลย” ต่อข้อเสนอ reuse pytapo. PO เริ่ม scoped offline acquisition core ผ่าน Claude: guard ของ SD request, bounded normalized listing/chunk transfer, Fixed/manifest/dedup helpers และ synthetic tests. ไม่ import/เรียก upstream หรือเปิด live route/auth/video; auth/media binding, stalled transport interruption และ real-file publication ยังเป็นงานแยก. Scope และ write paths อยู่ PROJECT_CONTROL; ไม่แก้ launcher/policy ไม่ติดตั้งเพิ่ม.

- **OD-31 — OWNER_RESEARCH_REQUEST:** Owner ขอค้นวิธีสร้างโปรแกรมเรียกใช้ GitHub library ของผู้อื่น. PO audit 4 candidates แบบ static ที่ pin commit แล้ว เสนอ `pytapo==3.4.26` ซึ่งติดตั้งใน isolated runtime อยู่แล้วเป็น backend ของ scoped CLI; เพิ่ม LIBRARY_REUSE_PLAN. ยังไม่ใช่ implementation/live/install approval เพิ่ม. พบ upstream read-error recovery อาจเรียก `setCruise(False)` จึงต้อง guard/patch ก่อน device trial; C545D compatibility/private route ยังไม่ยืนยัน. ไม่ส่งข้อมูลจริงให้ Dev และไม่เปลี่ยนต้นฉบับ SD เป็น Tapo Care.

- **OD-30 — OWNER_INSTRUCTION:** Owner ย้ำให้ Codex ค้นหาคำตอบเอง ไม่มอบงานค้นหา VPN/router/API หรือสอบถามผู้ผลิตให้ Owner. Supersedes next action ที่รอ Owner ถาม AIS/TP-Link ใน ROUTE_DECISION/STATUS; ทีมรับผิดชอบ source research และเสนอทางที่มีหลักฐาน. ไม่ตีความการค้นหาว่าอนุญาตส่งข้อความในนาม Owner, ใช้บัญชี/รหัสลับ หรือเปลี่ยนอุปกรณ์. ขอ Owner เฉพาะงานหน้างาน/การตัดสินใจที่ทีมทำแทนไม่ได้จริง พร้อมข้อเสนอที่ตรวจแล้ว.

- **OD-29 — OWNER_WORKFLOW:** Owner ให้ทีมทำงานต่อเนื่องจนจบงานที่ทำได้ใน scope และลดข้อความความคืบหน้าเหลือปัญหาหรือคำถามที่จำเป็น. PO เก็บรายละเอียดใน STATUS/local evidence และสรุปผลเมื่อจบชุดงาน; ไม่รอ Owner ยืนยันซ้ำสำหรับงานที่อนุมัติแล้ว. ไม่ใช่คำสั่งสร้าง scheduler/worker และไม่ขยาย camera/network/video/merge gates.

- **OD-28 — OWNER_SUBMITTED / PO_OBSERVED:** Owner แจ้ง “ทำแล้ว” หลังขั้นตอนส่ง private IPv4 ผ่านหนึ่งโฟลเดอร์ว่างใน dedicated iCloud handoff. PO พบรายการที่ส่งบน Mac ตรวจ canonical RFC1918/หนึ่งเป้าหมาย/โฟลเดอร์ว่างโดยไม่ตาม symlink แล้วบันทึกด้วย atomic helper เดิมลง ignored local config mode 0600 ไม่เขียนทับ ไม่แสดงค่า/ชื่อจริง/path. Config validation PASS; `check` คืน endpoint configured / BLOCKED, route/auth/download NOT_TESTED, camera requests 0. Supersedes endpoint missing และ sync observation pending ใน OD-26/27 สำหรับสถานะปัจจุบัน; ยังไม่ได้รับบัญชี/รหัสผ่าน และไม่เปิดเกตกล้องหรือพิสูจน์เส้นทางบ้าน→ร้าน. Code/tests ไม่เปลี่ยน; NOT_RUN_BY_DEVELOPER รอบนี้.

- **OD-27 — OWNER_REPORTED / PO_OBSERVED:** Owner แจ้งเปิด iCloud Drive อยู่. PO ตรวจเพียง directory readiness บน Mac (พบ) และสร้างโฟลเดอร์ใหม่ `FootTrafficSetup` กับ non-sensitive marker `MAC-READY.txt`; ไม่อ่านไฟล์ iCloud เดิม ไม่แสดง path/account และไม่เปลี่ยน sync/account. รอ Owner เห็น marker บน iPhone จึงยืนยัน cross-device sync; ไม่สมมติว่า Apple Account ตรงกันจาก directory presence. วิธีรับ endpoint ที่เตรียม: Owner สร้างหนึ่งโฟลเดอร์ว่างภายในจุดนี้ ตั้งชื่อเป็น IPv4 ภายในจาก Tapo แล้วแจ้งเฉพาะ “ทำแล้ว”. PO รับเฉพาะชื่อโฟลเดอร์ที่ Owner ระบุผ่านการกระทำนี้ ตรวจ RFC1918/ความกำกวมก่อนบันทึก config ใน Mac โดยไม่พิมพ์ค่า/ชื่อ/path ลง output หรือ Git. ไม่ใช้ชื่อโฟลเดอร์สำหรับ password/account/video ไม่แชร์ folder/public link ไม่เปิดเกตกล้องหรือถือว่า VPN พร้อม.

- **OD-26 — OWNER_WORKFLOW:** Owner ทำงานกับทีมผ่าน iPhone เป็นหลัก ใช้ Mac เองเมื่อสะดวก และมอบหมายงานบน Mac ให้ Codex จัดการ. ยกเลิกการให้ Owner เปิด Terminal/รัน configure/check เป็นขั้นตอนจำเป็นของงาน. Codex รับผิดชอบคำสั่ง local/เตรียมเครื่อง/ทดสอบและรายงานตาม scope ที่อนุมัติ; Owner ทำเฉพาะงานใน Tapo/ตัดสินใจ/ส่งข้อมูลผ่านช่องทางส่วนตัวที่พร้อม. ยังไม่มี IP หรือ credential input และไม่มีสิทธิ์ค้นไฟล์ส่วนตัวทั้งเครื่อง. PO ตรวจเครื่องมือที่มีแล้วไม่พบช่องรับค่าลับจาก iPhone ลง local Mac โดยตรง; ถาม readiness ของ iCloud Drive เพื่อประเมินไฟล์ส่วนตัวที่ Owner ระบุเป็นรายไฟล์ ไม่ถือว่า sync/account/channel พร้อมแล้ว. ไม่ส่ง IP/password ในแชตหรือ GitHub. ข้อจำกัด route/SD/Fixed/quota เดิมยังอยู่.

- **OD-24 - OWNER_INSTRUCTION 2026-10-08:** Owner authorized Mac software installation/home trials and requested IP/third-party guidance. PO installed isolated acquisition prerequisites; metadata/version checks PASS, device route/auth/SD NOT_TESTED. Automatic review initially blocked control maintenance; OD-25 explicitly resolves that approval blocker. No router/camera/OS-security changes, purchases, merge or scheduler. Detailed runtime evidence stays ignored/local.


- **OD-25 — OWNER_APPROVED MAINTENANCE:** Owner ตอบ “ได้” ต่อ scope ที่ PO เตรียม: ปรับ PROJECT_CONTROL/เอกสารเพื่อบันทึก OD-24 และให้ Claude ทำช่องกรอก IP เฉพาะในเครื่องพร้อม offline check. ยกเลิกสถานะ maintenance approval pending ของ OD-24; ไม่เปลี่ยน launcher/policyหรือให้ Claude ติดตั้ง/เชื่อมกล้อง. สิทธิ์กรอก IP ไม่ใช่ live PASS. Private route/endpoint ยังขาด และไม่มี camera/auth/SD request ในงานนี้.

- **OD-20 — OWNER_IMAGE:** Tapo Version **3.21.106**, Third-Party Compatibility **On**, Privacy Mode **Off**; Firmware **1.1.7** ตรงข้อมูลเดิม. Supersedes Third-Party Compatibility UNKNOWN ของ OD-18 สำหรับสถานะปัจจุบัน; ไม่ขอข้อมูลนี้ซ้ำ. ยืนยันค่าหน้าจอเท่านั้น ไม่ใช่ auth/route/SD export PASS. ไม่เปลี่ยนค่า ไม่เก็บภาพ/ชื่อกล้อง/SSID/พาธแนบใน git.

- **OD-23 — OWNER_DECISION / OWNER_CONFIRMED 2026-10-08:** ใช้ **Fixed Lens เป็นมุมหลักสำหรับการนับ ไม่ใช้ PT Lens**; Owner อยู่ที่ร้านเมื่อเปิด playback ในภาพ OD-22. Supersedes มุมหลักที่เป็นข้อเสนอและตำแหน่งโทรศัพท์ UNKNOWN ใน OD-22 สำหรับสถานะปัจจุบัน. ไม่ขอซ้ำ. ภาพเป็นหลักฐาน playback ขณะอยู่ร้าน ไม่ใช่ remote access/export จากบ้าน; ยังไม่ยืนยันว่าโทรศัพท์ใช้ Wi-Fi ร้านหรือ mobile data. Adapter ต้องพิสูจน์ว่าไฟล์มีมุม Fixed ที่ตรงต้นทาง; หากได้ PT อย่างเดียวให้หยุด ไม่ใช้แทนหรือรวมยอดสองเลนส์. ไม่เปลี่ยนมุม/ตั้งค่ากล้องหรือเปิดเกต live.

- **OD-21 — OWNER_CONFIRMED 2026-10-08:** ร้านไม่มีคอมพิวเตอร์/NAS มีเฉพาะกล้องและเครือข่ายเดิมตามข้อมูลก่อนหน้า. ตัดทางเลือกใช้ shop computer/NAS เป็น gateway ออกจากแผน ไม่ถามซ้ำ ไม่ซื้อเพิ่ม. VPN ที่บ้านอย่างเดียวไม่สร้างทางเชื่อมเข้าร้าน; ความสามารถเราเตอร์เดิมยังไม่ยืนยัน.
- **OD-22 — OWNER_IMAGE 2026-10-08:** คลิปเป้าหมายในรายการ SD: วันที่ 8 Oct BE 2569 (2026-10-08), เวลาเริ่มที่แสดง **09:51:53**, ความยาว **03:00**. ภาพ playback แสดง Fixed Lens ด้านบนและ PT Lens ด้านล่าง; เวลา overlay 09:51:58 และ timeline 09:51:57 เป็นตำแหน่งเล่น ไม่ใช่เวลาเริ่มรายการ. ข้อความ Owner `9:51:63` ไม่ใช่เวลา valid; PO ใช้ค่ารายการในภาพเพื่อระบุเป้าหมาย ไม่แปลงวินาที 63 เอง. เวลา/ความยาวเป็น UI evidence ยังไม่ใช่ metadata ไฟล์หรือ timezone ที่ยืนยันแล้ว. Fixed Lens เป็นข้อเสนอของ PO สำหรับมุมหลัก ยังไม่ใช่ Owner decision. ตำแหน่งโทรศัพท์ขณะดูภาพยังไม่ทราบ; ไม่อ้าง remote export/API PASS และไม่เก็บภาพ/ข้อมูลบุคคลใน git.

## สิ่งที่ยังเป็นข้อเสนอ ไม่ใช่ Owner-approved implementation


- เดินกลับข้ามเส้นนับอีกครั้ง, ตำแหน่งเส้น, reserve 10 GiB, ระยะเวลาเก็บ, เพดาน bytes และเวลารัน ยังรอตัดสินใจ/ทดสอบ
- `pytapo==3.4.26` ตรวจ static/ติดตั้ง runtime แยกแล้ว OD-24; ยังเป็น candidate ที่ไม่พิสูจน์กับ C545D จริง. RTSP/live view ผ่านไม่ใช่ SD export ผ่าน
- Camera Account กับ TP-Link ID แยกกัน; ชนิดบัญชีที่ downloader ต้องใช้ขึ้นกับวิธี/รุ่น ต้องตรวจและกรอกผ่านช่องทางส่วนตัวบน Mac
- Third-Party Compatibility: ตรวจสถานะก่อน ไม่เปิดเอง; event recording เดิมไม่ต้องเปลี่ยนเพื่อดึงคลิปที่มีอยู่
- คำสั่งให้ทดลองดึงไม่ใช่อนุมัติ reset/reboot/format SD, เปิดพอร์ต/DMZ, ปิด MFA, ติดตั้งทั่วเครื่อง, ซื้อของ, merge/deploy หรือ scheduler
- การรับข้อมูลลับแบบ local และตัวดาวน์โหลดยังเป็นงานทีมที่ต้องทำ ไม่ผลักให้ Owner ออกแบบ VPN หรือเขียนโปรแกรม

## หลักฐาน

- [PR #2](https://github.com/Eak-dev/Foot-traffic-counter/pull/2) — merged ตาม OD-14; baseline main/tag `v0.1.0`
- [กล้อง/แพ็กเกจ](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6013505806)
- [ฉลากเราเตอร์](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6013831335)
- [Router Device Info](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6014086882)
- [คำสั่งทดลองและผล inspection](https://github.com/Eak-dev/Foot-traffic-counter/pull/2#issuecomment-6014447731)
- OD-10/11: บทสนทนา Owner กับ PO ล่าสุด; ไม่แนบภาพ/วิดีโอ/credentials. ผลรัน Claude advisory ที่รายงานในแชตเป็นคำแนะนำ ไม่ได้ทดสอบกล้อง

เมื่อมีข้อมูลใหม่ ให้ระบุวันที่/ที่มา/OWNER_DECISION หรือ PROPOSED หรือ OBSERVED/ผลต่อ scope/งานถัดไป และรายการเดิมที่ถูกแทนที่
