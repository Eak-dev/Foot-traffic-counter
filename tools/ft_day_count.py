"""Persistent local counting worker; counters/trackers survive adjacent files.

Only ``--worker`` imports image/inference libraries, inside a deny-network
sandbox. The parent may acquire files; this worker has no credentials.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

from tools import ft_count as f
from tools.ft_count_zones import load_zones_config, _zone_config_sha, _config_sha256
from tools.ft_lane_counter import LaneCrossingCounter
from tools.ft_track_quality import TrackEvidence
from tools.ft_zone_entries import ZoneEntryCounter

VERSION='day_stream_v1'


def config_digest(config):
    return _config_sha256(dict(engine=VERSION,config=config,
                               policies=[_zone_config_sha(z) for z in config['zones']]))


class ObservationStream:
    """Pure anonymous observation state, shared across contiguous files."""
    def __init__(self,zones):
        self.zones={z['id']:z for z in zones};self.reset()

    def reset(self,origin=0):
        self.counters={};self.quality={};self.origin=origin
        for zid,z in self.zones.items():
            cfg=z['config'];mode=z.get('counter_mode','line');db=cfg.get('deadband',f.DEFAULT_DEADBAND)
            self.counters[zid]=(LaneCrossingCounter(z['lanes'],db) if mode=='lanes' else
                                ZoneEntryCounter(cfg['roi'],db) if mode=='entries' else
                                f.CrossingCounter(cfg['line'],cfg['roi'],db))
            if z.get('track_quality'):self.quality[zid]=TrackEvidence()

    def update(self,zid,track_id,point,t,box,source_ref):
        counter=self.counters[zid];quality=self.quality.get(zid)
        local_time=round(t-self.origin,3)
        if quality:quality.observe(track_id,point,local_time,box)
        counter.update(track_id,point,local_time)
        result=[]
        for event in counter.events:
            reasons=quality.assess(event)['reasons'] if quality else []
            item=dict(at=round(self.origin+event['time_seconds'],3),zone=zid,lane=event.get('lane_id'),
                      status='review' if reasons else 'accepted')
            item['ref']=_config_sha256(dict(source=source_ref,zone=zid,event=event))
            if reasons:item['review_reasons']=reasons
            result.append(item)
        counter.events.clear()  # motion state/cooldowns remain; no growing frame history
        return result


class FrameClock:
    """One absolute day-second ownership clock for overlapping source footage."""
    def __init__(self):self.last=-math.inf;self.end=-math.inf;self.owned_begin=-math.inf
    def begin(self,start,end,reset):
        f._require(type(start) is int and type(end) is int and -180<=start<end<=86580 and end-start<=180,
                   'invalid source clock')
        f._require(type(reset) is bool,'reset flag required')
        f._require(reset or math.isfinite(self.end) and start<=self.end+.001,'gap requires new tracking group')
        if reset:self.last=-math.inf;self.end=-math.inf
        self.owned_begin=max(start,self.end)
        self.end=max(self.end,end)
    def accept(self,t):
        f._require(type(t) in (int,float) and math.isfinite(t) and -180<=t<86580,'invalid frame clock')
        if t<self.owned_begin or t<=self.last+.001:return False
        self.last=t;return True


class Engine:
    def __init__(self,root,config,model,reference):
        import cv2
        import numpy as np
        import supervision as sv
        import onnxruntime as ort
        self.cv,self.np,self.sv=cv2,np,sv;cv2.setNumThreads(4)
        self.root=Path(root).resolve();self.config=config;self.clock=FrameClock()
        self.stream=ObservationStream(config['zones']);self.trackers={}
        f._validate_model_file(model)
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        self.net=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
        self.input_name=self.net.get_inputs()[0].name
        f._validate_input_file(reference)
        cap=cv2.VideoCapture(str(reference));ok,image=cap.read();cap.release()
        f._require(ok,'reference lens frame unavailable')
        self.reference=image;self.orb=cv2.ORB_create(nfeatures=1000)
        self.ref_k,self.ref_d=self.orb.detectAndCompute(self._ceiling(image),None)
        f._require(self.ref_d is not None and len(self.ref_k)>=30,'static lens reference insufficient')

    def _ceiling(self,image):
        # Static ceiling/beam strip; excludes shop/customer areas and image OSD.
        cv=self.cv;small=cv.resize(image,(960,540));return cv.cvtColor(small[55:150,30:920],cv.COLOR_BGR2GRAY)

    def verify_lens(self,image):
        cv=self.cv;keys,desc=self.orb.detectAndCompute(self._ceiling(image),None)
        if desc is None:return False
        pairs=cv.BFMatcher(cv.NORM_HAMMING).knnMatch(self.ref_d,desc,k=2)
        good=[m for pair in pairs if len(pair)==2 for m,n in [pair] if m.distance<.7*n.distance]
        if len(good)<20:return False
        a=self.np.float32([self.ref_k[m.queryIdx].pt for m in good]);b=self.np.float32([keys[m.trainIdx].pt for m in good])
        matrix,mask=cv.estimateAffinePartial2D(a,b,method=cv.RANSAC,ransacReprojThreshold=3)
        return bool(matrix is not None and mask is not None and mask.sum()>=20 and mask.mean()>=.6
                    and abs(matrix[0,0]-1)<.08 and abs(matrix[1,1]-1)<.08
                    and abs(matrix[0,1])<.05 and abs(matrix[1,0])<.05
                    and abs(matrix[0,2])<12 and abs(matrix[1,2])<12)

    def reset(self,origin):
        self.stream.reset(origin);self.trackers={}
        for z in self.config['zones']:
            self.trackers[z['id']]=self.sv.ByteTrack(track_activation_threshold=z['config'].get('confidence',f.DEFAULT_CONFIDENCE),
                lost_track_buffer=90,minimum_matching_threshold=.99,
                frame_rate=int(round(z['config'].get('sample_fps',5))),minimum_consecutive_frames=1)

    def detect(self,image,cfg):
        cv,np=self.cv,self.np;h,w=image.shape[:2];crop=cfg.get('crop',[0,0,1,1])
        x,y,x2,y2=int(crop[0]*w),int(crop[1]*h),int(crop[2]*w),int(crop[3]*h)
        rgb=cv.cvtColor(image[y:y2,x:x2],cv.COLOR_BGR2RGB);canvas,scale=f._letterbox(cv,np,rgb)
        blob=canvas.transpose(2,0,1)[np.newaxis,...].astype(np.float32)
        boxes,scores=f._decode_yolox(np,self.net.run(None,{self.input_name:blob})[0],scale)
        boxes[:,[0,2]]+=x;boxes[:,[1,3]]+=y
        if len(boxes):
            boxes[:,[0,2]]=np.clip(boxes[:,[0,2]],0,w);boxes[:,[1,3]]=np.clip(boxes[:,[1,3]],0,h)
            ids=cv.dnn.NMSBoxes(np.column_stack((boxes[:,:2],boxes[:,2:]-boxes[:,:2])).tolist(),scores.tolist(),f.DET_SCORE_FLOOR,f.NMS_IOU)
            ids=np.array(ids).reshape(-1) if len(ids) else np.array([],dtype=int);boxes,scores=boxes[ids],scores[ids]
        return self.sv.Detections(xyxy=boxes.astype(np.float32),confidence=scores.astype(np.float32),class_id=np.zeros(len(boxes),dtype=int))

    def process(self,message):
        f._require(isinstance(message,dict) and set(message)=={'start','end','reset','source_ref','input_sha256'},'invalid worker message')
        for key in ('source_ref','input_sha256'):
            f._require(isinstance(message[key],str) and len(message[key])==64 and all(c in '0123456789abcdef' for c in message[key]),'invalid source digest')
        path=self.root/'work'/'fixed.mp4';f._validate_input_file(path)
        f._require(f._file_sha256(path)==message['input_sha256'],'source hash mismatch')
        cap=self.cv.VideoCapture(str(path));events=[];frames=0;deadline=time.monotonic()+2400
        try:
            ok,first=cap.read();f._require(ok and self.verify_lens(first),'Fixed Lens ceiling verification failed')
            fps=cap.get(self.cv.CAP_PROP_FPS);count=int(cap.get(self.cv.CAP_PROP_FRAME_COUNT))
            duration=count/fps if fps>0 else 0
            f._require(.1<fps<=120 and count>0 and abs(duration-(message['end']-message['start']))<=2,
                       'source duration does not match SD interval')
            rates={z['config'].get('sample_fps',5) for z in self.config['zones']};f._require(len(rates)==1,'sample rate mismatch')
            stride=max(1,int(round(fps/next(iter(rates)))))
            self.clock.begin(message['start'],message['end'],message['reset'])
            if message['reset']:self.reset(message['start'])
            for index in range(count):
                f._require(time.monotonic()<deadline,'counting clip deadline exceeded')
                if index%stride:
                    f._require(cap.grab(),'source decode incomplete');continue
                if index==0:ok,image=True,first
                else:ok,image=cap.read()
                f._require(ok,'source decode incomplete')
                t=message['start']+round(index/fps,3)
                if t>=message['end'] or not self.clock.accept(t):continue
                h,w=image.shape[:2]
                for z in self.config['zones']:
                    tracked=self.trackers[z['id']].update_with_detections(self.detect(image,z['config']))
                    for i in range(len(tracked)):
                        if tracked.tracker_id[i] is None:continue
                        b=tracked.xyxy[i];box=[round(float(v),4) for v in (b[0]/w,b[1]/h,b[2]/w,b[3]/h)]
                        point=[round(float((b[0]+b[2])/2/w),4),round(float(((b[1]+b[3])/2 if z['config'].get('anchor')=='center' else b[3])/h),4)]
                        events.extend(self.stream.update(z['id'],int(tracked.tracker_id[i]),point,t,box,message['source_ref']))
                frames+=1
                f._require(len(events)<=10000,'per-clip event quota exceeded')
            events=[e for e in events if 0<=e['at']<86400]
            return dict(status='ok',frames=frames,events=events,lens_verified=True,clock_verified=True,
                        input_sha256=message['input_sha256'],config_sha256=config_digest(self.config))
        finally:cap.release()


def worker_main(root,config,model,reference):
    probe=socket.socket()
    try:
        try:probe.bind(('127.0.0.1',0))
        except PermissionError:pass
        else:raise f.ValidationError('network sandbox not enforced')
    finally:probe.close()
    os.umask(0o077);os.environ['MPLCONFIGDIR']=str(Path(root)/'cache')
    f._outside_repo(root);s=Path(root).lstat();f._require(s.st_uid==os.getuid() and not s.st_mode&0o077,'private worker root required')
    engine=Engine(root,load_zones_config(config),model,reference)
    print(json.dumps(dict(status='ready',config_sha256=config_digest(engine.config))),flush=True)
    while True:
        line=sys.stdin.readline(16385)
        if not line:break
        try:
            f._require(len(line)<=16384,'worker message too large')
            result=engine.process(json.loads(line))
        except Exception:
            print(json.dumps(dict(status='blocked',reason='COUNT_OR_SOURCE_VALIDATION_FAILED')),flush=True)
            return 2  # cannot continue with potentially partial tracker state
        print(json.dumps(result,allow_nan=False),flush=True)
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--root',required=True)
    parser.add_argument('--config',required=True);parser.add_argument('--model',required=True);parser.add_argument('--reference',required=True)
    args=parser.parse_args()
    try:sys.exit(worker_main(args.root,args.config,args.model,args.reference))
    except Exception:print('{"status":"blocked","reason":"WORKER_START_FAILED"}',flush=True);sys.exit(2)
