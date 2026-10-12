# ft_cloud_probe — คู่มือ (OD-40)

`tools/ft_cloud_probe.py` เป็นโปรแกรม Python 3.9+ standard library อย่างเดียว (ไม่ต้อง pip install) ที่ลองเชื่อมต่อ TP-Link/Tapo cloud account จริงแบบจำกัดเฉพาะ login + MFA + รายการกล้องในบัญชี **ไม่ใช่** โปรแกรมโหลดคลิป/SD และไม่เคยเรียก API ของกล้องโดยตรง ที่มาของโปรโตคอล/signature อยู่ใน [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) (พอร์ตจาก OnTapo เป็นการทดลองแบบ unofficial)

## ข้อกำหนดก่อนใช้งาน (สำคัญ)

- `login-check` เปิดกล่องข้อความ native ของ macOS (`/usr/bin/osascript`). Owner ตอบได้หน้า Mac หรือผ่าน Chrome Remote Desktop จาก iPhone ที่ตั้งค่าแล้ว (Owner ยืนยันรีโมตได้ 2026-10-10); PO รันคำสั่งให้. ไม่ส่งบัญชี/รหัสผ่าน/OTP ผ่านแชต
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
1. เปิดกล่องข้อความ native ถามอีเมล Tapo account (hidden answer; ไม่เกิน 5 นาที)
2. เปิดกล่องข้อความถามรหัสผ่าน (hidden answer; ไม่เกิน 5 นาที)
3. ส่ง login ที่เซ็นลายเซ็นตาม source ที่ pin ไปยัง `n-wap.i.tplinkcloud.com`. หากได้รับ region redirect ให้หยุดด้วย `UNSUPPORTED_REGION` เพื่อ audit account endpoint ที่ตอบกลับก่อน ไม่ส่งรหัสผ่านซ้ำไปที่ discovery/media host และไม่เดา region
4. ถ้าบัญชีต้อง MFA และรองรับส่งรหัสทางอีเมล จะขอส่งรหัสไปอีเมลเจ้าของบัญชีครั้งเดียว แล้วเปิดกล่องข้อความให้กรอกรหัสเมื่อได้รับ send acknowledgment (ยังไม่ใช่หลักฐานว่าอีเมลถึงแล้ว) (hidden answer) ยืนยันครั้งเดียว ไม่มีการลองซ้ำถ้าพลาด
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

- PO รัน `tls-check` ด้วยโปรแกรมนี้จาก Mac จริงวันที่ 2026-10-09 ผ่าน 3/3 endpoints, exit 0. System CA เดิมปฏิเสธทั้งสาม; root ที่ pin ไว้ทำให้ตรวจ chain/hostname ผ่านโดยไม่แก้ OS trust store. ไม่มี HTTP/auth/device payload. ผลนี้เป็นหลักฐาน TLS เท่านั้น; ผล login จริงล่าสุดดู STATUS
- การเจอ C545D ใน cloud inventory ไม่ได้แปลว่าดึง SD หรือสั่งกล้องได้จริง — ยังต้องมีงานแยกสำหรับ SD listing/media และ Fixed-lens mapping
- ความครอบคลุมของภูมิภาค cloud account ของผู้ให้บริการนอกเหนือ 3 host ที่ปักหมุดไว้ยังเป็น UNKNOWN โดยตั้งใจ (ไม่เดา)

Login และ OTP submission ต้องมี success code ชัดเจน พร้อม token และตรวจทั้ง outer/inner error. Status code รับ JSON integer หรือ canonical ASCII decimal string; ไม่รับ boolean, whitespace, leading zero, float หรือค่าขัดกัน. เฉพาะ MFA send ยอมรับ HTTP 200 ที่ไม่มี body หรือไม่มี code ตาม pinned OnTapo; ถ้ามี code ต้องไม่เป็น error และ JSON ที่มีต้องถูกต้อง. Send acknowledgment ไม่ใช่ auth success หรือหลักฐาน email delivery. หากรูปแบบจริงต่างจาก fixture ให้หยุดตรวจเพิ่ม ไม่ถือว่าเป็นหลักฐานว่ารหัส Owner ผิด. Python ไม่รับรองการล้างสตริงจาก memory อย่างสมบูรณ์; โปรแกรมไม่เขียนหรือรายงานค่าเหล่านี้

Follow-up 2026-10-09: รัน native login จริงแล้ว ครั้งแรก BLOCKED/MALFORMED_RESPONSE ไม่ทราบ stage. เพิ่ม `stage` (LOGIN/MFA_SEND/MFA_SUBMIT/DISCOVERY) และ `detail` จากรายการข้อความคงที่เพื่อแยก JSON/schema failures โดยไม่พิมพ์ response values หรือ secrets และไม่ผ่อนเงื่อนไขรับคำตอบ. PO 427/427 tests PASS; cloud subset 97/97 PASS. ครั้งที่สอง input TIMEOUT; ไม่มีผล auth/inventory ที่ยืนยันได้. รอบใหม่ต้องกรอก TP-Link ID ผ่านหน้าต่างส่วนตัวอีกครั้ง เพราะไม่ได้เก็บ credentials. หลักฐาน NOT_RUN ด้านบนเป็นประวัติก่อน trial; ผลปัจจุบันดู STATUS

PO validation 2026-10-09: 412/412 unittest PASS, exit 0 (13.724s), รวม cloud-probe synthetic 82 ข้อ. Final corrections NOT_RUN_BY_DEVELOPER; รายละเอียด launcher failure/timeout และการตรวจรับอยู่ STATUS. เป็นผลทดสอบก่อน live trial; ดูผลล่าสุดใน STATUS

Follow-up 2026-10-10: remote input ใช้ได้ตาม Owner. Trial แรกติด LOGIN/INVALID_CODE_TYPE; หลังรองรับ decimal string ถึง MFA_SEND/MFA_FAILED แต่ยังไม่ทราบรายละเอียดและ Owner ยังไม่เห็นอีเมล. แก้ send acknowledgment ตาม [OnTapo pinned source](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/src/ontapo/session.py) และเพิ่ม fixed diagnostics MFA_SEND_HTTP_ERROR/MFA_SEND_REJECTED. หลักฐาน string status จาก [tapo-cli account parser](https://github.com/dimme/tapo-cli/blob/main/tapo-cli.py). PO tests 434/434 PASS (63.662s), cloud 104/104 PASS (0.739s); NOT_RUN_BY_DEVELOPER. ไม่เก็บ raw replies หรือ secrets และไม่ retry อัตโนมัติ.

Live trial หลัง send-ack correction จบ TIMEOUT ระหว่าง native input (ไม่มี stage ใน report); ยังไม่ยืนยัน email delivery/auth/inventory. ไม่เปิดรอบซ้ำโดยอัตโนมัติ.

2026-10-12: Owner แจ้งกำลังกรอกบัญชี/รหัสผ่านเมื่อ dialog เดิม TIMEOUT. PO เพิ่มเวลาเฉพาะช่องบัญชี/รหัสผ่านจาก 120 เป็น 300 วินาทีเพื่อใช้ผ่าน iPhone; OTP prompt ยัง 120 วินาทีและอยู่ใน network budget เดิม (เริ่มหลังรับรหัสผ่าน). เพิ่ม fixed stages EMAIL_INPUT/PASSWORD_INPUT/OTP_INPUT ให้แยก input failure ได้โดยไม่มีค่าบัญชี. ไม่เพิ่ม network retry หรือเก็บ secrets.

2026-10-12 email correction: หลังเพิ่มเวลาป้อนบัญชี trial ถึง MFA_SEND แต่จบ MFA_SEND_REJECTED (explicit application error); ไม่ใช่ email-delivery PASS. PO พบ source เพิ่มที่ pin ได้: [tapo-tools request struct/method](https://github.com/igoriok/tapo-tools/blob/8d62e018d1010f97d197d23d7c2c92399dcd7d5e/tapo/tp-link-cloud.go) และ [ioBroker Tapo](https://github.com/TA2k/ioBroker.tapo/blob/5e67c5a43557b07500a6b742bde8e8c55497617b/src/main.ts). เปลี่ยนจาก getPushVC4TerminalMFA เป็น getEmailVC4TerminalMFA เพียงเส้นทางเดียว ใช้ body appType/cloudUserName/cloudPassword/terminalUUID บน pinned account host เดิม. Password อยู่ใน memory จนจบคำขอส่งหนึ่งครั้ง แล้วปล่อย reference ก่อน OTP; ไม่เก็บเพื่อใช้รอบหน้า. ไม่ใช้ endpoint guessing loop, upstream raw debug, verify=False หรือ terminalBindEnabled. Exact push endpoint เดิมถูกเอาออกจาก allowlist. เป็นการทดลอง schema ที่มีหลักฐาน source ไม่ใช่รับรองว่าบัญชีนี้จะผ่าน.

Claude advisory COMPLETED_LOCAL / 59.4s, NOT_RUN_BY_DEVELOPER: แนะนำเพิ่ม error classification ก่อนเปลี่ยน path เนื่องจาก packet ตอนส่งยังมีเพียง OnTapo และ candidate ที่ไม่ยืนยันของ tapo-cli. PO พบสอง implementations ข้างต้นระหว่าง advisory แล้วเลือกแก้ email path/body จากหลักฐานใหม่; ไม่อ้างว่า Claude ตรวจหรืออนุมัติ final implementation. PO ยังไม่ทราบ numeric error ของรอบเก่า และไม่เดาว่าเกิดจากรหัสผ่านผิด/rate limit. รองรับ email type 2 ถูกตรวจใน flow ก่อน send แล้ว.

APS1 follow-up 2026-10-12: MFA submit ผ่าน explicit status แต่ถูกบล็อก metadata origin; fixed diagnostic ระบุ REGION_APS1_ACCOUNT. PO TLS-only ตรวจ exact n-aps1-wap.i.tplinkcloud.com ด้วย pinned CA ผ่าน. รับ origin นี้เฉพาะ metadata ของภูมิภาคเดียวกับ discovery ที่มีอยู่; ไม่เพิ่ม HTTP target หรือส่ง password ไป host นี้. EUW1/USE1/unknown ยังหยุด. Actual retry อ่าน cloud inventory ได้ 13 cameras, exact C545D 0 จึง TARGET_NOT_FOUND / exit2. Auth/inventory verified, camera/SD/Fixed ยังไม่ทดสอบ. ไม่มี secret/raw response เก็บไว้.

Model diagnostics ที่เตรียมหลัง trial: c545d_model_variants นับเฉพาะ C545D ที่มี Tapo prefix หรือ suffix region/version แบบจำกัด โดยไม่พิมพ์ชื่อรุ่นดิบ/ชื่อกล้อง/IDs และไม่เปลี่ยน c545d_candidates หรือเลือกเป้าหมายให้เอง. ยังไม่รันกับบัญชีจริง; model mismatch เป็นสมมติฐาน ไม่ใช่สาเหตุที่พิสูจน์แล้ว. ต้องมี private input รอบใหม่สำหรับ live diagnosis.

## OD-42 — กล้องที่ Owner เลือกด้วยชื่อ

PO เก็บ digest ของชื่อที่ Owner ระบุและ lens FIXED ใน ignored local configuration (mode0600); ไม่เก็บชื่อจริงหรือภาพใน repo. เรียก Python API `login_check_command(target_name_sha256=...)` ด้วย digest นี้. CLI เดิมไม่มี argument สำหรับชื่อ/บัญชีและไม่อ่าน config อัตโนมัติ. Digest ต้องเป็น lowercase SHA256 64 ตัวก่อนเปิด dialog/network. ใช้ nickname แบบ base64 UTF-8 หรือ plain, normalize strip/casefold; fallback deviceName เฉพาะ nickname ขาด/ว่าง. nickname ผิดชนิด/ชื่อไม่ตรงไม่ใช้ fallback มาทดแทน.

หนึ่งชื่อที่ตรง => CLOUD_INVENTORY_ONLY; ศูนย์ => TARGET_NOT_FOUND; ชื่อซ้ำ => TARGET_AMBIGUOUS. ไม่ fallback ไปเลือกจากรุ่นเมื่อ Owner ระบุชื่อ. Output เพิ่มเพียง target_name_matches, selection_basis=OWNER_NAME_EXACT และ selected_model_kind เป็น EXACT/VARIANT/OTHER/UNKNOWN; ไม่ส่ง name/model/id/digest ดิบ. แม้ model เป็น OTHER ก็ถือได้แค่จับคู่รายการ cloud ตามชื่อ ไม่ยืนยันอุปกรณ์จริง/Fixed. ภาพล่าสุด Owner ยืนยัน Fixed อยู่ล่างและ PT อยู่บน; ตำแหน่งภาพไม่ใช้เดา channel ID.

Claude ทำ code/tests แต่ invocation TIMEOUT 240.8s ก่อน final report. PO ตรวจว่าไม่มี child/test process ของงานนี้เหลือ (Claude sessions ที่เห็นเริ่มก่อนงานนี้หลายวัน) จึงคืน empty lock; แก้ malformed-nickname fallback และ validate direct discovery input เพิ่มเอง. Final validation เป็น PO; NOT_RUN_BY_DEVELOPER ไม่อ้างผล Claude ที่ไม่ได้รับ.

Final PO validation OD-42: cloud 121/121 PASS (0.367s), full 451/451 PASS (32.487s), diff check PASS. ไม่ได้รันโดย Dev หลังแก้ review. Owner-name live outcome ดู STATUS.

Actual OD-42 result: SUCCESS / exit0, 13 cameras, exact C545D0, variants3, owner-name matches1, selected model kindVARIANT. ชื่อรุ่นต่างจาก exact string เป็นข้อเท็จจริงที่ classifier ยืนยัน แต่ไม่รายงานรูปแบบดิบ. Cloud target ที่ Owner เลือกยืนยันแล้ว; ภาพ Fixed และ SD ยังไม่ได้เรียกผ่าน API. ไม่มี worker/session token เก็บค้างหลังจบ.
