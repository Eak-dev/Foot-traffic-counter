# ft_acquire — ส่วนควบคุมการดึงคลิปแบบ offline (OD-32)

ส่วนนี้ทำงานกับ callback และข้อมูลจำลอง ยังไม่มีการเชื่อมกล้องจริง

## มีอะไรบ้าง (implemented จริง)

- `validate_sd_request` / `guarded_send` — ตรวจรูปร่าง request ของ
  `multipleRequest`/`getUserID`/`searchVideoOfDay`/`searchVideoWithUTC` แบบ
  whitelist เท่านั้น บล็อก setter/control ทุกชนิด แล้วค่อยเรียก `sender` ที่
  caller ฉีดเข้ามา (เป็น callable ธรรมดา ไม่ได้ผูกกับ pytapo หรือ socket จริง)
- `collect_pages` — paginate ผ่าน `fetch_page` ที่ caller ฉีดเข้ามา มี bound
  ครบ (page/record/deadline) กัน stall และกัน index เข้าใกล้ค่า sentinel ที่
  upstream ใช้เป็น "ไม่จำกัด"
- `copy_bounded` — สตรีมไบต์จาก iterable ที่ caller ฉีดเข้ามา ผ่าน sink
  แบบไฟล์ (มี `.write()`) โดยมี budget ไบต์ และ deadline แบบ cooperative
  (เช็คจังหวะระหว่างสเตปที่แยกจากกันได้เท่านั้น) คืนค่า
  `{"status": "STAGED", "bytes_written": <int>, "sha256": <hex64>}` เมื่อสำเร็จ
- `Manifest.add_clip` — บันทึก clip ลง manifest ในหน่วยความจำ โดยรับเฉพาะผล
  `staged_result` ที่มี schema ตรงกับผล `copy_bounded` โดย caller ต้องใช้ผลรับ
  ข้อมูลจริงเมื่อมี live adapter; core ไม่ตรวจ provenance ของ dict นี้เอง.
  ต้องมี `fixed_mapping_verified` / `container_validated` /
  `duration_validated` เป็น `True` ทุกตัว, `lens` ต้องเป็น `"FIXED"` เป๊ะ,
  `container` ต้องเป็น `"mp4"` หรือ `"mpegts"` เท่านั้น, และ duration ต้อง
  ตรงกับ `end - start` ภายใน tolerance ที่ caller ระบุ
- `check_command` / CLI `check` — คืนสถานะ `BLOCKED`/`NOT_TESTED` เสมอ ไม่เคย
  ต่อ network ไม่เคย import pytapo ไม่เคยอ่าน config จริง

ตัวอย่าง (synthetic ทั้งหมด ไม่ใช่ข้อมูลกล้องจริง):

```python
staged = copy_bounded(iter([b"....mp4-bytes...."]), sink,
                       expected_length=16, max_bytes=16,
                       deadline_s=30, clock=time.monotonic)
manifest.add_clip(
    ref="clip-1", start=start_dt, end=end_dt,
    lens="FIXED", container="mp4",
    duration_s=(end_dt - start_dt).total_seconds(), duration_tolerance_s=0.5,
    staged_result=staged,
    fixed_mapping_verified=True, container_validated=True, duration_validated=True,
)
```

## คำสั่ง stdout จริง

```
$ python3 tools/ft_acquire.py check
```
พิมพ์ JSON แล้ว **exit code 2 เสมอ** (ไม่ใช่ 0) เพราะยังไม่มีเส้นทางที่ผ่านการ
ตรวจแล้ว — `status` เป็น `"BLOCKED"`, `route`/`auth`/`download` เป็น
`"NOT_TESTED"`, `backend_binding` เป็น `"NOT_IMPLEMENTED"` และ `camera_requests` เป็น 0

## ข้อจำกัดจริง (ไม่ใช่ความเห็น)

- `fixed_mapping_verified` / `container_validated` / `duration_validated`
  เป็น **input ที่ caller ต้องพิสูจน์มาจากที่อื่น** (validator แยกที่ยังไม่มี
  ในโปรเจกต์นี้) การส่ง `True` เข้ามาไม่ใช่หลักฐานว่ากล้องจริงหรือไฟล์จริงผ่าน
  การตรวจแล้ว — เป็นแค่ "สัญญา" ที่ฟังก์ชันนี้บังคับให้ต้องประกาศก่อนเท่านั้น
- `copy_bounded` ไม่สามารถ "ขัดจังหวะ" `sink.write()` หรือ source ที่ค้างอยู่
  กลางคอลแบ็กเดียวแบบ synchronous ได้ — deadline check ทำงานได้แค่ระหว่าง
  สเตปที่แยกกัน ถ้า callback ที่ caller ฉีดมาค้างอยู่ในคอลครั้งเดียวตลอดกาล
  ฟังก์ชันนี้จะค้างตามไปด้วย การขัดจังหวะ transport/socket จริงต้องทำนอก
  โมดูลนี้ (process/socket-level timeout ที่ยังไม่ implement ที่นี่)
- ถ้า `copy_bounded` ล้มเหลวกลางทาง **caller เป็นคนรับผิดชอบลบ/เคลียร์ของที่
  เขียนไปแล้วใน sink เอง** — ฟังก์ชันนี้ไม่ย้อนลบอะไรให้
- `Manifest` อยู่ใน**หน่วยความจำอย่างเดียว** ไม่แตะ filesystem/database จริง
  ปิดโปรแกรมแล้วข้อมูลหาย
- ยังไม่ implement ในคอร์นี้ (ต้องงานตรวจสอบแยกก่อนแตะกล้องจริง): auth จริง,
  transport/constructor ของ `pytapo` หรือไลบรารีกล้องอื่น, interception ของ
  constructor จริง, การ encode/decode media จริง, และการเขียน/publish ไฟล์จริง
  ลงดิสก์ — ไม่มีสักอย่างในลิสต์นี้ที่ทำโดยโมดูลนี้
- โมดูลนี้ไม่เคยต่อกล้องจริงสักครั้ง (`real_camera: 0`) และ ceiling ตัวเลข
  ต่าง ๆ ในโค้ด (เช่น `DEV_MAX_INDEX_CEILING`) เป็น**เพดานพัฒนาเพื่อความ
  ปลอดภัยเท่านั้น** ไม่ใช่โควตาที่ policy จริงอนุมัติแล้ว

## งานของ PO

งานตรวจสอบที่เหลือ (เช่น ต่อ validator จริง, ต่อ pytapo, เขียนไฟล์ลงดิสก์จริง)
ทีมพัฒนาผ่าน Claude ตามใบงาน และ PO ตรวจ/รันบน Mac ที่ Owner อนุญาต
Owner ไม่ต้องเปิด Terminal. การทดลองจริงยังต้องมี route/credentials/metadata/quota
ที่ตรวจแล้ว และต้องมี scope เฉพาะก่อนเชื่อมกล้อง
