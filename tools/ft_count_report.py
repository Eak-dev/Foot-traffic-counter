"""Write an offline review page beside private counting artifacts, no server."""
import html
import json
import os
from pathlib import Path
from tools.ft_count import _open_private, _outside_repo


def write_page(directory, report, evaluation=None, video='annotated.mp4'):
    root=Path(directory)
    _outside_repo(root)
    if video not in ('annotated.mp4','counted-fixed.mp4'):raise ValueError('invalid video name')
    if root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:raise ValueError('private output required')
    rows=[]
    for n,e in enumerate(report['events'],1):
        t=float(e['time_seconds']);direction=html.escape(str(e['direction']))
        rows.append(f'<tr><td>{n}</td><td><button data-time="{t:.2f}">{t:.1f} วินาที</button></td><td>{direction}</td></tr>')
    validation='ยังไม่ได้ตรวจความแม่นยำด้วยการนับมือ'
    if evaluation:
        validation=(f'ตรวจช่วง {evaluation["window_seconds"][0]}–{evaluation["window_seconds"][1]} วินาที: '
                    f'ระบบ {evaluation["predicted_count"]} ครั้ง / นับมือ {evaluation["manual_count"]} ครั้ง; '
                    f'ตรงทั้งเหตุการณ์และทิศทาง {evaluation["true_positive"]} เหตุการณ์ '
                    f'(FP {evaluation["false_positive"]}, FN {evaluation["false_negative"]} เมื่อนับแบบแยกทิศทาง)')
    page='''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; media-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>ผลนับคนจาก Fixed Lens</title><style>body{font-family:system-ui;max-width:1000px;margin:32px auto;padding:0 20px;color:#132c36;background:#edf3f4}h1{font-size:26px}.count{font-size:56px;font-weight:700;color:#13695d}video{width:100%;background:#111;border-radius:12px}.note{background:#fff;padding:20px;border-radius:12px;line-height:1.7}table{width:100%;border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #ccd9dd;text-align:left}button{padding:7px;border:1px solid #b8c9cb;border-radius:6px;background:white;cursor:pointer}</style>
<h1>ผลทดลองนับคนเดินผ่าน · Fixed Lens</h1>'''
    page+=f'<div class="count">{int(report["count"])} ครั้ง</div><p>จำนวนครั้งที่เดินผ่านเส้นในคลิป ไม่ใช่จำนวนบุคคลไม่ซ้ำหรือยอดทั้งวัน</p>'
    page+=f'<video controls preload="metadata" src="{video}"></video><p class="note">{html.escape(validation)}<br>ตรวจโดย PO คนเดียว ผลรวมทั้งคลิปยังไม่ได้ตรวจมือครบทุกเหตุการณ์ ไม่รับรองความแม่นยำทั้งวัน<br>ประมวลผลใน Mac ด้วย YOLOX / ByteTrack ไม่มีการระบุตัวตนหรือจดจำใบหน้า</p>'
    page+='<p>Directions are relative to the configured line. Click a timestamp to review the passage.</p><table><tr><th>Event</th><th>Clip time</th><th>Direction</th></tr>'+''.join(rows)+'</table>'
    page+='''<script>document.querySelectorAll('button[data-time]').forEach(b=>b.onclick=()=>{let v=document.querySelector('video');v.currentTime=Math.max(0,Number(b.dataset.time)-1);v.play()});</script></html>'''
    fd=_open_private(str(root/'review.html'))
    with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(page)
