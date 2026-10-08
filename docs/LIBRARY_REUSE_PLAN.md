# ใช้ GitHub library เป็นส่วนดึงคลิป SD ของโปรแกรมเรา

สถานะ 2026-10-08: SOURCE_AUDITED / OFFLINE_CORE_AND_CONTROL_BRIDGE_IMPLEMENTED / LIVE_TRANSPORT_NOT_IMPLEMENTED. OD-31 source research ที่ baseline `d25670ef335ae772f1a96778fb111bf062942c28`; OD-32 core ที่ `62572b2aa91d2a937498a1a5331500ee10889f95`; OD-33 control bridge ที่ `9f645fc71bcfa5262e722b0c3d1b608f7a04435f`, branch เดิม. ไม่เปิดเกตกล้อง; IP/runtime ยังเป็นข้อมูล local ไม่ส่งให้ coding agent.

## ข้อเสนอที่เลือก

ใช้ `pytapo==3.4.26` เป็น backend ของโปรแกรม CLI ที่ทีมพัฒนาเอง. เวอร์ชันนี้ติดตั้งใน runtime แยกแล้วตาม OD-24; ไม่ต้องลง Home Assistant, Docker, web server หรือ Hub เพิ่ม. ไม่คัดลอกตัวอย่างที่ดึงทั้งวันมารันตรง ๆ. `pytapo` จัดการ protocol/auth/media; โปรแกรมเราเพิ่มขอบเขตคำสั่ง, listing limits, quota, deadline, การตรวจ Fixed Lens และการไม่ดึงซ้ำ. Compatibility กับ C545D HW 1.0 / FW 1.1.7 ยังต้องพิสูจน์หนึ่งคลิปหลัง route/auth/storage gates.

## เปรียบเทียบจาก source ที่ผูก commit

| Candidate / snapshot | สิ่งที่ source ทำได้ | ความเหมาะสม |
| --- | --- | --- |
| [JurajNyiri/pytapo](https://github.com/JurajNyiri/pytapo/tree/a2f0fbd1fa4f4fc79e9fb5df4e9893ca55a3ba8c), version 3.4.26, MIT | `getRecordings` / `getRecordingsUTC` และ `Downloader` ดึง SD; media session เปิด TCP ไป host โดยตรง | เลือกเป็น backend candidate; เหมาะกับต้นฉบับ SD แต่ไม่สร้างเส้นทางบ้าน→ร้าน |
| [mihai-dinculescu/tapo](https://github.com/mihai-dinculescu/tapo/tree/de769da4868d00ae3ad0968c276753062e0d8a1d), MIT | Python/Rust API; `CameraHubHandler` list/download recordings จาก H200/H500; media TCP ไป Hub โดยตรง. Camera PTZ handler ที่อ่านไม่มี API ดึง SD standalone แบบเดียวกัน | ไม่เลือกแทน pytapo รอบนี้: ร้านไม่มี Hub และยังไม่มี C545D standalone SD evidence; ไม่ติดตั้งเพิ่ม |
| [dimme/tapo-cli](https://github.com/dimme/tapo-cli/tree/8bb5f6d2f231cec55d43465f3169ac58f3d4c219) | CLI สำหรับ Tapo Care cloud recordings; source ระบุไม่ list camera SD clips | ไม่ตรงต้นฉบับ SD เดิม; ไม่เปลี่ยนไปสมัคร Tapo Care. ไม่พบ license จาก GitHub metadata/tree ที่ตรวจ จึงไม่เสนอ copy source |
| [yimstar9/tapo-h200-recording-downloader](https://github.com/yimstar9/tapo-h200-recording-downloader/tree/619cd787f2e445be58b86b4c14acc3bbb666a09d) | Local H200 + paired D230; มี media patch, config/env persistence และ network scan | ไม่ตรงอุปกรณ์ที่ร้าน; ไม่รัน scanner/config writer. ไม่พบ license จาก metadata/tree ที่ตรวจ จึงไม่เสนอ copy source |

MIT license ของ pytapo อ่านจาก [LICENSE](https://github.com/JurajNyiri/pytapo/blob/a2f0fbd1fa4f4fc79e9fb5df4e9893ca55a3ba8c/LICENSE). หากแจกจ่าย/ดัดแปลงส่วน upstream ให้คง copyright และ license notice ที่เกี่ยวข้อง; ใช้ dependency ที่ pin แทน vendor ทั้ง repo. License ไม่ใช่หลักฐานความเข้ากันได้กับกล้อง.

## จุดที่ต้องแก้ก่อนใช้ backend จริง

จาก static audit ของ `pytapo/__init__.py` ที่ snapshot ข้างต้น: constructor เรียก device info/presets; `executeFunction` เมื่อพบ error `-64303` อาจเรียก `setCruise(False)` แล้ว retry. แม้เรียก getter ก็ยังอาจมีคำสั่งเปลี่ยนกล้องผ่าน recovery นี้. จึงห้ามถือว่าเรียกเฉพาะ public getter แล้วเป็น read-only โดยอัตโนมัติ.

Adapter ต้องตรวจคำสั่งที่ขอบเขตส่ง request จริง: auth ที่จำเป็น, getters ที่ระบุ และ SD listing/download เท่านั้น; ตรวจ nested `multipleRequest` ด้วย. Recovery ที่ส่ง setter ให้หยุดด้วยรหัส redacted ก่อนส่ง ไม่ปิด cruise, ไม่หมุน PT, ไม่เปลี่ยน privacy/reboot/settings. การ override getter หรือจับ exception หลัง request ไม่เพียงพอ. เลือก narrow patch/subclass ที่ audit ครบ พร้อม synthetic request-spy tests ก่อน device trial; ไม่แก้ upstream ที่ติดตั้งแบบเงียบ ๆ และไม่เพิ่มสิทธิ์ให้ Dev.

`Downloader` มี retry/fallback และข้อมูล buffer/temp ก่อน output; การ polling ขนาดไฟล์ปลายทางอย่างเดียวจึงไม่จำกัด bytes ทั้งหมด. ต้องบังคับ byte budget ก่อนเก็บแต่ละ chunk, deadline รวม, temporary storage, retry/fallback policy ในจุดรับข้อมูลจริง. ถ้าขอบเขตนี้ทำผ่าน public API ไม่ครบ ให้ reuse protocol/crypto ที่ตรวจแล้วและเขียน transfer loop ที่จำกัดเอง พร้อมคง notice; ยังไม่ประกาศ wrapper พร้อม.

## แบบโปรแกรมและสถานะงานพัฒนา

OD-33 เพิ่ม [control-method bridge](TAPO_BRIDGE_GUIDE.md) แล้ว: bind เฉพาะ 4 audited methods บน facade โดยไม่เรียก constructor, guard ก่อน sender, fixed query scope, suppress retry/recovery และ latch failures รวม malformed SDK/replies. PO tests 330/330 PASS, static source attributes/import contract PASS. ทดสอบ SDK จำลอง; actual pinned SDK identity/execution, authentication และ transport ยังไม่ตรวจรับ. ไม่ใช่ sandbox สำหรับ SDK arbitrary code และไม่มี media downloader.

OD-32 เพิ่ม [offline core](ACQUISITION_CORE_GUIDE.md) แล้ว: strict SD request guard + injected sender, bounded normalized pagination, cooperative byte-copy, Fixed/container/duration proof inputs และ in-memory manifest/dedup. PO tests 295/295 PASS และ synthetic pipeline PASS. Core ยังไม่ import/ผูก pytapo; ไม่มี auth/media framing, interruptible transport, validator จริง หรือ atomic file publication. การตรวจ request shape ไม่ใช่หลักฐาน intercept constructor/recovery ของ upstream ได้แล้ว และ flags/staged dict ไม่พิสูจน์ provenance ด้วยตัวเอง.

| ส่วน | หน้าที่ / เกณฑ์ตรวจ |
| --- | --- |
| Offline plan/preflight | อ่านเฉพาะ configuration ที่ Owner ให้, ตรวจ runtime/schema/เกต; ไม่ import/instantiate pytapo, ไม่ค้น LAN; output redacted. ไม่บังคับ Owner เปิด Terminal |
| Backend boundary | lazy-load ใน process เฉพาะงาน live หลังเกต; network request allowlist, ไม่มี recovery setter; credentials ไม่เข้า args/env/log/Dev context |
| Bounded listing | ใช้วันที่/ช่วงคลิปที่ยืนยันแล้ว, explicit `start_index/end_index`, จำกัดหน้า/จำนวน/เวลา; ไม่ใช้ upstream default ที่ใหญ่มาก. Clock correction แยกจาก timezone |
| One-clip transfer | ดึงคลิปที่เลือกหนึ่งคลิป, staging นอก Git, total deadline/bytes/temp limits, no overwrite และ fail-closed partial result; quota เป็นข้อเสนอใน ONE_CLIP_PLAN ยังไม่อนุมัติ |
| Fixed Lens validation | ffprobe ตรวจ streams/duration และตรวจมุมกับต้นทาง; [ผู้ผลิต](https://www.tp-link.com/us/support/faq/4666/) อธิบาย VLC Track 1 Fixed / Track 2 PT แต่ไม่ใช้เลขนี้แทน downloader channel IDs. ไม่รวมยอด PT |
| Manifest/idempotency | ใช้ clip reference + SHA256, ไม่เผย path/ชื่อจริง; รับเป็นสำเร็จหลังตรวจไฟล์ครบ, retry ช่วงเดิมต้องไม่เพิ่มรายการซ้ำ |

ขั้น offline core/control-method binding → synthetic tests → PO review เสร็จตาม OD-32/33; ผล guard ไม่เปิดสิทธิ์ live. งานถัดไปคือ actual SDK identity/function audit และ scoped auth/media transport พร้อม interruptible deadlines/atomic staging. เมื่อ route/credentials/metadata/quota prerequisites ผ่านจึงทดลองหนึ่งคลิป แล้วค่อยขยายเป็น batch รายวันตาม D2→D3.

## ข้อสรุปเรื่องบ้าน→ร้าน

สร้างโปรแกรมเรียก library ได้และ reuse protocol ที่มีอยู่ช่วยลดงาน. แต่จาก transport code ที่ตรวจ ทั้ง pytapo และ Rust/Python Hub downloader ใช้ IP ที่ต้องเข้าถึงได้จริง; cloud password/cloud passthrough ไม่ใช่หลักฐาน media relay ข้ามเครือข่าย. ไม่มี candidate ที่ audit รอบนี้พิสูจน์ automatic remote SD ของ standalone C545D โดยไม่ต้องมี private route. ไม่ปิดงานค้นเส้นทางหรือผลักให้ Owner ถาม AIS; เป็นงานทีมตาม OD-30. ไม่สรุปว่าเป็นไปไม่ได้ และไม่เปลี่ยนเป้าหมายเป็น cloud recording/manual import โดยอัตโนมัติ.

## หลักฐาน source research OD-31

GitHub metadata/head/tree และ source 17 ไฟล์จาก 4 repositories อ่านเป็น public snapshots ชั่วคราว; ไม่ clone/install/import/execute upstream และไม่ใช้บัญชี Tapo/กล้องจริง. AST ตรวจพบ `setCruise` ใน error-recovery ของ `executeFunction`; ไม่ใช่ device test. ไม่มี new package/worker/scheduler. NOT_RUN_BY_DEVELOPER รอบ research; ผล PO unittest และสถานะส่งจริงอยู่ STATUS/delivery record.
