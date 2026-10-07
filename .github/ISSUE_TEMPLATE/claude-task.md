---
name: งานสำหรับ Claude
about: Codex เตรียม scope; เริ่มพัฒนา local และเผยแพร่ที่ checkpoint
title: "[claude] "
labels: []
---

## เป้าหมายและเกณฑ์เสร็จ
<!-- งานเดียวที่ตรวจรับได้ พร้อมอ้าง PLAN/STATUS/Owner decision -->
- [ ]

## Local baseline และ ownership
- Branch:
- Full HEAD:
- ผู้ถือ tree: Codex เตรียม → Claude พัฒนา → Codex review
- ไฟล์ค้างที่ PO ตรวจแล้ว (allow-dirty):
- ไฟล์ที่แก้ได้ (write-path; รายไฟล์ ไม่มี wildcard):

## Validation
- คำสั่งทดสอบ local/synthetic ที่อนุญาต:
- หลักฐานที่ต้องส่ง: changed files, tests/exit code, blockers, next action

## Checkpoint
<!-- local ก่อน; push เมื่อ reviewable / blocker สำคัญ / handoff ที่ต้องใช้ remote / Owner สั่ง -->
- จังหวะ publish:
- สถานะ: LOCAL_ONLY / SYNC_PENDING / SYNCED หลัง read-back

## ข้อจำกัดและเงื่อนไขหยุด
- ใช้ root/branch เดียวกับ Codex; หนึ่งผู้แก้ไฟล์ ไม่มี auto switch/pull/reset
- ไม่อ่านหรือเผยแพร่ secrets/ข้อมูลกล้อง/พาธเครื่องจริง
- ไม่เพิ่มสิทธิ์/ติดตั้ง/แตะกล้อง/เปิด scheduler/merge/deploy/ปิด Issue เอง
- Default launcher ไม่มี git-write/GitHub tools; PO review แล้วทำ checkpoint
