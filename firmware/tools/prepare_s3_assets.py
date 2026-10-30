#!/usr/bin/env python3
"""Prepare bounded S3 appearance assets from a prepared pack or local video tree.

Logical p4/ paths and p4-h264-v1 describe the shared file format, not chip identity.
The target field and dimensions identify this pack as ESP32-S3. FFmpeg with
libx264 is required. No network access or persistent installation is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import wave

MAX_STREAM = 384 * 1024
SLOT_BYTES = 3 * 1024 * 1024
HEADER_BYTES = 4096


def frame_count(stream):
    nals = re.split(b'\x00\x00\x00?\x01', stream)
    count = 0
    for nal in nals:
        if nal and nal[0] & 31 in (1, 5):
            # first_mb_in_slice=0 is Exp-Golomb 1. Multiple slices can corrupt
            # the tinyh264 decoder because it hands each slice to one frame.
            if len(nal) < 2 or not nal[1] & 0x80:
                raise ValueError('H264 requires one slice per access unit')
            count += 1
    if not count or count > 320:
        raise ValueError('H264 must contain 1..320 frames')
    return count


def minimal_sps(width=240, height=180):
    def ue(value):
        bits=bin(value+1)[2:]
        return '0'*(len(bits)-1)+bits
    cw=(width+15)//16;ch=(height+15)//16
    right=(cw*16-width)//2;bottom=(ch*16-height)//2
    crop=right!=0 or bottom!=0
    bits=ue(0)+ue(0)+ue(2)+ue(1)+'0'+ue(cw-1)+ue(ch-1)+'10'+str(int(crop))
    if crop:bits+=ue(0)+ue(right)+ue(0)+ue(bottom)
    bits+='01';bits+='0'*((-len(bits))%8)
    rbsp=bytes((66,0xc0,30))+int(bits,2).to_bytes(len(bits)//8,'big')
    escaped=bytearray();zeros=0
    for value in rbsp:
        if zeros>=2 and value<=3:escaped.append(3);zeros=0
        escaped.append(value);zeros=zeros+1 if value==0 else 0
    return b'\x67'+bytes(escaped)


def rewrite_sps(stream):
    # Match the runtime's tinyh264 profile. Untrusted runtime streams are also
    # checked against this exact bounded SPS before a decoder is opened.
    parts=re.split(b'(\x00\x00\x00?\x01)',stream)
    found=False
    for i in range(2,len(parts),2):
        if parts[i] and parts[i][0]&31==7:
            parts[i]=minimal_sps();found=True
    if not found:raise ValueError('H264 has no SPS')
    return b''.join(parts)


def validate_bounds(manifest, payload_bytes, slot_bytes=SLOT_BYTES):
    if not 0 < manifest['width'] <= 240 or not 0 < manifest['height'] <= 180:
        raise ValueError('S3 appearance must fit 240x180')
    if not 0 < manifest['fps'] <= 15:
        raise ValueError('S3 appearance must be <=15 fps')
    for family in manifest['families']:
        if not 0 < family['streamBytes'] <= MAX_STREAM:
            raise ValueError('S3 stream exceeds 384 KiB decoder limit: '+family.get('family',''))
        if not 0 < family.get('fps', manifest['fps']) <= 15 or not 0 < family['frames'] <= 320:
            raise ValueError('S3 family timing exceeds bounds')
    if payload_bytes + HEADER_BYTES > slot_bytes:
        raise ValueError(f'S3 appearance payload exceeds flash slot: {payload_bytes}+{HEADER_BYTES}>{slot_bytes}')


def stable_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()


def pack_id(manifest, files):
    digest=hashlib.sha256(b'pet-manager-p4-pack-v1\0')
    identity=stable_json(manifest)
    digest.update(struct.pack('<Q',len(identity)));digest.update(identity)
    for logical,path in sorted(files.items()):
        key=logical.encode();data=path.read_bytes()
        digest.update(struct.pack('<Q',len(key)));digest.update(key)
        digest.update(struct.pack('<Q',len(data)));digest.update(data)
    return digest.hexdigest()


def safe_source(root, name):
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('source path escapes input root')
    if not path.is_file():raise ValueError('missing source: '+str(path))
    if path.read_bytes()[:100].startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError('source is a Git LFS pointer: '+str(path))
    return path


def run(ffmpeg, args):
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y',*map(str,args)],check=True)


def prepare(source, output, ffmpeg, fps=15, slot_bytes=SLOT_BYTES, app_data_dir=None):
    source=Path(source).resolve();output=Path(output).resolve()
    if not 1 <= fps <= 15:raise ValueError('fps must be 1..15')
    if source.is_file():
        source_manifest=json.loads(source.read_text());root=source.parent
    elif (source/'p4/manifest.json').exists():
        source_manifest=json.loads((source/'p4/manifest.json').read_text());root=source
    elif (source/'manifest.json').exists():
        source_manifest=json.loads((source/'manifest.json').read_text());root=source
    else:
        root=source
        source_manifest={'families':[{'family':p.stem,'sourceFile':p.name} for p in sorted(root.glob('*.mp4'))]}
    if app_data_dir is not None:root=Path(app_data_dir).resolve()
    families=[family for family in source_manifest.get('families',[]) if family.get('ok') is not False]
    if not families or len(families)>24:raise ValueError('need 1..24 video families')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='s3-assets-',dir=output.parent) as tmp:
        tmp=Path(tmp);(tmp/'p4/families').mkdir(parents=True)
        manifest={'format':'p4-h264-v1','packId':'','codec':'h264','container':'annex-b',
                  'target':'esp32s3','width':240,'height':180,'fps':fps,'families':[]}
        files={}
        for index,family in enumerate(families):
            name=family.get('family')
            if not isinstance(name,str) or not name or len(name.encode())>=48:raise ValueError('invalid family name')
            filename=next((family[k] for k in ('sourceFile','videoPath','video','source','path') if isinstance(family.get(k),str) and family[k]),None)
            if not filename:raise ValueError('family requires sourceFile, video, source or path')
            src=safe_source(root,filename)
            dst=tmp/f'video-{index}.h264'
            # 240x180 visible pixels, 240x192 coded macroblocks; single reference,
            # constrained baseline and one slice match software decoder bounds.
            input_args=['-r',str(family.get('fps',source_manifest.get('fps',10)))] if src.suffix.lower()=='.h264' else []
            run(ffmpeg,[*input_args,'-i',src,'-an','-vf',f'fps={fps},scale=240:180:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=240:180:(ow-iw)/2:(oh-ih)/2,setsar=1',
                        '-frames:v',str(30*fps+1),'-c:v','libx264','-profile:v','baseline','-level:v','2.0','-pix_fmt','yuv420p',
                        '-preset','medium','-tune','zerolatency','-crf','30','-refs','1','-bf','0','-x264-params','cabac=0:bframes=0:ref=1:weightp=0:scenecut=0:keyint=300:min-keyint=300:repeat-headers=1:aud=1:threads=1:sliced-threads=0',
                        '-f','h264',dst])
            data=rewrite_sps(dst.read_bytes());dst.write_bytes(data);frames=frame_count(data)
            if frames > 30*fps:raise ValueError('S3 appearance video must not exceed 30 seconds; shorten the source explicitly')
            logical='p4/families/sha256-'+hashlib.sha256(data).hexdigest()[:24]+'.h264'
            target=tmp/logical;dst.replace(target);files[logical]=target
            entry={'family':name,'path':logical,'frames':frames,'streamBytes':len(data),'fps':fps,
                   'frameDurationMs':(1000+fps-1)//fps,'durationMs':(frames*1000+fps-1)//fps}
            # Preserve appearance cues; normalized mono PCM matches shared audio.
            audio=family.get('audioPath') or family.get('audioFile')
            if not audio and (root/(name+'.wav')).exists():audio=name+'.wav'
            if audio:
                audio_src=safe_source(root,audio);audio_tmp=tmp/f'audio-{index}.wav'
                run(ffmpeg,['-i',audio_src,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le','-f','wav',audio_tmp])
                with wave.open(str(audio_tmp),'rb') as wav:
                    if wav.getnframes()*wav.getnchannels()*wav.getsampwidth()>1048576:
                        raise ValueError('S3 appearance audio exceeds the runtime 1 MiB PCM limit')
                audio_data=audio_tmp.read_bytes();audio_logical='p4/audio/sha256-'+hashlib.sha256(audio_data).hexdigest()[:24]+'.wav'
                audio_target=tmp/audio_logical;audio_target.parent.mkdir(exist_ok=True);audio_tmp.replace(audio_target)
                files[audio_logical]=audio_target;entry['audioPath']=audio_logical
                entry['audioSource']='default' if family.get('audioSource')=='default' else 'custom'
            manifest['families'].append(entry)
            validate_bounds(manifest,sum(p.stat().st_size+3 for p in files.values()),slot_bytes)
        if source_manifest.get('systemCues'):manifest['systemCues']=True
        manifest['packId']=pack_id(manifest,files)
        (tmp/'p4/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        # Only replace known generated paths; leave unrelated user files intact.
        output.mkdir(parents=True,exist_ok=True)
        shutil.copytree(tmp/'p4',output/'p4',dirs_exist_ok=True)
        return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--ffmpeg',default=os.environ.get('FFMPEG') or shutil.which('ffmpeg'))
    parser.add_argument('--app-data-dir',type=Path,help='Root for custom appearance videoPath/audioPath files')
    parser.add_argument('--fps',type=int,default=15)
    parser.add_argument('--slot-bytes',type=int,default=SLOT_BYTES)
    args=parser.parse_args()
    if not args.ffmpeg:parser.error('FFmpeg with libx264 is required; set --ffmpeg or FFMPEG')
    result=prepare(args.source,args.output,args.ffmpeg,args.fps,args.slot_bytes,args.app_data_dir)
    print(json.dumps({'target':result['target'],'packId':result['packId'],'families':len(result['families']),'output':str(args.output)}))


if __name__=='__main__':main()
