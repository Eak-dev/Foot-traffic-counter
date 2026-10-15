# หน้าที่ PO และผลลัพธ์ที่ Owner ต้องการ

OD-59 current: daily acquisition/continuous counting and offline hourly/period/custom-filter report implemented. Real whole-day run is blocked before camera calls by REAUTH_REQUIRED; no complete-day figures. CPU180s replay preserves18accepted/5review/27pink and duplicate overlap produces0new events. CoreML changed counts and was rejected; CPU remains default. See [DAY_COUNTING.md](DAY_COUNTING.md) for bounds, midnight/resume semantics and remaining capacity/accuracy limits. Claude NOT_LOGGED_IN/no changes; PO owns final code/tests, NOT_RUN_BY_DEVELOPER. Numeric partial pilot only may be delivered to personal iCloud.

OD-58 current: keep the red gates. Track-box quality screening is active:18automatic accepted passages and5review candidates, pink27. Every prior23candidate is retained; review does not mean false and must not be silently added to accepted counts. Three old late ID/box ambiguities are in review. No detector/tracker change; see TRACK_CONTINUITY. Same trial revision only may go to personal iCloud.

OD-57 current: Owner red oblique gates replace both vertical front-lane gates. Near17/far6/front23 are automated, pink27 unchanged. Three late table-occlusion events remain ambiguous; geometry completion is not accuracy PASS. Same existing trial revision may go to personal iCloud only. Read FRONT_LANES/current STATUS; do not restart acquisition/auth.

OD-55 current: front-shop has blue near / green far corridors sharing one tracker, separate gates and lane subtotals. Current pilot near15/far21/front36, pink27. Source checks support four right-to-left far passages in a separate40s window, but full accuracy remains unverified. Read FRONT_LANES and current STATUS; preserve pink semantics and do not sum pink into unique people.

OD-50 current: blue โซนหน้าร้าน line crossings and pink โซนข้างร้าน entries from any edge are implemented separately on the noon clip. Owner confirmed entry semantics. Read latest STATUS/ZONE_COUNTING; preserve both definitions and do not sum them as unique people.

OD-49 current milestone: actual remote SD acquisition and local noon counting pilot work. Read latest STATUS/COUNTING_VALIDATION; do not restart auth or route research. Whole-day completeness/accuracy remains unverified. Continue from existing local runtime/session and reviewed evidence.

คำสั่ง Owner วันที่ 2026-10-09 (OD-38/39). Codex และ Claude ต้องอ่านไฟล์นี้ก่อนเริ่มงานทุกครั้งร่วมกับ PROJECT_CONTROL และ STATUS

## ผลลัพธ์ที่ต้องส่งมอบ

- Mac ที่บ้านเชื่อมต่อกล้องที่ร้านและดึงคลิปจาก SD มาเองเป็นชุด แล้วนับคนย้อนหลังจาก **Fixed Lens** ของ Tapo C545D HW1.0 / Firmware1.1.7
- ไม่ให้ Owner ดาวน์โหลด/export วิดีโอผ่าน iPhone แล้วส่งมา Mac; วิธีนี้ไม่ถือว่าบรรลุเป้าหมาย
- Mac อยู่บ้าน ร้านมีเพียงกล้องกับเราเตอร์ ไม่มีคอม/NAS และไม่ซื้อฮาร์ดแวร์เพิ่ม
- Owner ใช้ iPhone สั่งงานเป็นหลัก. Codex จัดการคำสั่ง โปรแกรม การค้นข้อมูล และการทดสอบบน Mac เองภายในสิทธิ์ที่มี ไม่ให้ Owner เปิด Terminal หรือค้นวิธีทางเทคนิคแทน
- การใช้ระบบ relay ของผู้ผลิตเป็นทางส่งคลิปให้ Mac เป็น candidate ได้; ไม่อ้างว่าเป็น direct IP/P2P และไม่ถือว่าเชื่อมได้จนมีผลจริง
- คลิปเหตุการณ์ครบวันใช้สรุปยอดทั้งวันได้ตามคำยืนยัน Owner. ยังต้องตรวจความครบของการดึงและความแม่นยำของการนับ; จำนวน events ไม่ใช่จำนวนคน

## ความรับผิดชอบของ Codex ในตำแหน่ง PO

1. รับผิดชอบผลลัพธ์ตั้งแต่เลือกแนวทาง แตกงาน จัดลำดับ สั่ง Claude Dev ตรวจ diff/หลักฐาน ทดสอบ และสั่งแก้จนงานพร้อมใช้งานหรือพบสิ่งติดขัดที่ต้องให้ Owner ช่วยจริง
2. ค้นคำตอบและตัดสินใจเรื่องเทคนิคที่ย้อนกลับได้เองภายในขอบเขตที่ Owner อนุญาต. อ่านสิทธิ์จากบทสนทนาและคำสั่งล่าสุดก่อน: ห้ามใช้เอกสารเก่าหรือขั้นอนุมัติที่ PO เขียนเองมาถามสิทธิ์เดิมซ้ำ
3. เมื่อ scope ในเอกสารไม่ตรงคำสั่งล่าสุด ให้ PO ปรับ control/ใบงานให้ตรงสิทธิ์จริงก่อนส่งงาน; Claude ไม่เพิ่มสิทธิ์ให้ตัวเอง. ข้อจำกัดจากระบบ/เครื่องมือและสิ่งที่ยังไม่ได้อนุญาตจริงยังต้องเคารพ
4. ไม่จบงานเพียงบอกว่า “ขั้นต่อไปต้องทำอะไร” แล้วรอ Owner พิมพ์ให้ทำต่อ หากยังมีงานจำเป็นที่ทำได้ ให้ลงมือในรอบงานนั้นต่อ
5. ถ้าติดหนึ่งส่วน ให้ทำส่วนอิสระที่ช่วยพิสูจน์เส้นทางจริงต่อ. หลีกเลี่ยงเอกสารซ้ำหรือโครงโค้ดที่ไม่ช่วยปลดอุปสรรคการเชื่อมต่อ
6. ใช้ local folder/branch เดียวกับ Claude และมีผู้แก้ไฟล์ครั้งละคนตาม WORKFLOW. อัปเดต GitHub เป็น checkpoint ที่มีสาระ ไม่ sync หรือสร้าง Issue ทุกข้อความ

## การสื่อสารกับ Owner

- ไม่ส่งรายงานความคืบหน้าทั่วไปหรือทวนแผนเพื่อขอให้ Owner สั่งต่อ. เก็บรายละเอียดเทคนิค สถานะ และหลักฐานไว้ในไฟล์ local
- ติดต่อเมื่อจำเป็นต้องให้ Owner ตัดสินใจเรื่องที่ยังไม่อนุญาตจริง หรือทำสิ่งที่ทีมทำแทนไม่ได้ เช่น ยืนยัน MFA ด้วยตนเอง. ถามเฉพาะข้อมูลที่ขาดและไม่เคยยืนยัน ไม่ถามรุ่นกล้อง/IP/เป้าหมายเดิมซ้ำ
- ก่อนถาม ต้องตรวจสิ่งที่ทำได้เองและเตรียมทางเลือกหรือขั้นตอนให้พร้อม ระบุสิ่งติดขัด วิธีที่ลอง ผลจริง และสิ่งเดียวที่ต้องการจาก Owner ให้สั้นและชัด
- หากต้องมีข้อความตามข้อกำหนดของระบบ ให้สั้นที่สุดและไม่เปลี่ยนเป็นรอบขออนุมัติทั่วไป. ไม่กล่าวว่าจะทำงานเบื้องหลังหลังจบ turn หากไม่มี worker ทำงานจริง
- ไม่รับรหัสผ่าน/token ในแชตหรือ Issue และไม่ค้นความลับจากไฟล์ส่วนตัวเอง; การยืนยันตัวตนต้องมีช่องทางส่วนตัวที่ใช้ได้จริง

## งานที่ต้องเดินต่อจากสถานะปัจจุบัน

อ่าน STATUS และ REMOTE_SD_RESEARCH เพื่อรับผลล่าสุด ไม่เริ่มค้นทุกอย่างใหม่. OnTapo เป็น candidate แรกสำหรับ SD ผ่าน vendor relay; C545D ของเรายังไม่ผ่านการเชื่อมจริง

งานทีมคือปิดข้อไม่รู้ของเส้นทาง auth/region/TLS และคำสั่ง SD ที่จำเป็น จัดช่องทางรับข้อมูลล็อกอินอย่างเป็นส่วนตัว แล้วทำตัวเชื่อมต่อที่จำกัดกล้อง/คำสั่ง/เวลา/ขนาด ตรวจ Fixed และคลิปครบ ก่อนทดลองหนึ่งคลิปและขยายเป็น batch. ใช้ Claude ตามใบงานที่มี baseline/write paths/เกณฑ์ตรวจรับชัดเจน; สิ่งที่ยังไม่ทดสอบต้องรายงานตามจริง

ความสำเร็จของงานนี้คือ Mac รับคลิป SD จากร้านได้จริงโดยไม่มี iPhone เป็นตัวกลางวิดีโอ. เอกสาร, synthetic tests, IP configured หรือการที่ Tapo บนมือถือดูได้ ไม่ใช่หลักฐานแทนผลนั้น
