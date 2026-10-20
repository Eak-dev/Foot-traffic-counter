# บ้าน → ร้าน: แผนเชื่อมต่อด้วยอุปกรณ์เดิม (OD-35)

> **OD-37 ปัจจุบัน:** พบ [OnTapo SD relay และ C545D developer research](REMOTE_SD_RESEARCH.md). เลือกตรวจ/ออกแบบ adaptation ของ SD relay ก่อน Tapo Care; คงต้นฉบับ SD และ Mac บ้าน. มี author-reported TC65 download กับ PO static source review แต่ยังไม่มีผล C545D ของเรา จึง CONDITIONAL research ไม่ใช่ live/production PASS. ไม่ต้องเลือกหรือซื้อ Tapo Care ตอนนี้; auth/input/region/Fixed/quota ยังต้องพิสูจน์
> OD-36/older next actions ด้านล่างเป็นประวัติและถูกแทนเฉพาะลำดับ candidate; ไม่เปิดเกตอุปกรณ์

> **OD-36 ประวัติ — ลำดับ candidate ถูกแทนที่ด้วย OD-37:** ปรึกษา Claude และตรวจ primary sources แล้ว: automatic SD จาก Mac บ้านภายใต้ข้อจำกัดเดิมเป็น NO-GO สำหรับ implementation ตอนนี้ (ไม่ใช่พิสูจน์ว่าเป็นไปไม่ได้ถาวร). พัก acquisition scaffolding เพิ่มและไม่รอ Owner router UI เป็นเกตบังคับของคำตัดสิน. [FEASIBILITY_REVIEW](FEASIBILITY_REVIEW.md) แยก manual SD/local import หนึ่งคลิปกับ Tapo Care cloud-source เป็น CONDITIONAL proposals; cloud ต้องยอมรับ source/privacy/งบและพิสูจน์ auth/Fixed/completeness ใหม่ก่อน. ไม่เปลี่ยน SD spec หรือเปิดเกตวิดีโอ/นับ/ซื้อในงานนี้
> รายละเอียด candidate/next action เดิมด้านล่างเป็นประวัติ OD-30–35; OD-36 มีผลเหนือข้อความที่ให้รอ router UI หรือพัฒนา adapter ต่อ

Owner ต้องการให้ Mac อยู่บ้านและเชื่อมไปกล้องร้าน. ไม่ใช้การย้าย Mac ไปที่ร้านเป็นขั้นบังคับ. Baseline `4681569f2b028e6def1f2a62616f5e981540cfa1`, branch งานเดิม; PO เป็นผู้ดำเนินการ. แผนนี้ยังไม่ใช่ tunnel ที่ตั้งแล้ว

## ผลที่ตรวจแล้วและจุดที่ขาด

- OD-34 OS route: camera private target อยู่ใน attached subnet ของ Mac บ้าน และ route ไม่ผ่าน tunnel. นี่คือสองปัญหา: ยังไม่มีทางเข้าร้าน และช่วง IP ทับกัน. เปลี่ยน IP/route ฝั่งบ้านอย่างเดียวไม่สร้างทางเข้าร้าน
- PO อ่านหน้า AIS ของ F6107A และ PDF LAN/DDNS/Port Forwarding แล้ว; ยังไม่มีหลักฐาน VPN Server สำหรับรุ่น/firmware ที่ Owner ใช้. ต้องดูเมนูจริง ไม่สรุป unsupported จากเอกสารที่ไม่มีคำนี้
- Mac เป็น x86_64; ตรวจเฉพาะชื่อแอปใน /Applications ไม่พบ WireGuard, OpenVPN Connect, Tunnelblick, Tailscale. ไม่อ่าน profile/Keychain/credentials และไม่ติดตั้งเดา protocol
- PO ยังเข้า shop router UI ไม่ได้: ไม่มี shop management route/session หรือ tunnel profile. Tapo account ไม่ใช่สิทธิ์จัดการเราเตอร์. ขั้นที่ขาดคือการเข้าถึงเมนูจริงจาก iPhone ที่ร้าน; ไม่ใช่ขาดคำอนุญาตทดลองจาก Owner

## วิธีหลักที่เลือกตรวจ

Mac บ้าน (VPN client) → encrypted tunnel → เราเตอร์ร้าน (VPN gateway) → camera private endpoint

ถ้า F6107A มี **VPN Server** แบบ WireGuard/OpenVPN หรือ authenticated IPsec ที่รองรับ LAN access: PO เลือก client ให้ตรง protocol และตรวจ endpoint ที่เข้าถึงได้จากบ้าน. ต้องตรวจ WAN IPv4/public IPv6/CGNAT จริงแยก; แพ็กเกจ 1000/200 หรือ DDNS อย่างเดียวไม่ยืนยัน inbound reachability

ตั้งเฉพาะ route ไปกล้อง (`/32` ถ้า client รองรับ) ผ่าน tunnel เพื่อแก้ overlap โดยไม่เปลี่ยน subnet บ้าน/ร้านทั้งวง. ใช้ปลายทางกล้องที่ส่งไว้ ไม่พึ่ง LAN discovery. หากชน IP ของ gateway บ้านเองหรือ client ไม่รองรับ host route ต้องออกแบบ address translation/อีกวิธีตาม capability ก่อนแก้. เป็นแบบเสนอ ไม่ได้เพิ่ม route บน Mac แล้ว

หากมีเพียง **VPN Client** หรือ **VPN Passthrough**: ยังไม่ใช่ server ที่ Mac บ้านใช้เข้าร้านได้. Reverse/site-to-site tunnel ต้องพิสูจน์การ forward LAN/return route และ reachable server endpoint ทั้งสองฝั่งก่อน; consumer privacy VPN ไม่ตอบโจทย์นี้. ไม่เช่า VPS หรือเปิดบริการบ้านโดยอัตโนมัติ

หากเราเตอร์ไม่มี gateway ที่ใช้ได้: ภายใต้ร้านมีเพียงกล้อง/เราเตอร์และไม่เพิ่มฮาร์ดแวร์ ต้องมี vendor relay ที่รองรับ automated SD retrieval จริง. `pytapo` ที่ตรวจยังเป็น direct local backend; Tapo app remote playback ไม่ยืนยัน Mac SDK/SD export. ต้องรายงานข้อจำกัดนี้ตามจริง ไม่ขายการติดตั้ง VPN เฉพาะบ้านว่าเป็นคำตอบ

## ขั้นที่ Owner ทำผ่าน iPhone ตอนนี้

1. ต่อ Wi-Fi ร้าน; เปิด Settings → Wi-Fi → แตะ ⓘ ของเครือข่ายที่ต่ออยู่
2. ดูช่อง Router แล้วเปิดที่อยู่นั้นใน Safari. ใช้บัญชีที่ Owner มีอยู่ล็อกอินเอง ไม่ส่ง password/OTP ในแชต
3. แจ้งว่าเปิด/ล็อกอินได้หรือไม่ได้. PO ต้องตรวจชื่อเมนู VPN และชนิด Server/Client ก่อนให้ขั้นตั้งค่า; ไม่ให้กด Apply, เปลี่ยน LAN หรือเปิดพอร์ตกล้องเดา ๆ

PO รับผิดชอบคำสั่ง Mac การเลือกซอฟต์แวร์ และผลทดสอบ. ไม่ให้ Owner หาคำตอบทางเทคนิคจากผู้ผลิตเอง; การเปิด UI เป็นงานเข้าถึงอุปกรณ์ที่ PO ยังไม่มีช่องทางควบคุม

## เกณฑ์รับและย้อนกลับ

เมื่อมี capability และค่าตั้งที่แน่นอนแล้ว เก็บ profile/endpoint/key เฉพาะ local private channel ที่ระบุชัด ไม่ผ่าน Git/Claude/chat. ก่อนใช้ตรวจ profile ไม่ให้รัน scripts, เปลี่ยน DNS/default route หรือเปิดสิทธิ์อื่นนอกงานโดยไม่ตั้งใจ

ตรวจตามลำดับ: tunnel authenticated → OS route กล้องผ่าน tunnel → bounded TCP 443/8800 → camera identity/auth → scoped SD listing/หนึ่งคลิป. แต่ละขั้นแยกผล; ไม่ใช้ tunnel-connected เป็น SD PASS. ขั้น TCP ตาม OD-34 ไม่ส่ง application payload; ขั้น auth/SD จัด implementation และ bounds แยก

Rollback สำหรับ configuration ที่จะเสนอ: ปิดเฉพาะ tunnel/profile/host route ที่สร้างในงานนี้ และยกเลิก peer/กฎใหม่ที่ร้าน; เก็บค่าเดิมก่อนเปลี่ยน. ไม่มี LAN renumbering, camera reboot/reset, firmware flash, public camera ports หรือ default Internet migration ในแบบนี้

## หลักฐาน primary sources ที่ตรวจ 2026-10-08

- [AIS F6107A](https://aiscallcenter.ais.co.th/ikm/acc/index.php?kmid=KM1099952), [Port Forwarding](https://aiscallcenter.ais.co.th/wp-content/uploads/2022/10/Port_Forwording_ZTE_F6107A.pdf), [DDNS](https://aiscallcenter.ais.co.th/wp-content/uploads/2022/10/DDNS_ZTE_F6107A.pdf), [LAN](https://aiscallcenter.ais.co.th/wp-content/uploads/2022/10/LAN_ZTE_F6107A.pdf): ไม่ใช่หลักฐาน VPN Server
- [Tailscale access devices without Tailscale](https://tailscale.com/docs/use-cases/personal-or-at-home-use/access-devices-without-tailscale): ต้องมี subnet router บน LAN ที่ต้องการเข้าถึง; ติดตั้งที่ Mac บ้านอย่างเดียวไม่สร้าง shop gateway
- [OpenVPN routing](https://openvpn.net/community-docs/expanding-the-scope-of-the-vpn-to-include-additional-machines-on-either-the-client-or-server-subnet.html): ต้องมีทั้งเส้นทางและ return route. Host-route design ด้านบนเป็นข้อเสนอของ PO ยังไม่ใช่ configuration ที่ทดสอบ
- [pytapo README](https://github.com/JurajNyiri/pytapo/blob/main/README.md): SD download ใช้ camera HOST และ local encrypted stream; cloud password ไม่ใช่ cloud relay
- [TP-Link FAQ 2742](https://www.tp-link.com/sa/support/faq/2742/): Tapo app สำหรับ iOS/Android ไม่ใช่ desktop app; ไม่สมมติว่าสามารถเปิด app เดิมบน Intel Mac
