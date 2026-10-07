# ผลตรวจ Mac สำหรับเตรียมดึง SD — 2026-10-08

Owner อนุญาตให้ PO ตรวจคอมพิวเตอร์และยืนยันว่าใช้แอป Tapo ได้แล้ว (OD-19). ตรวจ local แบบอ่านอย่างเดียว; ไม่อ่านรหัสผ่าน ไม่ติดตั้ง ไม่เปลี่ยนค่า และไม่ส่งคำขอไปกล้อง/ร้าน.

## ผลที่ตรวจได้

| รายการ | ผล | ขอบเขตหลักฐาน |
| --- | --- | --- |
| OS / สถาปัตยกรรม | macOS 14.8.9 / x86_64 | อ่านระบบ local |
| พื้นที่ว่าง | 18.46 GiB | snapshot จาก doctor; ไม่ใช่โควตาหรือ reserve ที่ Owner อนุมัติ |
| Python ของเครื่อง | 3.9.6 | version บน PATH; ใช้เครื่องมือ D0 ได้ |
| Python ที่มากับ Codex | 3.12.14 | bundled runtime ที่ tool ของ Codex ระบุ; ไม่แก้ runtime นี้ |
| Python 3.13 / 3.12 / 3.11 บน PATH | ไม่พบ executable ตามชื่อที่ตรวจ | ไม่ใช่การค้นทุกโฟลเดอร์หรือทุก virtualenv |
| ffmpeg / ffprobe | ไม่พบบน PATH หรือ bundled override/fallback ที่ตรวจ | ยังไม่พร้อมสำหรับ candidate MP4 download |
| pytapo / aiofiles / requests / urllib3 / pycryptodome / rtp / python-kasa | ไม่พบ package metadata ใน Python 3.9.6 และ bundled 3.12.14 ที่ตรวจ | ไม่ import package; ไม่ค้น environment อื่นทั้งหมด |
| Homebrew | ไม่พบบน PATH | ไม่จำเป็นต้องติดตั้ง Homebrew เพื่อทำงาน D0 |
| git / gh / Claude | พบ executable | การมีอยู่ไม่ใช่ผล auth/download ใหม่ |
| VPN profile ของ macOS | scutil --nc list อ่านสำเร็จ; ไม่พบ profile ในรายการนี้ | ไม่พิสูจน์ว่าไม่มี VPN แบบอื่น |
| VPN tools/apps ที่ตรวจ | ไม่พบ tailscale/wg/openvpn บน PATH; ไม่พบ Tailscale/WireGuard/OpenVPN Connect/Tunnelblick ใน /Applications | ไม่ได้ค้น home หรือ config ความลับ |
| Default route | interface ประเภท physical/other | อ่าน routing table เท่านั้น ไม่แสดง IP; ไม่ใช่หลักฐานไปถึงร้าน |
| Tunnel interfaces | พบ utun 6 interfaces | ไม่ระบุว่าเป็น VPN ร้าน; อาจมาจากบริการอื่น |
| Power (AC) | idle sleep 1 นาที; ปัจจุบันมี PreventSystemSleep และ PreventUserIdleSystemSleep assertions | ไม่แสดง process/เจ้าของ assertion; ไม่รับรองว่าจะตื่นทั้งคืน ไม่เปลี่ยน power settings |

## งานที่ทีมรับผิดชอบต่อ

1. Dependency audit ของ candidate pytapo 3.4.26 ให้ครบ รวม aiofiles และ ffmpeg/ffprobe; เลือก runtime แยกและ pin dependencies ก่อนเสนอการติดตั้งที่มีขอบเขต/rollback. ยังไม่ยืนยันว่าบน Python 3.12.14 ใช้ downloader ได้ และไม่แก้ Python เดิม/เครื่องมือ Codex.
2. ทำ adapter แบบ offline/synthetic หลัง PO ระบุ control/write paths; ทดลองข้อจำกัดเวลา/ข้อมูลและการเลือกมุมก่อนแตะกล้อง. ณ รอบนี้ยังไม่มี downloader หรือเครื่องมือรับรหัสจริง.
3. ตรวจวิธีทางเชื่อมจากอุปกรณ์/บริการเดิม: ยังไม่มี route บ้าน→ร้านที่พิสูจน์ได้จากการตรวจ Mac นี้. ถ้ามีอุปกรณ์เดิมที่ร้าน ทีมเสนอวิธีใช้ก่อน; ไม่ซื้อฮาร์ดแวร์ ไม่เปิดพอร์ตกล้องออก WAN/DMZ และไม่เปลี่ยน router/VPN เอง.
4. ประกอบ target/คลิป/route/เพดาน/storage/rollback จริงก่อน live trial หนึ่งคลิปตาม ONE_CLIP_PLAN. ข้อมูลลับรับในเครื่องผ่านช่องทางที่ทีมเตรียม ไม่ให้ Owner ส่งในแชต/Issue.

## สิ่งที่ Owner ช่วยได้จากแอป/หน้างาน

- แอปใช้งานได้และ Camera Account On ยืนยันแล้ว ไม่ขอซ้ำ. ดูเฉพาะสถานะ Tapo → Me → Third-Party Services → Third-Party Compatibility (On/Off/ไม่พบ) ตาม [คู่มือ TP-Link](https://www.tp-link.com/us/support/faq/4416/); ตำแหน่ง Me อาจต่างตามเวอร์ชัน. ยังไม่เปลี่ยนค่า.
- เลือกคลิปที่มีคนเดินผ่านหนึ่งคลิปซึ่งยังดูย้อนหลังได้ แจ้งวัน เวลา และมุมภาพ ไม่ส่ง raw video.
- แจ้งว่าที่ร้านมีคอมพิวเตอร์หรือ NAS เดิมที่เปิดใช้อยู่หรือไม่ เพื่อให้ทีมเลือกทางเชื่อมภายใต้ข้อจำกัดไม่ซื้อฮาร์ดแวร์. ไม่ต้องให้ Owner ออกแบบ VPN หรือตรวจ Mac เองซ้ำ.

ผลนี้เป็น LOCAL_INSPECTION เท่านั้น: camera requests/auth attempts/clips = 0/0/0; camera firmware/model ที่ Owner ยืนยันไม่ถูกย้อนเป็น UNKNOWN เพราะ doctor ไม่อ่านกล้อง. Route/auth/SD export ยัง NOT_TESTED.
