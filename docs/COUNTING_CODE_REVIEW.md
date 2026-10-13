# Code Review: Counter & Evaluation (Advisory, NOT_RUN_BY_DEVELOPER)

ขอบเขต: ตรวจเฉพาะ excerpt 2 ฟังก์ชันที่ให้มา (ไม่ได้อ่านซอร์สทั้งไฟล์/ไม่รันเทส) — ไม่ใช่การยืนยัน security/completeness ของระบบทั้งหมด

## ข้อบกพร่องที่พบ (concrete)

1. **`_signed_side` หารด้วยศูนย์ได้**: `math.dist(*self.line)` ถ้า `line[0]==line[1]` (ตั้งค่าเส้นผิดพลาด) จะ raise `ZeroDivisionError` ไม่มี guard — ควร validate เส้นตอน init ไม่ใช่ปล่อยให้พังตอน runtime
2. **`anchor` ถูก overwrite ทุก update แม้ side ไม่เปลี่ยน**: จึงวัด `MIN_DISPLACEMENT` จากแค่ก้าวล่าสุดก่อนข้ามเส้น ไม่ใช่ระยะทางสะสม → เดินช้าๆ ข้ามทีละ step เล็กๆ อาจหลุด threshold (false negative), ขณะที่ track ID กระโดดจาก occlusion/re-acquire ก้าวเดียวไกลพอจะผ่าน MIN_DISPLACEMENT ได้ง่าย (false positive/ทิศผิด) — ตรงกับ evidence ที่พบ direction confusion ตอนคนเดินสวนกันที่ 43s
3. **ไม่มี track-identity continuity check**: โค้ดเชื่อ `track_id` เดิมจาก tracker ล้วนๆ, ถ้า ByteTrack สลับ ID ตอนคนชนกัน ตรรกะนี้ไม่มีทางตรวจจับ — ระดับ counter แก้ไม่ได้ ต้องแก้ที่ tracker/matching

## evaluate()
- Design สมเหตุสมผล (ตรง direction, DP one-to-one, cap 500 event) แต่ **ไม่ตรวจว่า predicted/truth ผูกกับ hash เดียวกันจริง** ตามที่ docstring บอกไว้ว่าเป็นหน้าที่ของผู้เรียก — เป็นช่องโหว่เชิง process ไม่ใช่โค้ด

## สรุปเทียบ evidence
ผล P/R/F1 92.3% บนหน้าต่าง 0–50s (manual, single reviewer) **สนับสนุนได้แค่ scoped pilot ในเงื่อนไขเดิม** (กล้องเดิม/มุมเดิม/ความหนาแน่นต่ำ) เท่านั้น ไม่ใช่หลักฐานความแม่นยำระดับ full-day หรือฉากที่มีคนชนกันถี่กว่านี้ — ข้อบกพร่อง #2 อธิบาย error เดียวที่พบได้ตรงกัน จึงควรแก้ anchor-tracking ก่อนขยาย pilot

## PO disposition after reading full source and tests

- Finding1 is not present: CrossingCounter.__init__ rejects zero-length lines before _signed_side; config validates again. Existing degenerate-line tests cover this. The supplied excerpt omitted the constructor.
- Finding2 slow-cross claim is not present for the deployed preset: side0 returns before anchor replacement, preserving the last point beyond the deadband; deadband0.012 implies at least0.024 normal displacement across opposite confirmed sides, above MIN_DISPLACEMENT0.01. Added0.001-step regression alongside existing gradual-cross test. Do not attribute the43s direction error to this unproven cause.
- Finding3 remains a measured limitation: geometry/temporary tracker IDs can confuse two crossing people. No face/appearance identity model added; one direction error in reviewed13events is reported. Broader accuracy remains unverified.
- Added evaluate_report wrapper that rejects mismatching input/config hashes, with tampered-binding regression tests. Pure evaluate remains useful for synthetic event tests.
- Claude focused advisory completed exit0/40.0s, NOT_RUN_BY_DEVELOPER. PO owns final code/test/real-media acceptance. Evidence supports supervised noon pilot only, not a full-day accuracy guarantee.
