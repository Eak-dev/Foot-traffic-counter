# ft_cloud_probe — คู่มือ (OD-40)

`tools/ft_cloud_probe.py` เป็นโปรแกรม Python 3.9+ standard library อย่างเดียว (ไม่ต้อง pip install) ที่ลองเชื่อมต่อ TP-Link/Tapo cloud account จริงแบบจำกัดเฉพาะ login + MFA + รายการกล้องในบัญชี **ไม่ใช่** โปรแกรมโหลดคลิป/SD และไม่เคยเรียก API ของกล้องโดยตรง ที่มาของโปรโตคอล/signature อยู่ใน [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) (พอร์ตจาก OnTapo เป็นการทดลองแบบ unofficial)

## ข้อกำหนดก่อนใช้งาน (สำคัญ)

- `login-check` ต้องรันบน **Mac ที่มีคนอยู่หน้าเครื่องจริง** เพราะต้องตอบกล่องข้อความ native ของ macOS (`/usr/bin/osascript`) ด้วยมือ — **ไม่ใช่วิธีให้ Owner ป้อนข้อมูลจาก iPhone จากระยะไกล** ถ้า Owner ไม่ได้อยู่ที่ Mac คำสั่งนี้ใช้ไม่ได้
- ไม่มี argument/environment variable/ไฟล์สำหรับใส่ account หรือรหัสผ่าน; ไม่มีการเก็บ token/refresh token ไว้ในไฟล์หรือ Keychain เลย — อยู่ใน memory เฉพาะระหว่างรันคำสั่งเดียว
- การเจอกล้องรุ่น C545D ใน cloud inventory เป็นแค่ **CLOUD_INVENTORY_ONLY** (รายชื่อในบัญชี cloud) ไม่ใช่การยืนยัน SD listing, การ auth เข้ากล้องจริง หรือ Fixed-lens PASS

## คำสั่งที่มี

```
python3 tools/ft_cloud_probe.py check
python3 tools/ft_cloud_probe.py tls-check
python3 tools/ft_cloud_probe.py login-check
```

### `check` — ตรวจแบบ offline เท่านั้น

ไม่เปิด socket ไม่เปิด dialog ตรวจ pinned CA และการมี `/usr/bin/osascript`. CA ถูกต้องให้ `AUTH_INPUT_REQUIRED`; CA ผิดให้ `BLOCKED / CA_PIN_MISMATCH`. `live_auth: NOT_TESTED`, `sd_download: NOT_IMPLEMENTED` และ exit 2 เสมอ. การมี osascript ยังไม่พิสูจน์ว่าหน้าต่างใช้งานจริงสำเร็จ

### `tls-check` — ทดสอบ TLS handshake เท่านั้น

เชื่อมต่อ TLS (ไม่ส่ง HTTP request ไม่ auth ไม่มี payload กล้องใดๆ) ไปยัง 3 host ที่กำหนดตายตัวเท่านั้น:
`n-wap.i.tplinkcloud.com`, `aps1-app-server.iot.i.tplinkcloud.com`, `aps1-cipc-api.i.tplinkcloud.com`

ใช้ context ที่ไว้ใจเฉพาะ pinned CA ที่แนบมา (ไม่แตะ OS trust store) และปฏิเสธการใช้งานถ้า cert ที่แนบมาไม่ตรง hash ที่ปักหมุด exit 0 ถ้าทุก host ผ่าน, exit 1 ถ้ามี host ใด TLS/connect ล้มเหลว

### `login-check` — login จริง + MFA (ถ้าต้อง) + รายการกล้อง

ลำดับการทำงาน:
1. เปิดกล่องข้อความ native ถามอีเมล Tapo account (hidden answer)
2. เปิดกล่องข้อความถามรหัสผ่าน (hidden answer)
3. ส่ง login ที่เซ็นลายเซ็นตาม source ที่ pin ไปยัง `n-wap.i.tplinkcloud.com`. หากได้รับ region redirect ให้หยุดด้วย `UNSUPPORTED_REGION` เพื่อ audit account endpoint ที่ตอบกลับก่อน ไม่ส่งรหัสผ่านซ้ำไปที่ discovery/media host และไม่เดา region
4. ถ้าบัญชีต้อง MFA และรองรับส่งรหัสทางอีเมล จะส่งรหัสไปอีเมลเจ้าของบัญชีครั้งเดียว แล้วเปิดกล่องข้อความให้กรอกรหัส (hidden answer) ยืนยันครั้งเดียว ไม่มีการลองซ้ำถ้าพลาด
5. ดึงรายชื่ออุปกรณ์กล้องในบัญชี cloud (`GET /v2/things` ที่ `aps1-app-server.iot.i.tplinkcloud.com` เท่านั้น) แล้วรายงานแค่ **จำนวนกล้องทั้งหมด** และ **จำนวนที่ model ตรง C545D**

ผลลัพธ์ที่เป็นไปได้ของ `inventory_status`:
- `TARGET_NOT_FOUND` — ไม่มีกล้อง C545D ในบัญชี
- `CLOUD_INVENTORY_ONLY` — เจอ C545D หนึ่งตัว (แค่ยืนยันว่าอยู่ในบัญชี cloud เท่านั้น)
- `TARGET_AMBIGUOUS` — เจอ C545D มากกว่าหนึ่งตัว ต้องแยกให้ชัดก่อนทำขั้นต่อไป

เฉพาะ `CLOUD_INVENTORY_ONLY` ให้ exit 0; อีกสองกรณีเป็น BLOCKED / exit 2. ไม่ตีความ inventory สำเร็จเป็นการเชื่อมถึงกล้องจริง

การยกเลิก/ปิดกล่องข้อความ หรือกรอกไม่ทันเวลา จะหยุดก่อนส่ง network request ถัดไปทุกครั้ง (ไม่ใช่แค่หยุดรายงาน)

## ขอบเขตและข้อจำกัด (โดยตั้งใจ)

- ไม่มี argument ให้สั่ง URL/method/host เองได้เลย — host/endpoint ตายตัวตามด้านบน
- ไม่มีคำสั่งเกี่ยวกับ SD, media, relay allocation, device setter, หรือ refresh/retry token ใดๆ
- จำนวน HTTPS request ต่อการรันหนึ่งครั้งไม่เกิน 6 ครั้ง, แต่ละ response อ่านไม่เกิน 1 MiB, socket timeout ไม่เกิน 10 วินาทีต่อครั้ง, งบเวลารวมไม่เกิน 120 วินาที (แบบ cooperative เช็คระหว่าง step ไม่ใช่ interrupt กลาง syscall ที่ค้าง)
- ข้อผิดพลาดทุกจุด (TLS/HTTP/JSON/subprocess) ถูกแปลงเป็นโค้ดคงที่ (เช่น `TLS_ERROR`, `AUTH_FAILED`, `MALFORMED_RESPONSE`) เท่านั้น ไม่เคยพิมพ์ raw exception/HTTP body ที่อาจมีข้อมูลบัญชี
- argument ที่ไม่รู้จักจะไม่ถูก echo กลับในข้อความ error

## การทดสอบ

ทุกการทดสอบใน `tests/test_ft_cloud_probe.py` เป็น synthetic ทั้งหมด (fake HTTPS connection, fake `subprocess.run` สำหรับ dialog, fake clock/uuid) — ไม่มีการต่อ host จริงหรือเปิด dialog จริงในชุดทดสอบ รันด้วย:

```
python3 -m unittest discover -s tests -t . -v
```

## ยังไม่ทำ / ยังไม่พิสูจน์

- PO รัน `tls-check` ด้วยโปรแกรมนี้จาก Mac จริงวันที่ 2026-10-09 ผ่าน 3/3 endpoints, exit 0. System CA เดิมปฏิเสธทั้งสาม; root ที่ pin ไว้ทำให้ตรวจ chain/hostname ผ่านโดยไม่แก้ OS trust store. ไม่มี HTTP/auth/device payload. `login-check` และหน้าต่างกรอกข้อมูลจริงยัง NOT_RUN; รอ Owner กรอกส่วนตัวบน Mac
- การเจอ C545D ใน cloud inventory ไม่ได้แปลว่าดึง SD หรือสั่งกล้องได้จริง — ยังต้องมีงานแยกสำหรับ SD listing/media และ Fixed-lens mapping
- ความครอบคลุมของภูมิภาค cloud account ของผู้ให้บริการนอกเหนือ 3 host ที่ปักหมุดไว้ยังเป็น UNKNOWN โดยตั้งใจ (ไม่เดา)

รูปแบบ account response ของเราตรวจเข้มกว่าตัวอย่าง upstream: ต้องมี success code ชัดเจนและตรวจทั้ง outer/inner error. หากรูปแบบจริงต่างจาก fixture ให้หยุดตรวจเพิ่ม ไม่ถือว่าเป็นหลักฐานว่ารหัส Owner ผิด. Python ไม่รับรองการล้างสตริงจาก memory อย่างสมบูรณ์; โปรแกรมไม่เขียนหรือรายงานค่าเหล่านี้

PO validation 2026-10-09: 412/412 unittest PASS, exit 0 (13.724s), รวม cloud-probe synthetic 82 ข้อ. Final corrections NOT_RUN_BY_DEVELOPER; รายละเอียด launcher failure/timeout และการตรวจรับอยู่ STATUS. Native dialog/account login ยังไม่ได้รันจริง
