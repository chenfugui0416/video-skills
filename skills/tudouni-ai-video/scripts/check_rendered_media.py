#!/usr/bin/env python3
"""Check the encoded deliverable, including actual early audio activity."""
import argparse, array, hashlib, json, math, subprocess, sys
from pathlib import Path

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('video',type=Path)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--max-onset-ms',type=float,default=250)
    ap.add_argument('--threshold-db',type=float,default=-40)
    args=ap.parse_args(); errors=[]
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(args.video)]))
    streams=info['streams']; video=[s for s in streams if s['codec_type']=='video']; audio=[s for s in streams if s['codec_type']=='audio']
    if not video: errors.append('No video stream')
    if not audio: errors.append('No audio stream')
    decode=subprocess.run(['ffmpeg','-v','error','-i',str(args.video),'-f','null','-'],capture_output=True,text=True)
    if decode.returncode or decode.stderr.strip(): errors.append('Full decode reported errors: '+decode.stderr[-1000:])
    onset=None; peak=None; rms_first=None
    if audio:
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(args.video),'-t','10','-vn','-ac','1','-ar','48000','-f','s16le','-'])
        pcm=array.array('h'); pcm.frombytes(raw)
        if sys.byteorder!='little': pcm.byteswap()
        levels=[]
        for i in range(0,len(pcm),480):
            block=pcm[i:i+480]
            rms=math.sqrt(sum(float(x)*x for x in block)/len(block))/32768 if block else 0
            db=20*math.log10(max(rms,1e-12)); levels.append(db)
            if onset is None and db>=args.threshold_db: onset=round(i/48,3)
        peak=max(levels) if levels else None
        rms_first=levels[:25]
        if onset is None or onset>args.max_onset_ms: errors.append('Early audio activity exceeds onset limit')
    report={'ok':not errors,'file':str(args.video.resolve()),'sha256':digest(args.video),'bytes':args.video.stat().st_size,'duration_seconds':float(info['format']['duration']),'video_streams':len(video),'audio_streams':len(audio),'full_decode_ok':not decode.returncode and not decode.stderr.strip(),'audio_activity':{'analysis_window_seconds':10,'rms_window_ms':10,'threshold_dbfs':args.threshold_db,'max_onset_ms':args.max_onset_ms,'first_activity_ms':onset,'peak_window_dbfs':peak,'first_250ms_window_dbfs':rms_first,'scope':'Encoded PCM activity check; does not establish intelligibility or identify speech.'},'listening_verified':False,'errors':errors}
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('ok','duration_seconds','full_decode_ok','errors')},ensure_ascii=False));print('first_activity_ms='+str(onset));return 0 if report['ok'] else 1
if __name__=='__main__': sys.exit(main())
