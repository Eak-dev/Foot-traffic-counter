# จุดเชื่อมอ่านรายการ SD แบบ offline (OD-33)

`tools/ft_tapo_bridge.py` เชื่อมวิธีอ่านรายการเข้ากับ guard ของ `ft_acquire`
ด้วย SDK class, sender และ clock ที่ caller ส่งให้. ทดสอบด้วย SDK จำลองเท่านั้น;
ยังไม่ import/รัน `pytapo` ที่ติดตั้ง ไม่ authenticate และไม่ต่อกล้องจริง.

## API และขอบเขต

- `Bridge(sdk_class, sender, clock, max_calls=..., deadline_s=..., max_index=..., max_time_range=..., max_page_size=...)`
  ต้องระบุเพดานทั้งหมด; ไม่เรียก constructor/สร้าง subclass ของ SDK.
- `list_day(date, start_index, page_size)` รับวัน `YYYYMMDD` ที่ถูกต้อง.
- `list_utc(start_time, end_time, start_index, page_size)` รับช่วง UTC integer ที่จำกัดแล้ว.
- Bind เฉพาะ `getUserID`, `getRecordings`, `getRecordingsUTC`, `executeFunction`
  บน facade ของเรา; `performRequest` ผ่าน guard และ `setCruise` ถูกปฏิเสธ.
- คำขอต้องตรงวัน/ช่วงเวลา/ดัชนีที่เลือก. ไม่ยอม token refresh/listing retry,
  คำสั่งเปลี่ยนกล้อง หรือการเรียกซ้อนที่รีเซ็ตงบคำขอ.
- เมื่อ SDK/sender/response/clock ผิดพลาดจะ latch FAILED; API ครั้งต่อไปไม่ส่งคำขอ.
  Invalid input ที่ปฏิเสธก่อนเริ่มงานยังแก้แล้วเรียกใหม่ได้.
- รับเฉพาะ envelope/ผลตอบกลับ JSON ที่จำกัด depth/nodes/จำนวน records;
  คืนสำเนาแยกสำหรับ future normalizer ภายใน ไม่ใช่ manifest ที่เผยแพร่ได้.
  ไม่เดา Fixed Lens/timezone จาก raw records และไม่ดาวน์โหลดคลิป.

## สิ่งที่ต้องตรวจต่อก่อนใช้จริง

Source reference คือ [pytapo 3.4.26 snapshot](https://github.com/JurajNyiri/pytapo/blob/a2f0fbd1fa4f4fc79e9fb5df4e9893ca55a3ba8c/pytapo/__init__.py).
PO ตรวจโครงสร้าง attributes ของสี่ methods แบบ AST; ไม่ execute source.
Class ที่ caller ส่งให้ต้องเป็น class ที่ audit/pin แล้ว; bridge ไม่พิสูจน์ version
หรือเป็น sandbox สำหรับ Python SDK ที่ไม่น่าเชื่อถือ.

Deadline เป็น cooperative; หยุด callback ที่ค้างกลาง call ไม่ได้. Transport จริงต้อง
มี interruptible timeout และจำกัด response bytes ก่อน parse. Auth/media framing,
การเลือก Fixed track/metadata/timezone และ atomic file publication ยังไม่ implement.
เพดานพัฒนาไม่ใช่ quota ที่ Owner อนุมัติให้กล้องจริง.

PO จัดใบงานให้ Claude ตรวจและพัฒนาแต่ละส่วน แล้วตรวจอิสระก่อน checkpoint;
Owner ไม่ต้องประสาน Dev หรือรัน Terminal. Route/credentials/metadata/quota และ
scope ทดลองหนึ่งคลิปต้องพร้อมก่อน live. ไม่มี scheduler หรือสิทธิ์ merge เพิ่ม.
