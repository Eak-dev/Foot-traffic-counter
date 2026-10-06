# FT-D0 — หลักฐานตรวจแยกโดย PO

วันที่ตรวจ: 2026-10-06 (Asia/Bangkok). Issue #1; branch `claude/ft-d0-preflight`.
Baseline: `73249aabf9d413325c4a772cd68a3ebc5890415e`.
ขอบเขต: เตรียมโครงการและเครื่องมืออ่านข้อมูลในเครื่อง — ไม่ใช่การดึงวิดีโอจากกล้องที่ผ่านการพิสูจน์แล้ว.

## สภาพแวดล้อมที่ตรวจจริง

| รายการ | ผล / แหล่งหลักฐาน |
| --- | --- |
| การรีโมต Mac ที่บ้าน | PASS: เรียก shell และอ่านสถานะโปรเจกต์ได้ |
| ระบบ | macOS 14.8.9, x86_64, RAM 16 GiB, CPU logical 8 |
| Python สำหรับ D0 | 3.9.6; ไม่ติดตั้ง package ใดเพิ่ม |
| พื้นที่ว่าง | ประมาณ 20.82 GiB ณ การตรวจ; ไม่ใช่งบเก็บคลิปที่อนุมัติแล้ว |
| Claude CLI | 2.1.288; executable อยู่และเรียก inference ได้จริง |
| Model smoke | `claude-sonnet-5`, Effort Low, no tools: exit 0, is_error false, result READY, modelUsage ยืนยันชื่อรุ่น |
| Claude พัฒนางาน | `claude-sonnet-5`, Effort High, restricted file tools; รอบแรก exit 0, success, 25 turns, permission denials 0 |
| Claude แก้ตาม review | รอบสอง exit 0, success, 29 turns, modelUsage claude-sonnet-5, permission denials 0; PO ตรวจ source hash ว่าตรงรุ่นที่ผ่านทดสอบ |
| GitHub connector | อ่าน repo และสร้าง Issue #1 สำเร็จ |
| Git push dry-run | exit 0; ยังไม่ใช่หลักฐานการเปลี่ยน remote ref และไม่เปลี่ยน credentials |
| Power settings | อ่านพบ idle sleep = 1 ทั้ง AC และ battery; ไม่แก้ค่า, ไม่ตรวจ active wake assertions; ความพร้อมรายคืน UNKNOWN |
| ffprobe / tailscale | ไม่พบบน PATH; ไม่ใช่ข้อกำหนด D0; ไม่ติดตั้ง |
| กล้อง/เครือข่ายร้าน | UNKNOWN / NOT TOUCHED |

ตัว doctor ตรวจ executable presence โดยไม่เรียก auth/inference; ค่า functional UNKNOWN ใน JSON ของ doctor จึงไม่ขัดกับผล smoke ที่ PO ทดสอบแยกต่างหาก.

## Root cause → แก้ไข → ทดสอบซ้ำ

1. รอบแรกมี 33 tests: 32 ผ่าน, 1 cleanup ERROR. สาเหตุคือ test ลบ temp tree ใน tearDown ก่อน cleanup chmod. Claude แก้ลำดับ cleanup โดยคงการทดสอบไฟล์อ่านไม่ได้ไว้.
2. PO พิสูจน์ว่า root symlink ต่อท้าย `/.` ถูกตามเข้าไปอ่าน. Claude เปลี่ยนการเปิด root/child เป็น anchored descriptor, ไม่ตาม final symlink; เพิ่มทดสอบ directory ที่ถูกสลับเป็น symlink.
3. PO พิสูจน์ว่าไฟล์โตระหว่าง hash ยังถูกรายงานสำเร็จ. Claude จำกัด bytes ที่อ่านและเทียบ inode/size/timestamps ก่อน–หลัง; ไฟล์ที่เปลี่ยนถูกระบุ INCOMPLETE/CHANGED.
4. PO พิสูจน์ว่า argparse แสดงค่าข้อมูลตัวอย่างที่อาจเป็นความลับใน error. Claude เปลี่ยนเป็น fixed error codes และเพิ่ม canary tests. ไม่ใช้ข้อมูลลับจริง.

## ผลทดสอบบน Mac จริง

- `python3 -m py_compile tools/ft_data.py tests/test_ft_data.py`: PASS.
- `python3 -m unittest discover -s tests -t . -v`: **52 tests, PASS, ไม่ข้าม permission test บน Mac นี้**.
- PO regression แยก 7 checks: root symlink-dot, changed-file rejection, unknown-argument redaction, read-only + byte-identical dedup, unknown source time/completeness, CLI invalid budget และ CLI missing input: **7/7 PASS**.
- `python3 tools/ft_data.py doctor --json`: exit 0, preparation PASS, **live_ready false**, camera route/credentials/firmware UNKNOWN.
- ค่า reserve เริ่มต้น 10 GiB เป็น PROPOSED_NOT_OWNER_APPROVED. ผล disk PASS ใช้เกณฑ์เสนอนี้เท่านั้น.
- ทดสอบ inventory ด้วย synthetic bytes ใน temporary directory ไม่ใช่วิดีโอจริง; ไม่มีการถ่ายโอนคลิปของร้าน.

## ขอบเขตของหลักฐาน

PASS หมายถึงการเตรียมเครื่องและพฤติกรรม CLI ที่ทดสอบ ไม่ได้ยืนยันการเชื่อมกล้อง การดาวน์โหลดจริง ความสมบูรณ์ของคลิป ความแม่นยำของการนับ หรือความพร้อมรายคืน.
การ hash ไม่ได้ตรวจว่า MP4 เล่นได้ และตรวจไฟล์ซ้ำได้เฉพาะไบต์เหมือนกัน ไม่ใช่ช่วงภาพซ้อน/วิดีโอเข้ารหัสใหม่.
การสแกนยึด selected root และ entries ภายใน; parent path อาจเป็น platform alias เช่น /tmp บน macOS. ไม่อ้างว่าเป็น filesystem sandbox หรือ atomic snapshot.

## การเปลี่ยนแปลงและความปลอดภัย

สร้าง clone/branch แยก และไฟล์โค้ด/เอกสารเท่านั้น. ไม่มี package install, login/logout, token change, การแก้กล้อง/router/VPN/power/security, scheduler, ML weights, การซื้อ หรือ production deploy.
ไม่มี raw video, credentials, private host/address, serial หรือข้อมูลส่วนตัวในหลักฐานนี้.
การ merge และการเริ่ม D1/D2 ยังต้องเป็นไปตาม PROJECT_CONTROL; ไม่ปิด Issue อัตโนมัติ.

## SHA256 ของ source ที่ตรวจ

- `tools/ft_data.py`: `dca66f864daac928d22794df53fad1f9c037fc22554da12d136125af250e500e`
- `tests/test_ft_data.py`: `78a5268e97fb4c5b50c4867706c351480b87392ea3d138beafe4243fe454cb4d`
