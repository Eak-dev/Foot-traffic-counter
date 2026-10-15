# เซสชัน Tapo ใช้ซ้ำบน Mac

OD-61 opt-in local retention: retain-7 / retain-30 commands are implemented and synthetically tested. They require a currently valid session, keep the original issued_at/target/device/terminal and update only the local encrypted Keychain record (schema2) with a bounded7/30day duration. No vendor request, password storage, OTP disabling or automatic renewal of the local deadline. Expired sessions cannot be revived. Defaults and the active session remain48h until Owner explicitly selects a longer option; the preference question is pending. The next bootstrap still defaults48h, so PO should reapply the recorded Owner choice after a necessary future private bootstrap without asking the same permission again. Vendor refresh/lifetime remains independently controlled by Tapo.

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

- `start`: หน้าต่างส่วนตัวหนึ่งรอบ; ช่องว่าง/ข้อมูลไม่ผ่าน local validation ถามซ้ำเฉพาะช่องเดิมได้สูงสุด3ครั้งใน deadlineเดิม (ไม่ใช่ retryรหัสที่vendorปฏิเสธ) และแสดงชื่อขั้นตอนเมื่อผิดพลาดโดยไม่แสดงค่าที่กรอก. ขอ refresh token และเลือกกล้องตาม digest config เดิมก่อนเก็บ. หากมีเซสชันอยู่จะไม่เปิดล็อกอินซ้ำ (`SESSION_BUSY`); ใช้ `status/use` ก่อน. `forget` แล้ว `start` ใช้เมื่อจำเป็นต้องยืนยันใหม่จริง.
- `status`: สถานะ เวลาเหลือ และ deadline UTC เท่านั้น ไม่มีการเรียก Tapo.
- `use`: อ่าน Keychain, ตรวจเวลา/schema/host/target และเรียก inventory เพื่อยืนยันกล้องเดิม. ไม่เปิด dialog. HTTP401 อนุญาต refresh1ครั้งและ GET inventoryซ้ำ1ครั้ง; 403/429/5xx ไม่ใช้กติกานี้.
- `sd-check`: ใช้เซสชันเดิมกับ probe ที่ตรวจแล้ว สูงสุด4device requests/20คลิปแรกของ20261012. ตรวจ deadline ใน device budget ด้วย. ไม่ดาวน์โหลดวิดีโอ และไม่ถือว่า channel0 คือ Fixed.
- `refresh-check`: PO ทดสอบ refresh1ครั้งอย่างชัดเจนโดยไม่สร้าง401ปลอม แล้วตรวจ inventory. ไม่เลื่อน deadline. ผลจริงต้องแยกจาก synthetic tests.
- `forget`: ลบเฉพาะ project session item; ไม่ได้ revokeทุกsessionที่server.

Lease48h เริ่มเมื่อ auth สำเร็จครั้งแรก: restart/sleep/refresh ไม่เพิ่มเวลา. ก่อนใช้งานตรวจ wall clock กับเวลาเดิมที่เก็บ; ภายใน process ใช้ monotonic เพิ่มอีกชั้น. ครบกำหนดหยุดและลบเมื่อ Keychain เข้าถึงได้. ถ้าลบไม่ได้รายงาน `EXPIRED, cleanup_pending`. ไม่มี scheduler หรือการรับประกันลบทันเวลาขณะที่เครื่องปิด. ผู้มีสิทธิ์ในบัญชี OS ที่แก้นาฬิกาและข้อมูลย้อนหลังได้อยู่นอกการรับประกันนี้.

เซสชันเก็บใน login Keychain แบบ local file backend: service `org.foot-traffic-counter.tapo-session`, account `session-v1`; ทดสอบใช้ `selftest-v1` เท่านั้น. Scope query/add/update/delete เป็นรายการนี้ใน login.keychain-db โดยตรง. Helper สร้าง restricted ACL ให้ตัวเองเพียงแอปเดียว ไม่ใช้ all-app access หรือ sync flag. เก็บ access/refresh token, terminal UUID, digestเป้าหมาย/อุปกรณ์, hostที่ allowlist, timestamps และ revision. เก็บผ่าน private subprocess pipes; ห้ามเรียก helper `load` แล้วพิมพ์stdoutใน terminal/tool เพราะผลเป็นข้อมูลลับ.

Helper อยู่ใน `~/.local/share/foot-traffic-counter/bin/ft-keychain` พร้อม application/bin mode0700 และลายเซ็น ad-hoc identifier `org.foot-traffic-counter.keychain-helper`. Lock mode0600 อยู่ใน application directory. ไม่มี plaintext credential/cache/tempไฟล์. `SecKeychainSetUserInteractionAllowed(false)` มีผลเฉพาะ process helper; ไม่เปลี่ยนค่าระบบ. `SESSION_LOCKED/STORE_DENIED` ต้องแก้ที่สถานะ login Keychain ไม่ใช้ fallback plaintext หรือปลดล็อกอัตโนมัติ.

ตัวช่วยใช้ Objective-C/Foundation/Security และ compilerที่มีอยู่แล้ว. ทดลอง Swift เดิมไม่ผ่านเพราะ SDK/compiler mismatch และ SwiftBridging ซ้ำ; เปลี่ยนเฉพาะ implementationภาษา native ไม่ได้ติดตั้งหรือเปลี่ยน toolchain. PO compile ด้วย `xcrun clang -fobjc-arc -Wno-deprecated-declarations -framework Foundation -framework Security tools/native/ft_keychain.m -o <project-helper-path>` แล้ว chmod0700, codesign ad-hocและverifyก่อนใช้งาน. ห้ามแทนที่ binary ขณะมี session โดยไม่ตรวจผลต่อ ACL; signature identity ของ ad-hoc buildอาจเปลี่ยนเมื่อโค้ดเปลี่ยน.

Update token เป็น atomic Keychain item updateภายใต้ process lock พร้อม revision check/read-back. ถ้าหมุน token แล้วเขียนกลับไม่สำเร็จจะไม่รายงาน SUCCESS; อาจต้องยืนยันใหม่ถ้า vendorเพิกถอนrefreshเดิมแล้ว. Networkชั่วคราวเก็บเซสชันเดิม; HTTP401 ที่ยืนยันได้หลัง refresh/ไม่มีrefreshจะคืน REAUTH_REQUIREDและล้างรายการ. Unknown vendor errorcodeยังไม่เดาว่าเป็นการเพิกถอนและไม่ลบข้อมูลโดยอัตโนมัติ.

Refresh ใช้ POST `/` ที่ account hostเดิม `n-wap.i.tplinkcloud.com` เท่านั้น พร้อม exact payload guard. CA pinเดิม, auth budget6requests/120s, socket10s, response1MiB; no redirects/host fallback. DNS/syscallsยังเป็น cooperative time budget ไม่ใช่ hard wall-clock interrupt. โค้ดอ้างอิง pinned OnTapo ตาม [แบบ](SESSION_48H_DESIGN.md); vendor token lifetimeอาจสั้นกว่า48hหรือถูกเพิกถอน.

สถานะตรวจรับแยกกัน: LOCAL_48H_EXPIRY_TESTED (synthetic), KEYCHAIN_CROSS_PROCESS_VERIFIED (รายการจำลอง), CACHE_REUSE_VERIFIED (บัญชีจริงสองprocess), REFRESH_VERIFIED (vendorจริง), VENDOR_48H_OBSERVED (สังเกตครบเวลาจริง). สองรายการแรกไม่แทนสามรายการหลัง. ผลล่าสุดดู [STATUS](STATUS.md).
