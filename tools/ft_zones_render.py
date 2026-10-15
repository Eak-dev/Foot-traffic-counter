"""Private dual-zone H.264 presentation; inference and counts are never changed."""
import json
import os
import subprocess
import time
from pathlib import Path

from tools import ft_count


def render_review(source, root, zones, reports, deadline):
    """Called only after successful inference inside the caller's network sandbox."""
    import socket
    probe = socket.socket()
    try:
        try:
            probe.bind(('127.0.0.1', 0))
        except PermissionError:
            pass
        else:
            raise ft_count.ValidationError('network sandbox not enforced')
    finally:
        probe.close()
    ft_count._validate_input_file(source)
    ft_count._outside_repo(root)
    root = Path(root)
    ft_count._require(root.stat().st_uid == os.getuid() and not root.stat().st_mode & 0o077, 'private output required')
    from tools.ft_count_zones import merge_reports
    merged = merge_reports(zones, reports)
    ft_count._require(ft_count._file_sha256(source) == merged['input_sha256'], 'source hash mismatch')
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = '/System/Library/Fonts/Supplemental/Tahoma.ttf'
    ft_count._require(Path(font_path).is_file(), 'Thai presentation font unavailable')
    font = ImageFont.truetype(font_path, 24)
    small = ImageFont.truetype(font_path, 16)
    ffmpeg = Path(__file__).resolve().parent.parent / '.venv/ft-media-bin/ffmpeg'
    ft_count._require(ffmpeg.is_file(), 'review encoder unavailable')
    output = root / 'counted-zones.mp4'
    fd = ft_count._open_private(str(output))
    os.close(fd)
    cap = cv2.VideoCapture(str(source))
    logs, proc = [], None
    try:
        ft_count._require(cap.isOpened(), 'source could not be opened')
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        stride = max(1, int(round(fps / merged['sample_fps'])))
        for zone in zones:
            path = root / zone['id'] / 'tracks.jsonl'
            ft_count._outside_repo(path)
            ft_count._require(path.stat().st_size <= ft_count.MAX_TRACKS_JSONL_BYTES, 'track log exceeds cap')
            logs.append(path.open())
        width, height = 1152, 648
        cmd = [str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{width}x{height}', '-r', str(fps / stride), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        emitted = 0
        for frame_index in range(frame_count):
            ft_count._require(time.monotonic() < deadline, 'presentation time budget exceeded')
            if frame_index % stride:
                ft_count._require(cap.grab(), 'source decode incomplete')
                continue
            ok, frame = cap.read()
            ft_count._require(ok, 'source decode incomplete')
            t = frame_index / fps
            canvas = Image.fromarray(cv2.cvtColor(cv2.resize(frame, (width, height)), cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(canvas)
            for zone, report, log in zip(zones, reports, logs):
                line = log.readline(1024 * 1024)
                ft_count._require(bool(line) and line.endswith('\n'), 'track log incomplete')
                row = json.loads(line)
                ft_count._require(row['frame'] == frame_index and abs(row['time_seconds'] - t) < .002, 'track timing mismatch')
                regions = zone['lanes'] if zone.get('counter_mode') == 'lanes' else [{**zone, **zone['config']}]
                for region in regions:
                    color, roi = region['color'], region['roi']
                    points = [(round(x*width), round(y*height)) for x, y in roi]
                    draw.line(points + [points[0]], fill=color, width=3)
                    gate = [(round(x*width), round(y*height)) for x, y in region['line']]
                    if zone.get("counter_mode", "line") in ("line", "lanes"):
                        gate_color = '#FF3030' if zone.get('counter_mode') == 'lanes' else color
                        draw.line(gate, fill=gate_color, width=4)
                    for track in row['tracks']:
                        if ft_count._point_in_polygon(track['foot'], roi):
                            x, y = track['foot'][0]*width, track['foot'][1]*height
                            draw.ellipse((x-3,y-3,x+3,y+3), fill=color)
                    label_x, label_y = points[0]
                    label_y = max(102, label_y-32)
                    box = draw.textbbox((label_x,label_y), region['name'], font=small)
                    draw.rectangle((box[0]-4,box[1]-3,box[2]+4,box[3]+3), fill='#142128')
                    draw.text((label_x,label_y), region['name'], font=small, fill=color)
                if zone.get('track_quality'):
                    for event in report['review_events']:
                        if -.001 <= t - event['time_seconds'] <= 1.2:
                            x, y = event['evidence']['to'][0]*width, event['evidence']['to'][1]*height
                            draw.ellipse((x-12,y-12,x+12,y+12), outline='#FFBB55', width=4)
                            draw.text((x+14,y-20), 'รอตรวจ', font=small, fill='#FFBB55',
                                      stroke_width=2, stroke_fill='#111B22')
            # Panel stays to the right of the camera's timestamp/lens overlay.
            panel_rows = []
            for zone,report in zip(zones,reports):
                count = sum(e['time_seconds'] <= t + 1e-6 for e in report['events'])
                if zone.get('counter_mode') == 'lanes':
                    for lane in zone['lanes']:
                        subtotal = sum(e['time_seconds'] <= t + 1e-6 and e['lane_id'] == lane['id'] for e in report['events'])
                        panel_rows.append((f"{lane['name']}   {subtotal} ครั้ง", lane['color']))
                    caption = 'ผ่านเกณฑ์' if zone.get('track_quality') else 'ข้ามเส้น'
                    panel_rows.append((f"รวมหน้าร้าน ({caption})   {count} ครั้ง", zone['color']))
                    if zone.get('track_quality'):
                        pending = sum(e['time_seconds'] <= t + 1e-6 for e in report['review_events'])
                        panel_rows.append((f"หน้าร้าน รอตรวจ   {pending} จังหวะ", '#FFBB55'))
                else:
                    method = "เข้าโซน" if zone.get("counter_mode") == "entries" else "ข้ามเส้น"
                    panel_rows.append((f"{zone['name']} ({method})   {count} ครั้ง", zone['color']))
            panel_bottom = 38*len(panel_rows)+38
            draw.rectangle((620, 3, 1148, panel_bottom), fill='#111B22')
            for n,(label,color) in enumerate(panel_rows):
                draw.text((636,8+n*38), label, font=font, fill=color)
            draw.text((636,panel_bottom-26), f'PILOT | passages | {t:.1f}s', font=small, fill='white')
            proc.stdin.write(canvas.tobytes())
            emitted += 1
            if emitted % 50 == 0:
                ft_count._require(output.stat().st_size < 150 * 1024 * 1024, 'presentation quota exhausted')
        ft_count._require(emitted == merged['frames_processed'], 'presentation frame count mismatch')
        ft_count._require(all(not log.read(1) for log in logs), 'extra track frames')
        proc.stdin.close()
        ft_count._require(proc.wait(timeout=max(1,min(60,deadline-time.monotonic()))) == 0, 'review encoding failed')
        ft_count._require(0 < output.stat().st_size < 150 * 1024 * 1024, 'presentation quota exhausted')
        output.chmod(0o600)
        return output.name
    except Exception:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()
        output.unlink(missing_ok=True)
        raise
    finally:
        cap.release()
        for log in logs:
            log.close()
