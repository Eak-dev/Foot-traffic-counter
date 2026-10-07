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

## สิ่งที่ยังเป็นข้อเสนอ ไม่ใช่ Owner-approved implementation

- เดินกลับข้ามเส้นนับอีกครั้ง, ตำแหน่งเส้น, reserve 10 GiB, ระยะเวลาเก็บ, เพดาน bytes และเวลารัน ยังรอตัดสินใจ/ทดสอบ
- `pytapo` เป็น candidate ยังไม่ pin/ติดตั้ง/พิสูจน์กับ C545D จริง; RTSP/live view ผ่านไม่ใช่ SD export ผ่าน
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
