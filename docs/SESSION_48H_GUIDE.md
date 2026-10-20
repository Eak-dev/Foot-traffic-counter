# เซสชัน Tapo และการต่อ token อัตโนมัติ

OD-65 /2026-10-18: Owner requires automatic vendor refresh without an artificial local48h/7day/30day expiry. This supersedes the earlier48h default and pending retention choice. New private bootstrap writes strict schema3 in the existing local Keychain item, with no local deadline. A validated schema1/2 item still present is migrated before enforcing any former local cap; its original authentication time and credentials are preserved. Deleted/missing tokens cannot be restored. retain-7 / retain-30 are removed from API and CLI so they cannot reinstate a local cutoff. The filename is retained for existing links.

When authorized use encounters explicit inventory HTTP401, refresh once and replay target discovery once within the existing budgets. Save rotated tokens in Keychain without resetting the original authentication time. Elapsed2/7/30days does not delete credentials or require another login. HTTP403/429/5xx, timeout and connection errors are not proof of token expiry and do not delete tokens. Confirmed refresh401, access401 after successful refresh, and missing refresh credentials when needed stop with REAUTH_REQUIRED and distinct fixed causes. No automatic login dialog, background keepalive or new scheduler.

Safe results include local_expiry_policy=VENDOR_MANAGED, expires_at_utc/remaining_seconds=null, original authentication age, observation start time, observed successful refresh count, last refresh time and last vendor verification time. Local status does not advance vendor verification. Legacy migration starts a new observation counter rather than inventing historical refresh counts. Terminal auth results include these numerical observations before credentials are deleted, allowing the existing redacted caller/job log to preserve evidence without new credential/audit files. REFRESH_REJECTED differs from ACCESS_REJECTED_AFTER_REFRESH and NO_REFRESH_TOKEN. Refresh rejection does not establish whether the vendor's reason is expiry or revocation.

Actual usable lifetime is UNKNOWN: simulated2/7/30day tests are not vendor lifetime evidence. Last successful vendor verification and first rejection bound the observation, not the exact expiry instant. Rotation means the measured age is continuous session age since login, not lifetime of one token string. The old48h code already deleted the prior session before OD-65, so one new private bootstrap is needed to begin actual observation.

OD-45 /2026-10-13: บัญชีจริงล็อกอินสำเร็จและบันทึกเซสชันใน Keychain แล้ว. ใช้ซ้ำจากสอง process ผ่านโดยไม่มี dialog, ทดสอบ vendor refresh ผ่านโดยไม่เลื่อน deadline และอ่านรายการ SD 20 รายการแรกผ่านเซสชันเดิมได้. CACHE_REUSE_VERIFIED / REFRESH_VERIFIED; ยังไม่ได้สังเกตครบ48ชั่วโมงจริง และยังไม่ได้ดาวน์โหลดวิดีโอหรือยืนยัน Fixed track. ผลล่าสุดดู STATUS.

PO เป็นผู้รันคำสั่งให้ Owner; Owner ใช้ iPhone remote กรอกเฉพาะ email/password/OTP ในหน้าต่างส่วนตัว **Foot Traffic / Tapo login**. ใช้บัญชีเข้าแอป Tapo สำหรับ cloud login. ไม่ส่งรหัสในแชต. โปรแกรมไม่เก็บ password/email/OTP. ขณะเซสชันปัจจุบันยังใช้ได้ ให้ใช้ `use` หรือ `sd-check` โดยไม่เปิด bootstrap ซ้ำ; กรอกใหม่เฉพาะเมื่อจำเป็นต้องยืนยันตัวตนใหม่จริง.

คำสั่งจาก root ของโปรเจกต์:

```sh
python3 -m tools.ft_session start
python3 -m tools.ft_session status
python3 -m tools.ft_session use
python3 -m tools.ft_session sd-check
python3 -m tools.ft_session refresh-check
python3 -m tools.ft_session forget
```

- `start`: หน้าต่างส่วนตัวหนึ่งรอบ; ช่องว่าง/ข้อมูลไม่ผ่าน local validation ถามซ้ำเฉพาะช่องเดิมได้สูงสุด3ครั้งใน deadlineเดิม (ไม่ใช่ retryรหัสที่vendorปฏิเสธ) และแสดงชื่อขั้นตอนเมื่อผิดพลาดโดยไม่แสดงค่าที่กรอก. ขอ refresh token และเลือกกล้องตาม digest config เดิมก่อนเก็บ schema3 ไม่มี local expiry. หากมีเซสชันอยู่จะไม่เปิดล็อกอินซ้ำ (`SESSION_BUSY`); ใช้ `status/use` ก่อน. `forget` แล้ว `start` ใช้เมื่อจำเป็นต้องยืนยันใหม่จริง.
- `status`: Local schema/clock check and observations only, no Tapo call. ACTIVE does not independently verify current vendor acceptance.
- `use`: อ่าน Keychain, ตรวจเวลา/schema/host/target และเรียก inventory เพื่อยืนยันกล้องเดิม. ไม่เปิด dialog. HTTP401 อนุญาต refresh1ครั้งและ GET inventoryซ้ำ1ครั้ง; 403/429/5xx ไม่ใช้กติกานี้.
- `sd-check`: ใช้เซสชันเดิมกับ probe ที่ตรวจแล้ว สูงสุด4device requests/20คลิปแรกของ20261012. Passes a clock guard and preserves per-operation request/time budgets. ไม่ดาวน์โหลดวิดีโอ และไม่ถือว่า channel0 คือ Fixed.
- `refresh-check`: PO ทดสอบ refresh1ครั้งอย่างชัดเจนโดยไม่สร้าง401ปลอม แล้วตรวจ inventory. Preserves original authentication time. ผลจริงต้องแยกจาก synthetic tests.
- `forget`: ลบเฉพาะ project session item; ไม่ได้ revokeทุกsessionที่server.

Clock guards still reject wall-clock/monotonic rollback and nonfinite values. Schema/host/target/device/revision/lock and pinned transport checks remain. Per-operation request/time budgets and the finite72h/2cycle counting job are unchanged; only the artificial credential-age ceiling is removed. Vendor refresh may still be rejected. No stored password, MFA bypass or automatic login is introduced.

เซสชันเก็บใน login Keychain แบบ local file backend: service `org.foot-traffic-counter.tapo-session`, account `session-v1`; ทดสอบใช้ `selftest-v1` เท่านั้น. Scope query/add/update/delete เป็นรายการนี้ใน login.keychain-db โดยตรง. Helper สร้าง restricted ACL ให้ตัวเองเพียงแอปเดียว ไม่ใช้ all-app access หรือ sync flag. เก็บ access/refresh token, terminal UUID, digestเป้าหมาย/อุปกรณ์, hostที่ allowlist, timestamps และ revision. เก็บผ่าน private subprocess pipes; ห้ามเรียก helper `load` แล้วพิมพ์stdoutใน terminal/tool เพราะผลเป็นข้อมูลลับ.

Helper อยู่ใน `~/.local/share/foot-traffic-counter/bin/ft-keychain` พร้อม application/bin mode0700 และลายเซ็น ad-hoc identifier `org.foot-traffic-counter.keychain-helper`. Lock mode0600 อยู่ใน application directory. ไม่มี plaintext credential/cache/tempไฟล์. `SecKeychainSetUserInteractionAllowed(false)` มีผลเฉพาะ process helper; ไม่เปลี่ยนค่าระบบ. `SESSION_LOCKED/STORE_DENIED` ต้องแก้ที่สถานะ login Keychain ไม่ใช้ fallback plaintext หรือปลดล็อกอัตโนมัติ.

ตัวช่วยใช้ Objective-C/Foundation/Security และ compilerที่มีอยู่แล้ว. ทดลอง Swift เดิมไม่ผ่านเพราะ SDK/compiler mismatch และ SwiftBridging ซ้ำ; เปลี่ยนเฉพาะ implementationภาษา native ไม่ได้ติดตั้งหรือเปลี่ยน toolchain. PO compile ด้วย `xcrun clang -fobjc-arc -Wno-deprecated-declarations -framework Foundation -framework Security tools/native/ft_keychain.m -o <project-helper-path>` แล้ว chmod0700, codesign ad-hocและverifyก่อนใช้งาน. ห้ามแทนที่ binary ขณะมี session โดยไม่ตรวจผลต่อ ACL; signature identity ของ ad-hoc buildอาจเปลี่ยนเมื่อโค้ดเปลี่ยน.

Update token เป็น atomic Keychain item updateภายใต้ process lock พร้อม revision check/read-back. ถ้าหมุน token แล้วเขียนกลับไม่สำเร็จจะไม่รายงาน SUCCESS; อาจต้องยืนยันใหม่ถ้า vendorเพิกถอนrefreshเดิมแล้ว. Networkชั่วคราวเก็บเซสชันเดิม; HTTP401 ที่ยืนยันได้หลัง refresh/ไม่มีrefreshจะคืน REAUTH_REQUIREDและล้างรายการ. Unknown vendor errorcodeยังไม่เดาว่าเป็นการเพิกถอนและไม่ลบข้อมูลโดยอัตโนมัติ.

Refresh ใช้ POST `/` ที่ account hostเดิม `n-wap.i.tplinkcloud.com` เท่านั้น พร้อม exact payload guard. CA pinเดิม, auth budget6requests/120s, socket10s, response1MiB; no redirects/host fallback. DNS/syscallsยังเป็น cooperative time budget ไม่ใช่ hard wall-clock interrupt. โค้ดอ้างอิง pinned OnTapo ตาม [แบบ](SESSION_48H_DESIGN.md); vendor token lifetimeอาจสั้นกว่า48hหรือถูกเพิกถอน.

สถานะตรวจรับแยกกัน: LOCAL_48H_EXPIRY_TESTED (synthetic), KEYCHAIN_CROSS_PROCESS_VERIFIED (รายการจำลอง), CACHE_REUSE_VERIFIED (บัญชีจริงสองprocess), REFRESH_VERIFIED (vendorจริง), VENDOR_48H_OBSERVED (สังเกตครบเวลาจริง). สองรายการแรกไม่แทนสามรายการหลัง. ผลล่าสุดดู [STATUS](STATUS.md).
