# เซสชัน Tapo ใช้ซ้ำสูงสุด 48 ชั่วโมง — OD-44

สถานะ: **DESIGN_READY / NOT_IMPLEMENTED / NOT_ACTIVE** (2026-10-12). Owner ขอออกแบบเพื่อลดการกรอกบัญชีทุกครั้ง. เอกสารนี้เป็นแบบที่ PO ตรวจจากโค้ดและแหล่งข้อมูลแล้ว ไม่ใช่ผลยืนยันว่าเปิดใช้ 48 ชั่วโมงจริง. Claude design review หมดเวลา180.7s ก่อนส่งไฟล์; PO ตรวจ process และรับ ownership กลับก่อนเขียน. NOT_RUN_BY_DEVELOPER.

## สาเหตุและผลที่ต้องการ

ตัว probe ปัจจุบันตั้ง `refreshTokenNeeded=False` ทั้ง login/MFA และเก็บ access token ใน memory จน process จบเท่านั้น. การขอ email/password ใหม่ทุกรอบเกิดจากการออกแบบของเรา ไม่ใช่หลักฐานว่า Tapo บังคับล็อกอินใหม่ทุกคำสั่ง. โทเคนรอบก่อนหมดไปแล้ว จึงต้องล็อกอินผ่านหน้าต่างส่วนตัวอีกครั้งตอนเปิดใช้ระบบใหม่.

ผลที่ต้องส่งมอบ: ล็อกอินครั้งเดียว แล้วคำสั่งที่รันใหม่หรือหลัง restart ใช้เซสชันเดิมได้จนถึงเส้นตาย48h โดยไม่กรอก email/password/OTP ซ้ำในเส้นทางปกติ. นี่เป็นเพดานการใช้ที่โปรแกรมกำหนด ไม่รับประกันอายุโทเคนฝั่งผู้ผลิต. Mac ยังต้องตื่น มีเครือข่าย และเข้าถึง Keychain ได้เมื่อทำงาน; การจำเซสชันไม่ทำให้ Codex ทำงานต่อเนื่อง48hหรือสร้าง scheduler.

## แบบที่เลือก

1. **Python session manager** เป็นจุดเดียวที่ auth, discovery และ SD adapter เรียกใช้. เลิกเปิด native login โดยอัตโนมัติทุกครั้ง. เปิดช่องกรอกเมื่อเป็นคำสั่งเริ่มเซสชันหรือจำเป็นต้องยืนยันใหม่เท่านั้น.
2. **Native Keychain helper** ขนาดเล็ก ใช้ Swift กับ Apple Security framework ที่มี compiler บน Mac แล้ว. รับคำสั่งจำกัดผ่าน subprocess pipe จาก Python; ไม่มี token ใน argv/environment/terminal output/log. ไม่ใช้ `security ... -w <secret>` หรือไฟล์ plaintext แม้ chmod0600.
3. **Keychain item เฉพาะโปรเจกต์** เป็น generic-password item มี service/account identifier คงที่ซึ่งไม่ใช่อีเมลจริง. จำกัด query/add/update/delete ที่ item นี้และ Keychain ของผู้ใช้ที่เลือกไว้ชัดเจน; ไม่ enumerate ค้นหรือแก้ item อื่น. ใช้ local nonsynchronizing storage ไม่ส่งเข้า iCloud Drive/iCloud Keychain.
4. **Keychain backend ที่เสนอสำหรับ CLI:** SecItem APIs บน file-based login Keychain พร้อม SecAccess ACL ของ helper ที่มีตัวตน/ลายเซ็นและตำแหน่งคงที่. Apple แนะนำ data-protection backend เมื่อเหมาะสม แต่มี access-group/signing constraints ต่างกัน; ไม่อ้างว่า CLI ใช้ data-protection ไม่ได้ และไม่คัดลอก iOS accessibility flags มาใช้กับ file-based backend. ต้องพิสูจน์การอ่านข้าม process และ signing/ACL ด้วย item จำลองก่อนเลือก backendขั้นสุดท้าย. ห้ามเปิด all-app access (`-A`) หรือแก้ global Keychain/security settings เพื่อหลบ prompt.
5. **Pinned HTTPS client** เดิมยังควบคุม host/CA/target/ขอบเขตคำสั่ง. Token ของบัญชีอาจเข้าถึงกล้องอื่นได้ตามสิทธิ์ Tapo แต่โปรแกรมยังบังคับเฉพาะกล้องที่ Owner เลือก; Keychainไม่ได้ทำให้สิทธิ์ vendor token แคบลงเอง.

## ข้อมูลที่เก็บ

เก็บในค่า item ที่เข้ารหัสโดย Keychain: `schema_version`, access token, refresh tokenถ้ามี, terminal UUID, `issued_at_utc`, `hard_expires_at_utc`, `last_seen_utc`, name-selector digest และ selected-device digest. เก็บเฉพาะค่า host/region ที่ผ่าน allowlist ไม่เชื่อ URL ที่อ่านกลับมาโดยอัตโนมัติ. ไม่เก็บ password, OTP, raw login response, ชื่อกล้อง, อีเมล หรือวิดีโอ. หาก protocolจำเป็นต้องมีข้อมูลเพิ่ม ให้พิสูจน์ความจำเป็นก่อนเพิ่ม.

เวลาเริ่มนับคือการยืนยันตัวตนสำเร็จครั้งแรกของ sessionนั้น. บันทึกได้หลังยืนยัน unique target และ C545D familyแล้ว; การรอ discoveryไม่เลื่อนเวลาเริ่ม. `hard_expires_at = issued_at + 172800วินาที` เป็นขอบเขตตายตัว.

## ลำดับการใช้งาน

| เหตุการณ์ | พฤติกรรม |
|---|---|
| ยังไม่มีเซสชัน | คืน `REAUTH_REQUIRED`; คำสั่งเริ่มเซสชันเปิด native email/password/MFA หนึ่งรอบ |
| ล็อกอินและเลือก target สำเร็จ | ขอ refresh token, validateข้อมูล แล้วเก็บ item; รายงานเวลาใช้งานได้ถึงเมื่อไรโดยไม่มี secret |
| รันคำสั่งใหม่ใน48h | อ่าน item ตรวจ schema/เวลา/host/digest แล้วใช้ tokenเดิม re-discover target; ไม่มีช่องกรอก |
| access tokenหมดอายุหรือ401ที่ยืนยันได้ | refreshได้สูงสุด1ครั้ง แล้ว replayเฉพาะ inventory readที่ปลอดภัยได้1ครั้ง; นับรวมใน budget |
| refreshสำเร็จ | update token/refresh-token rotation แบบหนึ่ง item พร้อม revision check; deadlineเดิมไม่เปลี่ยน |
| refreshถูกปฏิเสธ/เพิกถอน/ไม่มีrefresh token | หยุดและคืน `REAUTH_REQUIRED`; ล้างเซสชันที่ใช้ไม่ได้ ไม่วน popup/refresh |
| network timeout/429/5xx | รายงานข้อผิดพลาดเครือข่าย ไม่ตีความว่า tokenเสียและไม่ลบทิ้งโดยพลการ |
| Keychainล็อกหรือปฏิเสธสิทธิ์ | `SESSION_LOCKED`/`STORE_DENIED`; ไม่เปิด plaintext fallback หรือเปลี่ยน Keychain settings |
| ครบ48h | ปฏิเสธการใช้และ refreshทันที; ลบ itemเมื่อเข้าถึงได้ ไม่เลื่อนอายุอัตโนมัติ |
| Ownerสั่งลืมเซสชัน | ลบเฉพาะ itemนี้ ปล่อย referenceใน process; ไม่อ้างว่า revokeทุกsessionที่server |

ก่อน network operation ที่ต้องใช้ auth ให้ตรวจ deadlineซ้ำ รวมถึงก่อน/หลัง refresh และก่อน callbackเข้าอุปกรณ์. ห้าม replay downloadหรือคำสั่งที่ผลไม่แน่นอนเพียงเพราะ tokenหมดอายุ. หากภายหลังมีงาน mediaยาว ให้กำหนด abort/partial-output semantics ในใบงาน media; เซสชันนี้ไม่เปิดสิทธิ์ดาวน์โหลดเพิ่ม.

หนึ่ง session operation ถือ process lock จนใช้/หมุน/บันทึก tokenจบ ป้องกัน concurrent refresh และคำสั่ง forgetแข่งกับการใช้. หลัง restartอ่านเวลาเดิมจาก Keychain; sleepนับรวม. ใช้ monotonic clockตรวจ elapsedภายใน processและตรวจ wall-clockเทียบ `last_seen` ที่บันทึก. เมื่อพบเวลาไหลย้อนให้หยุด ไม่ต่ออายุเอง. แบบ softwareนี้ไม่อ้างว่าป้องกันผู้มีสิทธิ์สูงที่ย้อนทั้งนาฬิกาและข้อมูลเก่าได้.

ไม่มี schedulerในแบบนี้: เมื่อ Macหลับ/ปิด จะไม่สามารถรับรองการลบทางกายภาพตรงวินาทีที่48hได้. รับรองที่ออกแบบคือ **ห้ามนำไปใช้อีกเมื่อเกิน deadline**; cleanupทำเมื่อโปรแกรมกลับมารันและ Keychainพร้อม. หากลบไม่ได้ ให้คงสถานะหมดอายุและรายงาน cleanup pending.

## Refresh: ส่วนที่ยังต้องพิสูจน์

Pinned OnTapo ขอ `refreshTokenNeeded=True`, อ่าน `result.refreshToken` และ POST JSON `{method:refreshToken, params:{appType,refreshToken,terminalUUID}}` ไป account originที่เส้นทาง `/`. ไม่ได้พิสูจน์ token lifetime48hของกล้อง/บัญชีเรา.

Candidateแรกคือ POST `/` บน account hostเดิมที่ตรวจแล้ว `n-wap.i.tplinkcloud.com`, ใช้ CA pinเดิมและ body shapeตายตัว. เป็น endpointใหม่ใน allowlistจึงต้องแก้พร้อม guard/testsแบบแคบ; ไม่เปิด arbitrary POST. `n-aps1-wap` ยังเป็น metadata-only ตามกติกาเดิม ไม่เลื่อนไปส่งcredentialsโดยเดา. ไม่มี host fallbackหรือปิด TLS. ต้อง live-test refreshก่อนประกาศว่า tokenต่ออายุเองได้จริง. อายุที่serverแจ้ง (ถ้ามี) ต้องตรวจชื่อฟิลด์/หน่วยจากหลักฐานก่อนนำมาใช้; ไม่เดาว่า access tokenอายุ48h.

กำหนด auth-operation ceiling6 HTTPS requests/120s cooperative,10s socket/1MiBต่อresponse; refreshสูงสุด1และ replay inventoryสูงสุด1อยู่ในเพดานนี้. Device probeเดิมยังสูงสุด4requests/90sแยกกัน. ใช้ on-demand refresh ไม่สร้าง pollingเพื่อให้เซสชันไม่หมดอายุ. Explicit auth-invalidกับ transient failureต้องจำแนกแยกกัน.

## ขอบเขต implementation ถัดไป

| ไฟล์ที่เสนอ | หน้าที่ |
|---|---|
| `tools/ft_session.py` | state machine,48h validation, lock, redacted status/forget, Keychain bridge |
| `tools/native/ft_keychain.swift` | จำกัด store/load/deleteของproject item; bounded private pipe protocol |
| `tools/ft_cloud_probe.py` | แยก authจากdiscovery, รับ session provider, request/validate refresh-tokenและrefresh endpointแบบแคบ; เก็บ legacy no-cache diagnosticได้ |
| `tools/ft_sd_probe.py` | เรียก session providerแล้วใช้ named-target/device guardsเดิม |
| `tests/test_ft_session.py` และ auth/SD testsเดิม | synthetic failure/expiry/reuse/refresh/redaction/integration boundaries |
| `docs/SESSION_48H_GUIDE.md` | คำสั่งใช้งาน ข้อจำกัด ผลทดสอบจริง และ recovery |

POต้องจัด implementation controlให้รองรับ native helperเฉพาะงานนี้ (ข้อยกเว้นจาก Python-onlyเดิม), exact Keychain service/account selectors, installation directoryเฉพาะแอปนอกgitและ host/path refreshก่อน dispatch. ไม่สร้าง worktree/branchใหม่. Compiled helperไม่เข้าgit; ไม่เพิ่มแพ็กเกจหรือซื้อ developer account. หากต้องใช้ identity/entitlementที่เครื่องยังไม่มี ให้รายงานผลทดลองจริงและเลือก implementationที่ตรวจได้ ไม่ลดการป้องกันเอง.

ไม่มีการเปลี่ยน Keychain/เปิดเซสชันจริงในงานออกแบบนี้. คำขอ Ownerเป็นที่มาของการออกแบบให้จำเซสชัน ไม่ใช้ memory-only policyเก่ามาขออนุมัติความต้องการเดิมซ้ำ.

## เกณฑ์ตรวจรับก่อนเปิดใช้

- Mock clock: ก่อน48hใช้ได้; เท่ากับ/เกิน48hปฏิเสธ; refresh/restart/sleepไม่เลื่อนdeadline; clock rollback/schema/target/hostไม่ตรงหยุดก่อนnetwork.
- Mock network: valid-sessionสองprocessไม่เปิดdialog; 401นำไปrefreshได้ครั้งเดียว; 403/429/5xxไม่ทำrefreshแบบเหมารวม; token rotation/store failureไม่รายงานcached-successผิด; concurrent use/forgetไม่เกิดrace.
- ตรวจไม่มีsecretในstdoutที่แสดงให้tools/user, argv, environment, exceptions, repo,ไฟล์temp/logหรือiCloud. Private pipeที่ส่งค่าให้parentต้องถูกconsumeในprocessและไม่forwardเข้าtool output.
- ทดลอง Keychainด้วยrandom disposable project-test itemเท่านั้น: write/readอีกprocess/update/delete, locked/denied outcomes, narrow ACL/signingและการไม่sync. ไม่ค้นitemส่วนตัว. ลบtest itemหลังจบ.
- หลังreview: native private loginครั้งเดียว สร้าง48h lease แล้วรัน inventory/SD diagnosticอีกprocessให้สำเร็จโดยไม่ขอemail/password/MFA. ยืนยัน actual refresh/rotationแยกจากcache reuse; ไม่ทำลายsessionเพื่อบังคับ401โดยเดา.
- สถานะแยก: `CACHE_REUSE_VERIFIED`, `REFRESH_VERIFIED`, `LOCAL_48H_EXPIRY_TESTED`, `VENDOR_48H_OBSERVED`. Accelerated testsพิสูจน์กติกาเวลา ไม่แทนการใช้งานvendorจริงครบ48h. การรอสังเกตครบ48hต้องเป็นงานที่มีrunnerจริง ไม่อ้างว่าทำเบื้องหลังเมื่อไม่มี.

## แหล่งหลักฐาน

- โค้ดในrepo: `tools/ft_cloud_probe.py`, `tools/ft_sd_probe.py`; ผล liveล่าสุดอยู่ STATUS.
- [OnTapo session.py pinned](https://github.com/noriellecruz/ontapo/blob/a387f6abddb72f7e6eea72b374df5ad189da1f5f/src/ontapo/session.py): reuse/refresh candidate; ไม่ใช่การรับรองจากผู้ผลิตหรือผล live refreshของเรา.
- [Apple: Using the keychain to manage user secrets](https://developer.apple.com/documentation/security/using-the-keychain-to-manage-user-secrets) และ [TN3137: On Mac keychain APIs and implementations](https://developer.apple.com/documentation/technotes/tn3137-on-mac-keychains): encrypted secret storage, SecItem, backend/ACL distinctions. POอ่านTN3137 Markdownทางการเมื่อ2026-10-12.
- [Apple: kSecAttrSynchronizable](https://developer.apple.com/documentation/security/ksecattrsynchronizable): syncเป็นคุณสมบัติที่ต้องควบคุมต่อitem; ไม่อ้างว่าเปิดiCloudบนเครื่องแล้วทุกitemต้องsync.

การตรวจงานออกแบบ: diff check PASS; POรันชุดเดิม510/510 PASS (28.479s) เพื่อยืนยันbaselineตามrepo workflow. ไม่มีโค้ดเซสชันใหม่และผลนี้ไม่ยืนยันKeychain/reuse/refresh/48h.
