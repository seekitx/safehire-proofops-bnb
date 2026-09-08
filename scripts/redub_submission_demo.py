"""MiniMax stock-voice redub; key comes from stdin and is never persisted.

Only narration text is sent to MiniMax. Existing visuals are retained, with
duration adjusted per scene. Captions use provider or local audio word timestamps.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.data/minimax-redub'
VISUALS = ROOT / '.data/submission-video'
PUBLIC = ROOT / 'apps/web/assets/submission-2026-09-08'
SCENES = [
    ('01-market', "Finding an agent is easy. Knowing what you're actually paying for is harder. That's what SafeHire is built for. Let's walk through the marketplace, then look at a real order the owner has already paid for. We won't make another payment in this video."),
    ('02-categories', "Start with the job you need done: grid calculations, liquidity positions, yield comparison, or lending risk. Each service tells you what it can deliver, and where its limits are. If a provider can't give us a valid signed quote, we don't offer a purchase button."),
    ('03-quote', "Here's the grid calculator. The quoted service fee is zero point five U, plus network fees. The reference price and budget are example inputs supplied by the buyer. Before any payment, SafeHire checks the provider's signature and the exact terms. The wallet stays under the user's control."),
    ('04-paid-order', "Now, the real purchase. This is order five six seven four three, created inside SafeHire on B N B Chain. Each link opens an actual transaction. The owner confirmed every wallet step, including the exact token allowance and escrow funding. After we notified the provider, it submitted the result."),
    ('05-result', "Here's what came back: five buy levels and five sell levels. SafeHire checked the delivered file against its on chain record, then recalculated the prices, quantities, and total allocation. Those checks passed. This is a verified calculation. It does not mean trades were placed, or that the strategy will make money."),
    ('06-followup', "The work doesn't disappear when you close the tab. The server checked this order in the background and sent a delivery alert through Bark. The owner confirmed receiving it on the phone. Asked whether the result was worth the price, the owner said, I feel it is worth it. That's owner feedback, not an independent review."),
    ('07-boundaries', "The result has been submitted, but final settlement is still pending. We keep that distinction visible. We also show where the marketplace needs more work: reliable supply across all four categories, independent alternatives, and stronger human comparisons. You can explore the live product, inspect the raw evidence, and review the code using the links below."),
]
_aligner: Any = None


def probe(path: Path) -> float:
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'csv=p=0', str(path)], text=True))


def stamp(ms: int, separator: str = ',') -> str:
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}{separator}{ms % 1000:03}'


def fetch_json(url: str, payload: dict[str, Any] | None = None,
               key: str | None = None) -> Any:
    """Use system curl TLS trust; credentials travel only on stdin, never argv."""
    if not url.startswith('https://'):
        raise ValueError('HTTPS is required')
    def quoted(value: str) -> str:
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'
    lines = ['url = ' + quoted(url)]
    if key:
        lines.append('header = ' + quoted('Authorization: Bearer ' + key))
    if payload is not None:
        lines.extend(['header = "Content-Type: application/json"',
                      'data = ' + quoted(json.dumps(payload))])
    result = subprocess.run(['curl', '-q', '--fail', '--silent', '--show-error',
                             '--connect-timeout', '8', '--max-time', '90' if payload else '10', '--config', '-'],
                            input='\n'.join(lines), text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f'MiniMax transport failed (curl code {result.returncode}); credentials omitted')
    return json.loads(result.stdout)


def align_audio(audio: Path, text: str) -> list[dict[str, Any]]:
    """Fallback: align authored captions to local ASR word timestamps, not guessed scene durations."""
    global _aligner
    if _aligner is None:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
        _aligner = WhisperModel('base', device='cpu', compute_type='int8', cpu_threads=4,
                                local_files_only=True)
    segments, _ = _aligner.transcribe(str(audio), language='en', beam_size=5,
                     word_timestamps=True, condition_on_previous_text=False)
    spoken = [w for segment in segments for w in (segment.words or [])]
    original = list(re.finditer(r'\S+', text))
    def normalize(value: str) -> str:
        return re.sub(r'[^a-z0-9]', '', value.lower())
    wanted = [normalize(m.group()) for m in original]
    heard = [normalize(w.word) for w in spoken]
    matcher = SequenceMatcher(a=wanted, b=heard, autojunk=False)
    if matcher.ratio() < .72:
        raise ValueError('Generated speech differs too much from intended narration')
    timed: list[dict[str, Any]] = []
    edits = []
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == 'equal':
            intervals = [(w.start, w.end) for w in spoken[c:d]]
        elif a == b:
            edits.append({'kind': tag, 'recognized': heard[c:d]})
            continue
        else:
            lo = spoken[c].start if c < len(spoken) else spoken[-1].end
            hi = spoken[d - 1].end if d > c else lo + .12
            intervals = [(lo + (hi-lo)*i/(b-a), lo + (hi-lo)*(i+1)/(b-a)) for i in range(b-a)]
            edits.append({'kind': tag, 'intended': wanted[a:b], 'recognized': heard[c:d]})
        for token, (start, end) in zip(original[a:b], intervals, strict=True):
            timed.append({'word': text[token.start():token.end()], 'word_begin': token.start(),
                          'word_end': token.end(), 'time_begin': round(start*1000), 'time_end': round(end*1000)})
    (WORK / (audio.stem + '-alignment-check.json')).write_text(json.dumps({
        'origin': 'local faster-whisper base word timestamps aligned to authored text',
        'match_ratio': matcher.ratio(), 'recognized_transcript': ' '.join(w.word.strip() for w in spoken),
        'edits': edits, 'not_provider_timestamps': True}, indent=2))
    # Match the common timing schema while explicitly preserving origin metadata.
    for i in range(len(timed)-1):
        timed[i]['word'] = text[timed[i]['word_begin']:timed[i+1]['word_begin']]
    return [{'text': text, 'text_begin': 0, 'timestamped_words': timed,
             'timing_origin': 'local_asr_alignment'}]


def captions(timing: list[dict[str, Any]], offset: float) -> list[dict[str, Any]]:
    result = []
    for segment in timing:
        words = segment.get('timestamped_words', [])
        if not words:
            raise ValueError('MiniMax did not return word timestamps')
        source = segment['text']
        matches = list(re.finditer(r'\S+', source))
        base = segment.get('text_begin', 0)
        if ''.join(w['word'] for w in words).strip() != source.strip():
            raise ValueError('Provider subtitle text mismatch')
        # Short, timed phrases; never a full paragraph over the picture.
        for i in range(0, len(matches), 7):
            group = matches[i:i + 7]
            start, end = group[0].start() + base, group[-1].end() + base
            selected = [w for w in words if w['word_end'] > start and w['word_begin'] < end]
            if not selected:
                raise ValueError('Missing timing for subtitle phrase')
            result.append({'text': source[group[0].start():group[-1].end()],
                           'startMs': round(offset * 1000 + selected[0]['time_begin']),
                           'endMs': round(offset * 1000 + selected[-1]['time_end']),
                           'timestampMs': None, 'confidence': None})
    return result


def main() -> None:
    key = sys.stdin.readline().strip()
    if not key:
        raise ValueError('MiniMax key must be supplied on stdin')
    WORK.mkdir(parents=True, exist_ok=True)
    all_cues, audit, parts = [], [], []
    elapsed = 0.0
    for name, text in SCENES:
        audio, subs = WORK / f'{name}.mp3', WORK / f'{name}-words.json'
        text_path = WORK / f'{name}-source.txt'
        response_cache = WORK / f'{name}-response.json'
        if not (audio.exists() and subs.exists() and text_path.exists() and text_path.read_text() == text):
            payload = {'model': 'speech-2.8-hd', 'text': text, 'stream': False,
                       'language_boost': 'English', 'output_format': 'hex',
                       'voice_setting': {'voice_id': 'English_expressive_narrator',
                                         'speed': 0.98, 'vol': 1, 'pitch': 0},
                       'audio_setting': {'sample_rate': 32000, 'bitrate': 128000,
                                         'format': 'mp3', 'channel': 1},
                       'subtitle_enable': True, 'subtitle_type': 'word'}
            print(f'Requesting MiniMax narration for {name}', flush=True)
            if response_cache.exists() and text_path.exists() and text_path.read_text() == text:
                data = json.loads(response_cache.read_text())
            else:
                data = fetch_json('https://api.minimaxi.com/v1/t2a_v2', payload, key)
                response_cache.write_text(json.dumps(data))
                text_path.write_text(text)
            if data.get('base_resp', {}).get('status_code') != 0:
                raise RuntimeError('MiniMax rejected request: code ' + str(data.get('base_resp', {}).get('status_code')))
            audio.write_bytes(bytes.fromhex(data['data']['audio']))
            print(f'{name}: audio saved; fetching word timestamps', flush=True)
            try:
                timing = fetch_json(data['data']['subtitle_file'])
            except RuntimeError:
                print(f'{name}: subtitle CDN unavailable; aligning the saved audio locally', flush=True)
                timing = align_audio(audio, text)
            subs.write_text(json.dumps(timing, ensure_ascii=False, indent=2))
            text_path.write_text(text)
        timing = json.loads(subs.read_text())
        audio_length = probe(audio)
        local_cues = captions(timing, 0)
        if max(c['endMs'] for c in local_cues) > audio_length * 1000 + 150:
            raise ValueError('Captions extend beyond audio')
        all_cues.extend(captions(timing, elapsed))
        duration = round((audio_length + 0.6) * 25) / 25
        source = VISUALS / f'{name}.mp4'
        old_duration = probe(source)
        part = WORK / f'{name}-redub.mp4'
        # Remove old static caption band; keep all original webpage pixels.
        subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                        '-i', str(source), '-i', str(audio), '-t', str(duration),
                        '-filter_complex', f'[0:v]crop=1440:960:0:0,setpts={duration / old_duration}*PTS,pad=1440:1080:0:0:color=0x142c27[v];[1:a]apad[a]',
                        '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast',
                        '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '25', '-c:a', 'aac',
                        '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(part)], check=True)
        parts.append(part)
        audit.append({'scene': name, 'text': text, 'start_seconds': elapsed,
                      'audio_seconds': audio_length, 'scene_seconds': duration,
                      'caption_phrases': len(local_cues), 'audio_speed_adjustment': 1.0,
                      'visual_speed_factor': duration / old_duration})
        elapsed += duration
        print(f'{name}: voice and {len(local_cues)} synchronized phrases prepared', flush=True)
    key = None
    for a, b in pairwise(all_cues):
        if a['endMs'] > b['startMs'] + 5:
            raise ValueError('Overlapping captions')
    (WORK / 'captions.json').write_text(json.dumps(all_cues, ensure_ascii=False, indent=2))
    srt = WORK / 'safehire-demo.en.srt'
    srt.write_text('\n\n'.join(f"{i+1}\n{stamp(c['startMs'])} --> {stamp(c['endMs'])}\n{c['text']}" for i, c in enumerate(all_cues)) + '\n')
    vtt = WORK / 'safehire-demo.en.vtt'
    vtt.write_text('WEBVTT\n\n' + '\n\n'.join(f"{stamp(c['startMs'], '.')} --> {stamp(c['endMs'], '.')}\n{c['text']}" for c in all_cues) + '\n')
    concat = WORK / 'concat.txt'
    concat.write_text(''.join("file '" + str(p) + "'\n" for p in parts))
    final = WORK / 'safehire-demo.mp4'
    style = 'FontName=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00272C14,Outline=0.7,Shadow=0,Alignment=2,MarginV=8,MarginL=20,MarginR=20'
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat',
                    '-safe', '0', '-i', str(concat), '-vf', f"subtitles={srt}:force_style='{style}'",
                    '-af', 'loudnorm=I=-16:TP=-1.5:LRA=9', '-c:v', 'libx264', '-preset',
                    'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '25', '-c:a',
                    'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(final)], check=True)
    manifest = {'version': 'minimax-redub-2026-09-08', 'voice_model': 'speech-2.8-hd',
                'voice_id': 'English_expressive_narrator', 'voice_type': 'stock synthetic voice',
                'caption_alignment': 'Word timestamps: MiniMax when available, otherwise local ASR aligned to authored text; original audio speed retained. Per-scene alignment checks identify fallback.',
                'caption_count': len(all_cues), 'duration_seconds': probe(final),
                'sha256': hashlib.sha256(final.read_bytes()).hexdigest(), 'scenes': audit,
                'content_changes': 'Narration delivery and wording only; original business scope and evidence boundaries retained',
                'credential_saved': False, 'human_listening_review': 'pending'}
    (WORK / 'redub-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('MiniMax video complete:', round(probe(final), 2), 'seconds', flush=True)


if __name__ == '__main__':
    main()
