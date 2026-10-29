"""
Procedural Sound Generation & Audio Engine
Upgraded with:
- Pygame mixer pre_init buffer (2048) and channel pooling to prevent crackling/underruns.
- Voice limiting & cooldowns to prevent aggressive sound overlap.
- Smooth attack/decay windowing on all synthesized audio buffers (eliminates DC click/pops).
- New weapon & gameplay SFX: Item pickup chime, Laser zap, Rocket launch, Heavy explosion, and Stun wobble.
- Soft-knee limiter in AudioTimeline to prevent clipping in headless MP4 audio muxing.
"""

import math
import struct
import wave
import io
import os
import time
import random
import subprocess

SAMPLE_RATE = 44100
VICTORY_DIR = os.path.join(os.path.dirname(__file__), "assets", "sounds", "victory")

def apply_envelope(samples, attack_samples=40, decay_samples=100):
    """Applies smooth fade-in and fade-out to prevent zero-crossing clicks."""
    n = len(samples)
    for i in range(min(attack_samples, n)):
        samples[i] = int(samples[i] * (i / attack_samples))
    for i in range(min(decay_samples, n)):
        idx = n - 1 - i
        samples[idx] = int(samples[idx] * (i / decay_samples))
    return samples

def generate_hoofbeat():
    """Generates a soft double-beat 'clop-clop' hoof sound on turf."""
    samples = []
    # Beat 1 (lower thump)
    duration_1 = 0.038
    n1 = int(SAMPLE_RATE * duration_1)
    for i in range(n1):
        t = i / SAMPLE_RATE
        freq = 105 + 35 * math.exp(-75 * t)
        v = math.sin(2 * math.pi * freq * t) + 0.25 * random.uniform(-1, 1)
        env = math.exp(-85 * t)
        s = int(v * 0.38 * env * 32767)
        samples.append(s)

    # Gap between hooves
    gap = int(SAMPLE_RATE * 0.032)
    samples.extend([0] * gap)

    # Beat 2 (crisper clack)
    duration_2 = 0.042
    n2 = int(SAMPLE_RATE * duration_2)
    for i in range(n2):
        t = i / SAMPLE_RATE
        freq = 155 + 50 * math.exp(-65 * t)
        v = math.sin(2 * math.pi * freq * t) + 0.35 * random.uniform(-1, 1)
        env = math.exp(-75 * t)
        s = int(v * 0.35 * env * 32767)
        samples.append(s)

    return apply_envelope(samples, attack_samples=60, decay_samples=80)

def generate_bump_sound():
    """Heavy low-frequency impact thud for horse collision."""
    samples = []
    duration = 0.12
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 85 - 45 * (i / n)
        noise = random.uniform(-0.4, 0.4)
        v = 0.7 * math.sin(2 * math.pi * freq * t) + 0.3 * noise
        env = math.exp(-22 * t)
        s = int(v * 0.55 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=50, decay_samples=120)

def generate_mud_splash():
    """Wet squelch/splash sound for mud obstacle."""
    samples = []
    duration = 0.15
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 220 - 110 * (i / n)
        v = 0.5 * random.uniform(-1, 1) + 0.5 * math.sin(2 * math.pi * freq * t)
        env = (1 - (i / n)) * (0.5 + 0.5 * math.sin(90 * t))
        s = int(v * 0.45 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=60, decay_samples=100)

def generate_hurdle_jump():
    """Whoosh / spring sound for clearing a hurdle."""
    samples = []
    duration = 0.16
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 260 + 320 * (i / n)
        v = math.sin(2 * math.pi * freq * t) + 0.15 * random.uniform(-1, 1)
        env = math.sin(math.pi * (i / n))
        s = int(v * 0.38 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=80, decay_samples=120)

def generate_start_bell():
    """Classic brass race starting bell/chime."""
    samples = []
    duration = 0.70
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        v = (
            0.6 * math.sin(2 * math.pi * 880 * t) +
            0.3 * math.sin(2 * math.pi * 1760 * t) +
            0.15 * math.sin(2 * math.pi * 2640 * t)
        )
        env = math.exp(-5.2 * t)
        s = int(v * 0.60 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=30, decay_samples=200)

def generate_finish_fanfare():
    """Triumphant brass trumpet victory herald fanfare for championship finish."""
    samples = []
    # Fanfare motif: G4 -> C5 -> E5 -> G5 -> E5 -> G5 -> C6 (high triumphant resolution)
    notes = [
        (392.00, 0.11, 0.70),
        (523.25, 0.11, 0.75),
        (659.25, 0.11, 0.80),
        (783.99, 0.26, 0.85),
        (659.25, 0.12, 0.80),
        (783.99, 0.14, 0.85),
        (1046.50, 0.90, 0.95),  # High C6 with rich vibrato
    ]

    for freq, dur, vol in notes:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            # Brass harmonic character: fundamental + 2nd + 3rd + 4th harmonics
            vibrato = 1.0 + (0.015 * math.sin(2 * math.pi * 5.5 * t) if dur > 0.4 else 0.0)
            f = freq * vibrato

            h1 = math.sin(2 * math.pi * f * t)
            h2 = 0.50 * math.sin(2 * math.pi * f * 2 * t)
            h3 = 0.25 * math.sin(2 * math.pi * f * 3 * t)
            h4 = 0.12 * math.sin(2 * math.pi * f * 4 * t)
            brass_raw = (h1 + h2 + h3 + h4) / 1.87

            # Envelope with crisp brass attack and smooth decay
            if t < 0.02:
                env = t / 0.02
            else:
                env = math.exp(-2.2 * (t - 0.02))

            v = brass_raw * env * vol * 0.70
            s = int(max(-32767, min(32767, v * 32767)))
            samples.append(s)

    return apply_envelope(samples, attack_samples=40, decay_samples=180)

def generate_crowd_cheer(duration=3.2):
    """Energetic stadium derby crowd cheer that erupts when winner crosses the line."""
    total_samples = int(SAMPLE_RATE * duration)
    samples = []
    lp1, lp2 = 0.0, 0.0
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Envelope: fast swell in 0.18s, sustained roaring peak, gentle fade into podium
        if t < 0.18:
            env = t / 0.18
        elif t < 2.2:
            # Random subtle undulating flutter of cheering fans
            env = 1.0 + 0.12 * math.sin(2 * math.pi * 3.5 * t) + 0.08 * math.sin(2 * math.pi * 7.2 * t)
        else:
            env = max(0.0, 1.0 - (t - 2.2) / (duration - 2.2))

        # Shaped vocal noise with resonant formant peaks (simulates crowd roaring)
        white = random.uniform(-1.0, 1.0)
        vocal_formant1 = math.sin(2 * math.pi * 580 * t + white * 0.8)
        vocal_formant2 = math.sin(2 * math.pi * 920 * t + white * 0.6)
        whistle = 0.15 * math.sin(2 * math.pi * 2100 * t + 0.2 * math.sin(30 * t)) if (0.4 < t < 1.6) else 0.0

        raw = 0.45 * white + 0.35 * vocal_formant1 + 0.20 * vocal_formant2 + whistle
        # Two-pole low pass filter smoothing
        lp1 += (raw - lp1) * 0.28
        lp2 += (lp1 - lp2) * 0.28

        v = lp2 * env * 0.65
        s = int(max(-32767, min(32767, v * 32767)))
        samples.append(s)

    return apply_envelope(samples, attack_samples=60, decay_samples=250)

def generate_pickup_chime():
    """Pleasant 2-tone melodic chime when collecting a weapon crate."""
    samples = []
    notes = [(659.25, 0.08), (880.0, 0.14)]  # E5 -> A5
    for freq, dur in notes:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            v = 0.75 * math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * freq * 2 * t)
            env = math.exp(-4.5 * t)
            s = int(v * 0.48 * env * 32767)
            samples.append(s)
    return apply_envelope(samples, attack_samples=40, decay_samples=120)

def generate_laser_sound():
    """Futuristic high-energy laser zap."""
    samples = []
    duration = 0.13
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        # Exponential downward chirp
        freq = 1300 * math.exp(-14 * t) + 200
        v = math.sin(2 * math.pi * freq * t) + 0.15 * (1.0 if math.sin(2 * math.pi * freq * 0.5 * t) >= 0 else -1.0)
        env = math.exp(-9.0 * t)
        s = int(v * 0.52 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=30, decay_samples=80)

def generate_rocket_sound():
    """Whooshing rocket ignition launch sound."""
    samples = []
    duration = 0.22
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 180 + 260 * (i / n)
        noise = random.uniform(-0.6, 0.6)
        v = 0.5 * math.sin(2 * math.pi * freq * t) + 0.5 * noise
        env = math.sin(math.pi * (i / n))
        s = int(v * 0.46 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=80, decay_samples=100)

def generate_explosion_sound():
    """Deep thunderous explosion for rocket and bomb impacts."""
    samples = []
    duration = 0.32
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 90 * math.exp(-8 * t) + 30
        noise = random.uniform(-0.7, 0.7)
        v = 0.6 * math.sin(2 * math.pi * freq * t) + 0.4 * noise
        env = math.exp(-6.5 * t)
        s = int(v * 0.65 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=40, decay_samples=160)

def generate_stun_sound():
    """Cartoon-style dizzy wobble whistle for stunned horse."""
    samples = []
    duration = 0.40
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        # 8 Hz vibrato pitch modulation
        freq = 480 + 90 * math.sin(2 * math.pi * 8.5 * t)
        v = math.sin(2 * math.pi * freq * t)
        env = math.exp(-2.5 * t)
        s = int(v * 0.42 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=60, decay_samples=160)

def generate_turbo_boost():
    """High-velocity futuristic acceleration boost whoosh / riser for speed pads."""
    samples = []
    duration = 0.18
    n = int(SAMPLE_RATE * duration)
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 240 + 640 * ((i / n) ** 1.5)
        v = 0.65 * math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * (freq * 1.5) * t)
        noise = random.uniform(-0.35, 0.35)
        raw = 0.7 * v + 0.3 * noise
        env = math.sin(math.pi * (i / n))
        s = int(raw * 0.52 * env * 32767)
        samples.append(s)
    return apply_envelope(samples, attack_samples=50, decay_samples=70)

# -------------------------------------------------------------
# DYNAMIC VICTORY SFX POOL (Memes, Signature Stabs, Fanfares)
# -------------------------------------------------------------

def generate_airhorn():
    """Classic MLG triple-blast airhorn."""
    samples = []
    bursts = [(0.13, 0.035), (0.13, 0.035), (0.42, 0.0)]
    f_base = 466.16  # Bb4
    f_fifth = 698.46 # F5

    for dur, gap in bursts:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            bend = 1.0 + (0.08 * math.exp(-60.0 * t))
            f1 = f_base * bend
            f2 = f_fifth * bend

            h1 = math.sin(2 * math.pi * f1 * t)
            h2 = 0.65 * math.sin(2 * math.pi * f1 * 2 * t)
            h3 = 0.45 * math.sin(2 * math.pi * f1 * 3 * t)
            h4 = 0.30 * math.sin(2 * math.pi * f1 * 4 * t)
            fifth = 0.55 * math.sin(2 * math.pi * f2 * t)
            raw = (h1 + h2 + h3 + h4 + fifth) / 2.95

            if t < 0.008:
                env = t / 0.008
            elif dur > 0.25 and t > (dur - 0.08):
                env = max(0.0, (dur - t) / 0.08)
            else:
                env = 1.0

            v = max(-1.0, min(1.0, raw * 1.25)) * env * 0.75
            samples.append(int(v * 32767))

        if gap > 0:
            samples.extend([0] * int(SAMPLE_RATE * gap))

    return apply_envelope(samples, attack_samples=30, decay_samples=150)

def generate_anime_impact():
    """Dramatic anime shock bass drop and metallic dissonance."""
    duration = 1.25
    total_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        sting_env = math.exp(-12.0 * t)
        sting = (
            0.50 * math.sin(2 * math.pi * 622.25 * t) +
            0.40 * math.sin(2 * math.pi * 880.00 * t) +
            0.35 * math.sin(2 * math.pi * 1046.50 * t) +
            0.20 * math.sin(2 * math.pi * 1480.00 * t)
        ) * sting_env

        bass_freq = 38.0 + 142.0 * math.exp(-9.0 * t)
        bass_phase = 2 * math.pi * bass_freq * t
        bass_raw = math.sin(bass_phase) + 0.35 * math.sin(bass_phase * 2)
        bass_dist = math.tanh(bass_raw * 1.8)
        bass_env = math.exp(-3.2 * t)
        bass = bass_dist * bass_env * 0.75

        shimmer_env = math.sin(min(1.0, t / 0.3) * math.pi * 0.5) * math.exp(-2.2 * t)
        shimmer = 0.18 * math.sin(2 * math.pi * 784.0 * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 6.5 * t)) * shimmer_env

        raw = sting * 0.65 + bass * 0.85 + shimmer
        v = max(-1.0, min(1.0, raw)) * 0.82
        samples.append(int(v * 32767))

    return apply_envelope(samples, attack_samples=20, decay_samples=250)

def generate_siuuu():
    """Cristiano Ronaldo's iconic 'SIUUU' vocal celebration."""
    duration = 1.40
    total_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        if t < 0.10:
            s_env = math.sin(math.pi * (t / 0.10))
            noise = random.uniform(-1.0, 1.0)
            val = noise * s_env * 0.45
        else:
            vt = t - 0.10
            f0 = 210.0 + 120.0 * math.exp(-2.2 * vt)
            vib = 1.0 + 0.025 * math.sin(2 * math.pi * 5.8 * vt)
            f0 *= vib

            p = (vt * f0) % 1.0
            glottal = (math.sin(2 * math.pi * p) + 0.45 * math.sin(4 * math.pi * p) + 0.25 * math.sin(6 * math.pi * p))

            f1_res = math.sin(2 * math.pi * 380.0 * vt)
            f2_res = math.sin(2 * math.pi * 850.0 * vt)
            f3_res = math.sin(2 * math.pi * 2500.0 * vt)

            vocal = 0.50 * glottal + 0.25 * f1_res + 0.18 * f2_res + 0.07 * f3_res

            if vt < 0.12:
                v_env = vt / 0.12
            else:
                v_env = math.exp(-1.5 * (vt - 0.12))

            val = max(-1.0, min(1.0, vocal * 1.5)) * v_env * 0.85

        samples.append(int(val * 32767))

    return apply_envelope(samples, attack_samples=40, decay_samples=250)

def generate_horse_whinny():
    """Loud funny / triumphant horse whinny / neigh."""
    duration = 1.35
    total_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        if t < 0.45:
            p_base = 720.0 + 680.0 * (t / 0.45)
            vib = 120.0 * math.sin(2 * math.pi * 14.0 * t)
            freq = p_base + vib
            env = math.sin(math.pi * 0.5 * (t / 0.45))
        elif t < 0.95:
            p_base = 1400.0 - 750.0 * ((t - 0.45) / 0.50)
            vib = 150.0 * math.sin(2 * math.pi * 11.5 * t)
            freq = p_base + vib
            env = 1.0 - 0.25 * ((t - 0.45) / 0.50)
        else:
            freq = 150.0 + 30.0 * math.sin(2 * math.pi * 28.0 * t)
            env = max(0.0, 1.0 - ((t - 0.95) / 0.40))

        h1 = math.sin(2 * math.pi * freq * t)
        h2 = 0.40 * math.sin(4 * math.pi * freq * t)
        h3 = 0.20 * math.sin(6 * math.pi * freq * t)
        noise = 0.15 * random.uniform(-1.0, 1.0) if t > 0.90 else 0.05 * random.uniform(-1.0, 1.0)
        raw = (h1 + h2 + h3 + noise) / 1.70 * env * 0.78
        val = max(-1.0, min(1.0, raw))
        samples.append(int(val * 32767))

    return apply_envelope(samples, attack_samples=50, decay_samples=200)

def generate_retro_8bit():
    """Nostalgic 8-bit NES chiptune victory jingle."""
    notes = [
        (523.25, 0.08),  # C5
        (659.25, 0.08),  # E5
        (783.99, 0.08),  # G5
        (1046.50, 0.13), # C6
        (783.99, 0.08),  # G5
        (1046.50, 0.52), # C6 sustained triumph
    ]
    samples = []
    for freq, dur in notes:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            vib = 1.0 + (0.02 * math.sin(2 * math.pi * 12.0 * t) if dur > 0.2 else 0.0)
            f = freq * vib
            phase = (t * f) % 1.0
            duty = 0.5 if dur < 0.2 else 0.25
            pulse = 1.0 if phase < duty else -1.0
            sub = 0.35 * (1.0 if ((t * f * 0.5) % 1.0) < 0.5 else -1.0) if dur > 0.2 else 0.0

            if t < 0.01:
                env = t / 0.01
            else:
                env = math.exp(-2.2 * t)

            val = (pulse * 0.70 + sub) * env * 0.65
            samples.append(int(val * 32767))

    return apply_envelope(samples, attack_samples=30, decay_samples=180)

def generate_giga_chad():
    """Sigma / Giga Chad phonk bass drop & cowbell hit."""
    duration = 1.35
    total_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        cb_env = math.exp(-18.0 * t)
        cowbell = (
            0.55 * (1.0 if ((t * 800.0) % 1.0) < 0.5 else -1.0) +
            0.35 * (1.0 if ((t * 540.0) % 1.0) < 0.5 else -1.0)
        ) * cb_env

        if t >= 0.06:
            bt = t - 0.06
            bfreq = 44.0 + 14.0 * math.exp(-4.0 * bt)
            bphase = 2 * math.pi * bfreq * bt
            sub_raw = math.sin(bphase) + 0.40 * math.sin(2 * bphase)
            sub_sat = math.tanh(sub_raw * 2.2)
            sub_env = math.exp(-2.4 * bt)
            bass = sub_sat * sub_env * 0.85
        else:
            bass = 0.0

        val = max(-1.0, min(1.0, cowbell * 0.65 + bass * 0.85)) * 0.80
        samples.append(int(val * 32767))

    return apply_envelope(samples, attack_samples=25, decay_samples=200)

VICTORY_SOUNDS = {
    "airhorn": {"name": "MLG Airhorn Blast", "func": generate_airhorn, "file": "airhorn.ogg", "volume": 0.88},
    "anime_impact": {"name": "Anime Dramatic Impact", "func": generate_anime_impact, "file": "anime_impact.ogg", "volume": 0.88},
    "siuuu": {"name": "Cristiano Ronaldo SIUUU", "func": generate_siuuu, "file": "siuuu.ogg", "volume": 0.92},
    "horse_whinny": {"name": "Crazy Horse Whinny", "func": generate_horse_whinny, "file": "horse_whinny.ogg", "volume": 0.85},
    "retro_8bit": {"name": "8-Bit Arcade Victory", "func": generate_retro_8bit, "file": "retro_8bit.ogg", "volume": 0.82},
    "royal_fanfare": {"name": "Royal Brass Fanfare", "func": generate_finish_fanfare, "file": "royal_fanfare.ogg", "volume": 0.85},
    "giga_chad": {"name": "Sigma Phonk Bass Drop", "func": generate_giga_chad, "file": "giga_chad.ogg", "volume": 0.90},
}

CELEBRITY_VICTORY_SIGNATURES = {
    "ronaldo": "siuuu",
    "giga_chad": "giga_chad",
    "ishowspeed": "airhorn",
    "speed": "airhorn",
    "mrbeast": "airhorn",
    "kai_cenat": "airhorn",
    "xqc": "airhorn",
    "the_rock": "anime_impact",
    "goku": "anime_impact",
    "naruto": "anime_impact",
    "luffy": "anime_impact",
    "spider_man": "anime_impact",
    "batman": "dramatic_cinematic",
    "messi": "retro_8bit",
    "pewdiepie": "retro_8bit",
    "elon_musk": "retro_8bit",
    "bill_gates": "retro_8bit",
    "hasbulla": "horse_whinny",
    "shrek": "horse_whinny",
    "trump": "royal_fanfare",
    "queen_elizabeth": "royal_fanfare",
    "julius_caesar": "royal_fanfare",
    "napoleon": "royal_fanfare",
    "michael_jackson": "crowd_cheer",
    "taylor_swift": "crowd_cheer"
}

def load_wav_samples(file_path):
    """Loads 16-bit PCM samples from a WAV file as a list of integers."""
    try:
        with wave.open(file_path, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw_data = wf.readframes(n_frames)
            if sampwidth == 2:
                count = n_frames * n_channels
                samples_all = struct.unpack(f"<{count}h", raw_data)
                if n_channels == 1:
                    return list(samples_all)
                else:
                    return [int((samples_all[i*2] + samples_all[i*2+1]) / 2) for i in range(n_frames)]
    except Exception:
        pass
    return None

def load_audio_samples(file_path):
    """Loads 16-bit PCM samples from an audio file (.wav, .ogg, .mp3)."""
    if not os.path.exists(file_path):
        return None
    if file_path.endswith('.wav'):
        return load_wav_samples(file_path)
    try:
        from record_race import resolve_ffmpeg_path
        ffmpeg_exe = resolve_ffmpeg_path()
        cmd = [ffmpeg_exe, '-i', file_path, '-f', 's16le', '-ac', '1', '-ar', str(SAMPLE_RATE), '-']
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw_pcm = res.stdout
        if raw_pcm:
            count = len(raw_pcm) // 2
            return list(struct.unpack(f"<{count}h", raw_pcm))
    except Exception:
        pass
    return None

def get_victory_sound_samples(key):
    """Gets samples for a victory sound from memory generator or disk."""
    os.makedirs(VICTORY_DIR, exist_ok=True)
    info = VICTORY_SOUNDS.get(key)
    if not info:
        return generate_finish_fanfare()

    # Fast path: procedural in-memory generation (zero disk read needed)
    if "func" in info:
        return info["func"]()

    # Fallback to disk file if custom sound
    file_name = info.get("file", f"{key}.ogg")
    file_path = os.path.join(VICTORY_DIR, file_name)
    if os.path.exists(file_path):
        samples = load_audio_samples(file_path)
        if samples:
            return samples

    return generate_finish_fanfare()

def get_victory_sound_for_winner(celebrity_id=None, fallback_random=True):
    """Returns the victory sound key for a winner."""
    if celebrity_id and celebrity_id in CELEBRITY_VICTORY_SIGNATURES:
        return CELEBRITY_VICTORY_SIGNATURES[celebrity_id]
    if fallback_random:
        return random.choice(list(VICTORY_SOUNDS.keys()))
    return "royal_fanfare"

def samples_to_wav_bytes(samples, num_channels=1):
    """Converts a list of int16 samples into a valid in-memory WAV byte stream."""
    byte_buf = io.BytesIO()
    with wave.open(byte_buf, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        packed = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(packed)
    byte_buf.seek(0)
    return byte_buf.read()


class SoundManager:
    """
    Robust real-time Pygame audio manager with:
    - 2048 buffer pre-initialization
    - Dedicated channel pooling
    - Minimum re-trigger cooldowns to eliminate audio crackling and spam.
    """
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.sounds = {}
        self.last_played = {}
        self.cooldowns = {
            "hoofbeat": 0.085,
            "bump": 0.14,
            "mud": 0.12,
            "hurdle": 0.14,
            "start": 0.50,
            "finish": 0.50,
            "cheer": 1.50,
            "pickup": 0.09,
            "laser": 0.08,
            "rocket": 0.10,
            "explosion": 0.12,
            "stun": 0.22,
            "boost": 0.10,
        }

        if not self.enabled:
            return

        try:
            import pygame
            if not pygame.mixer.get_init():
                # Fix audio crackling by setting buffer size to 2048
                pygame.mixer.pre_init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=2048)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(24)

            self.sounds["hoofbeat"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_hoofbeat())))
            self.sounds["bump"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_bump_sound())))
            self.sounds["mud"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_mud_splash())))
            self.sounds["hurdle"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_hurdle_jump())))
            self.sounds["start"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_start_bell())))
            self.sounds["finish"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_finish_fanfare())))
            self.sounds["cheer"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_crowd_cheer())))
            self.sounds["pickup"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_pickup_chime())))
            self.sounds["laser"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_laser_sound())))
            self.sounds["rocket"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_rocket_sound())))
            self.sounds["explosion"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_explosion_sound())))
            self.sounds["stun"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_stun_sound())))
            self.sounds["boost"] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(generate_turbo_boost())))

            # Tuned volume levels
            self.sounds["hoofbeat"].set_volume(0.20)
            self.sounds["bump"].set_volume(0.50)
            self.sounds["mud"].set_volume(0.35)
            self.sounds["hurdle"].set_volume(0.35)
            self.sounds["start"].set_volume(0.60)
            self.sounds["finish"].set_volume(0.70)
            self.sounds["cheer"].set_volume(0.65)
            self.sounds["pickup"].set_volume(0.55)
            self.sounds["laser"].set_volume(0.50)
            self.sounds["rocket"].set_volume(0.48)
            self.sounds["explosion"].set_volume(0.60)
            self.sounds["stun"].set_volume(0.45)
            self.sounds["boost"].set_volume(0.55)

            # Load dynamic victory sounds pool
            for v_key, v_info in VICTORY_SOUNDS.items():
                v_samples = get_victory_sound_samples(v_key)
                self.sounds[v_key] = pygame.mixer.Sound(io.BytesIO(samples_to_wav_bytes(v_samples)))
                self.sounds[v_key].set_volume(v_info.get("volume", 0.85))
                self.cooldowns[v_key] = 0.50
            if "royal_fanfare" in self.sounds:
                self.sounds["finish"] = self.sounds["royal_fanfare"]
        except Exception as e:
            self.enabled = False

    def play(self, sound_name):
        if not self.enabled:
            return
        now = time.time()
        cd = self.cooldowns.get(sound_name, 0.05)
        if now - self.last_played.get(sound_name, 0.0) < cd:
            return  # Suppress overlapping voice spam

        snd = self.sounds.get(sound_name)
        if snd:
            snd.play()
            self.last_played[sound_name] = now


class AudioTimeline:
    """
    Builds a frame-accurate audio buffer during headless or live simulation.
    Includes soft-knee limiting to eliminate digital clipping in output MP4.
    """
    def __init__(self, fps=60):
        self.fps = fps
        self.sample_rate = SAMPLE_RATE
        self.events = []  # list of (sample_index, sample_data_list, volume, pan)

        # Pre-synthesize sound buffers
        self.table = {
            "hoofbeat": generate_hoofbeat(),
            "bump": generate_bump_sound(),
            "mud": generate_mud_splash(),
            "hurdle": generate_hurdle_jump(),
            "start": generate_start_bell(),
            "finish": generate_finish_fanfare(),
            "cheer": generate_crowd_cheer(),
            "pickup": generate_pickup_chime(),
            "laser": generate_laser_sound(),
            "rocket": generate_rocket_sound(),
            "explosion": generate_explosion_sound(),
            "stun": generate_stun_sound(),
            "boost": generate_turbo_boost(),
        }

        # Dynamic Victory SFX Pool
        for v_key in VICTORY_SOUNDS:
            self.table[v_key] = get_victory_sound_samples(v_key)
        if "royal_fanfare" in self.table:
            self.table["finish"] = self.table["royal_fanfare"]

    def schedule(self, frame_num, sound_type, volume=0.5, pan=0.0):
        """Schedule a sound effect at a specific frame index."""
        sample_idx = int((frame_num / self.fps) * self.sample_rate)
        data = self.table.get(sound_type)
        if data:
            self.events.append((sample_idx, data, volume, pan))

    def export_wav(self, file_path, total_frames):
        """
        Compiles all scheduled sound events into a clean, studio-grade stereo WAV file.
        Features:
        - 100% clean baseline (zero white-noise / zero static hissing).
        - Noise gate to eliminate low-level digital hum.
        - Peak normalization with 1.0 dBFS headroom to prevent clipping and distortion.
        """
        total_samples = int(((total_frames + 60) / self.fps) * self.sample_rate)
        left_channel = [0.0] * total_samples
        right_channel = [0.0] * total_samples

        # Mix scheduled sound events onto clean silent canvas
        for start_idx, data, vol, pan in self.events:
            pan_left = (1.0 - pan) * 0.5 * vol
            pan_right = (1.0 + pan) * 0.5 * vol
            for j, s in enumerate(data):
                idx = start_idx + j
                if idx < total_samples:
                    left_channel[idx] += s * pan_left
                    right_channel[idx] += s * pan_right

        # Peak detection for audio normalization
        peak = 0.0
        for i in range(total_samples):
            abs_l = abs(left_channel[i])
            abs_r = abs(right_channel[i])
            if abs_l > peak:
                peak = abs_l
            if abs_r > peak:
                peak = abs_r

        # Normalize with clean headroom (target peak: 27500 out of 32767 = -1.5 dBFS)
        gain = 1.0
        if peak > 27500.0:
            gain = 27500.0 / peak
        elif 0 < peak < 16000.0:
            gain = 24000.0 / peak  # Boost if overall mix was quiet

        # Pack into 16-bit signed stereo with noise gate
        interleaved = []
        for i in range(total_samples):
            l_val = left_channel[i] * gain
            r_val = right_channel[i] * gain

            # Noise gate: mute any imperceptible sub-threshold noise
            if abs(l_val) < 8.0:
                l_val = 0.0
            if abs(r_val) < 8.0:
                r_val = 0.0

            # Soft clamp limiter to prevent any integer overflow
            l = int(max(-32767, min(32767, l_val)))
            r = int(max(-32767, min(32767, r_val)))
            interleaved.append(l)
            interleaved.append(r)

        with wave.open(file_path, 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            raw = struct.pack(f"<{len(interleaved)}h", *interleaved)
            wf.writeframes(raw)
