"""Karaoke-ifier classic single-page interface + pretrained six-stem HTDemucs."""
import os, sys, re, uuid, time, threading, subprocess, shutil, hashlib, json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT=Path(__file__).resolve().parent
JOBS=ROOT/'jobs'; JOBS.mkdir(exist_ok=True)
MAX_BYTES=75*1024*1024
STEM_NAMES=('vocals','drums','bass','guitar','piano','other')
app=FastAPI(title='Karaoke-ifier Classic AI')
app.mount('/jobs', StaticFiles(directory=str(JOBS)), name='jobs')
_state={}; _lock=threading.Lock()

def status(job, **fields):
    with _lock: _state[job].update(fields)

def work(job, source):
    try:
        device='cuda' if _gpu() else 'cpu'
        status(job,stage='Preparing Demucs separation',phase='separating',device=device,progress=None,started_at=time.time())
        output=JOBS/job/'separated'
        cmd=[sys.executable,'-m','demucs','-n','htdemucs_6s','-d',device,'--shifts','0','--overlap','0.1','-o',str(output),str(source)]
        log=JOBS/job/'demucs.log'
        with log.open('w',encoding='utf-8') as stream:
            proc=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT)
            started=time.monotonic()
            while proc.poll() is None:
                elapsed=time.monotonic()-started
                if elapsed>3600:
                    proc.kill()
                    raise RuntimeError('Demucs exceeded the 60-minute time limit. Try a shorter file.')
                # Heartbeat: a running inference does not imply a known percentage.
                status(job,stage='Separating six stems with HTDemucs',phase='separating',elapsed_seconds=round(elapsed),running=True)
                time.sleep(2)
            completed=proc
        status(job,running=False)
        if completed.returncode!=0:
            tail=log.read_text(errors='replace')[-1800:]
            raise RuntimeError('Demucs failed. Check logs: '+tail)
        status(job,stage='Checking six tracks',phase='finalizing',progress=90)
        folder=output/'htdemucs_6s'/source.stem
        wavs={name:folder/(name+'.wav') for name in STEM_NAMES}
        missing=[name for name,p in wavs.items() if not p.exists()]
        if missing: raise RuntimeError('Demucs did not produce: '+', '.join(missing))
        # Lightweight playback copies; the lossless WAVs are preserved for download.
        if shutil.which('ffmpeg') is None: raise RuntimeError('ffmpeg is required for fast browser playback.')
        previews={}
        for idx,(name,wav) in enumerate(wavs.items()):
            mp3=folder/(name+'.mp3')
            status(job,stage=f'Encoding {name} for browser playback ({idx+1}/6)',phase='finalizing',progress=90+idx)
            if not mp3.is_file() or mp3.stat().st_size==0:
                subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-vn','-codec:a','libmp3lame','-b:a','128k','-threads','2',str(mp3)],check=True,timeout=300)
            previews[name]=f'/jobs/{job}/separated/htdemucs_6s/{source.stem}/{name}.mp3'
        result={'stems':previews,'downloads':{name:f'/jobs/{job}/separated/htdemucs_6s/{source.stem}/{name}.wav' for name in STEM_NAMES}}
        (JOBS/job/'result.json').write_text(json.dumps(result))
        status(job,stage='Ready — select instruments and sing live',phase='ready',progress=100,done=True,**result)
    except Exception as exc:
        status(job,done=True,error=str(exc),stage='Separation failed',phase='failed',running=False)

def _gpu():
    try:
        import torch
        return torch.cuda.is_available()
    except Exception: return False

@app.get('/')
def home(): return FileResponse(ROOT/'static'/'index.html',headers={'Cache-Control':'no-store'})

@app.post('/api/separate')
async def separate(audio:UploadFile=File(...)):
    name=Path(audio.filename or 'song.wav').name
    ext=Path(name).suffix.lower()
    if ext not in ('.mp3','.wav','.m4a','.flac','.ogg','.aac'):
        raise HTTPException(400,'Please upload MP3, WAV, M4A, FLAC, OGG, or AAC.')
    # Content-addressed cache: repeated uploads can reuse completed 6-stem results.
    import tempfile
    digest=hashlib.sha256()
    count=0
    with tempfile.NamedTemporaryFile(dir=JOBS,delete=False) as tmp:
        temp_path=Path(tmp.name)
        try:
            while data:=await audio.read(1024*1024):
                count+=len(data)
                if count>MAX_BYTES: raise HTTPException(413,'Maximum upload size: 75 MB.')
                digest.update(data);tmp.write(data)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    if count==0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(400,'Empty audio file.')
    job=digest.hexdigest()[:12]
    folder=JOBS/job;folder.mkdir(exist_ok=True)
    path=folder/('input'+ext)
    cached=folder/'result.json'
    with _lock:
        existing=_state.get(job)
        if existing is not None and not existing.get('error'):
            temp_path.unlink(missing_ok=True)
            return {'job':job,'message':'Using existing processing job.'}
        if cached.exists():
            result=json.loads(cached.read_text())
            _state[job]={'job':job,'done':True,'stage':'Loaded from cache','phase':'ready','progress':100,'device':'cached','elapsed_seconds':0,'running':False,'error':None,**result}
            temp_path.unlink(missing_ok=True)
            return {'job':job,'message':'Previously separated song found in cache.'}
        temp_path.replace(path)
        _state[job]={'job':job,'done':False,'stage':'Queued for separation','progress':None,'phase':'queued','elapsed_seconds':0,'running':False,'device':'checking','stems':{},'downloads':{},'error':None}
    threading.Thread(target=work,args=(job,path),daemon=True).start()
    return {'job':job,'message':'Song uploaded. Starting 6-stem HTDemucs.'}

@app.get('/api/status/{job}')
def get_status(job:str):
    if not re.fullmatch('[0-9a-f]{12}',job): raise HTTPException(404,'Unknown job')
    with _lock:
        info=_state.get(job)
        if info is None: raise HTTPException(404,'Unknown job')
        return dict(info)

@app.get('/api/health')
def health(): return {'ok':True,'gpu':_gpu(),'model':'htdemucs_6s','audio_playback':'mp3 128k','cache':True}

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT','8000')))
