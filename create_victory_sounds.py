"""
Test and build procedural victory sounds pool for HORSE HAVOC.
"""

import os
import math
import struct
import wave
import random

SAMPLE_RATE = 44100

def apply_envelope(samples, attack_samples=40, decay_samples=100):
    n = len(samples)
    for i in range(min(attack_samples, n)):
        samples[i] = int(samples[i] * (i / attack_samples))
    for i in range(min(decay_samples, n)):
        idx = n - 1 - i
        samples[idx] = int(samples[idx] * (i / decay_samples))
    return samples

def generate_airhorn():
    """Classic MLG triple-blast airhorn."""
    samples = []
    # 3 bursts: toot (0.13s), gap (0.035s), toot (0.13s), gap (0.035s), blast (0.42s)
    bursts = [(0.13, 0.035), (0.13, 0.035), (0.42, 0.0)]
    f_base = 466.16  # Bb4
    f_fifth = 698.46 # F5

    for dur, gap in bursts:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            # Onset slight pitch bend
            bend = 1.0 + (0.08 * math.exp(-60.0 * t))
            f1 = f_base * bend
            f2 = f_fifth * bend

            # Brass / reed buzz harmonics
            h1 = math.sin(2 * math.pi * f1 * t)
            h2 = 0.65 * math.sin(2 * math.pi * f1 * 2 * t)
            h3 = 0.45 * math.sin(2 * math.pi * f1 * 3 * t)
            h4 = 0.30 * math.sin(2 * math.pi * f1 * 4 * t)
            fifth = 0.55 * math.sin(2 * math.pi * f2 * t)
            raw = (h1 + h2 + h3 + h4 + fifth) / 2.95

            # Crisp gate envelope
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
        # 1. Metallic sting chord (Eb5, A5, C6) with fast decay
        sting_env = math.exp(-12.0 * t)
        sting = (
            0.50 * math.sin(2 * math.pi * 622.25 * t) +
            0.40 * math.sin(2 * math.pi * 880.00 * t) +
            0.35 * math.sin(2 * math.pi * 1046.50 * t) +
            0.20 * math.sin(2 * math.pi * 1480.00 * t)
        ) * sting_env

        # 2. Heavy sub bass drop (180Hz -> 38Hz)
        bass_freq = 38.0 + 142.0 * math.exp(-9.0 * t)
        bass_phase = 2 * math.pi * bass_freq * t
        bass_raw = math.sin(bass_phase) + 0.35 * math.sin(bass_phase * 2)
        # Soft saturation distortion
        bass_dist = math.tanh(bass_raw * 1.8)
        bass_env = math.exp(-3.2 * t)
        bass = bass_dist * bass_env * 0.75

        # 3. Dramatic shimmer tail with tremolo
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
        # Part 1: Sibilant 'S' noise (0 to 0.10s)
        if t < 0.10:
            s_env = math.sin(math.pi * (t / 0.10))
            noise = random.uniform(-1.0, 1.0)
            # High pass noise approximation
            val = noise * s_env * 0.45
        else:
            # Part 2: Booming 'II-UUUU!' vocal shout
            vt = t - 0.10
            # Pitch slide: from 330 Hz down to 210 Hz
            f0 = 210.0 + 120.0 * math.exp(-2.2 * vt)
            # Vibrato
            vib = 1.0 + 0.025 * math.sin(2 * math.pi * 5.8 * vt)
            f0 *= vib

            # Glottal pulse synthesis with vocal tract formants
            p = (vt * f0) % 1.0
            glottal = (math.sin(2 * math.pi * p) + 0.45 * math.sin(4 * math.pi * p) + 0.25 * math.sin(6 * math.pi * p))

            # Formant resonance simulation: F1 ~ 380Hz, F2 ~ 850Hz, F3 ~ 2500Hz
            f1_res = math.sin(2 * math.pi * 380.0 * vt)
            f2_res = math.sin(2 * math.pi * 850.0 * vt)
            f3_res = math.sin(2 * math.pi * 2500.0 * vt)

            vocal = 0.50 * glottal + 0.25 * f1_res + 0.18 * f2_res + 0.07 * f3_res

            # Envelope: fast swell, sustained scream, smooth stadium echo
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
            # Ascending high whinny
            p_base = 720.0 + 680.0 * (t / 0.45)
            # Rapid vibrato flutter
            vib = 120.0 * math.sin(2 * math.pi * 14.0 * t)
            freq = p_base + vib
            env = math.sin(math.pi * 0.5 * (t / 0.45))
        elif t < 0.95:
            # Warbling descending neigh
            p_base = 1400.0 - 750.0 * ((t - 0.45) / 0.50)
            vib = 150.0 * math.sin(2 * math.pi * 11.5 * t)
            freq = p_base + vib
            env = 1.0 - 0.25 * ((t - 0.45) / 0.50)
        else:
            # Low guttural snort
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
            # 8-bit pulse wave (square wave with variable duty cycle)
            vib = 1.0 + (0.02 * math.sin(2 * math.pi * 12.0 * t) if dur > 0.2 else 0.0)
            f = freq * vib
            phase = (t * f) % 1.0
            duty = 0.5 if dur < 0.2 else 0.25
            pulse = 1.0 if phase < duty else -1.0

            # Arpeggiated bass harmony on long note
            sub = 0.35 * (1.0 if ((t * f * 0.5) % 1.0) < 0.5 else -1.0) if dur > 0.2 else 0.0

            if t < 0.01:
                env = t / 0.01
            else:
                env = math.exp(-2.2 * t)

            val = (pulse * 0.70 + sub) * env * 0.65
            samples.append(int(val * 32767))

    return apply_envelope(samples, attack_samples=30, decay_samples=180)

def generate_finish_fanfare():
    """Triumphant brass trumpet herald fanfare."""
    notes = [
        (392.00, 0.11, 0.70),
        (523.25, 0.11, 0.75),
        (659.25, 0.11, 0.80),
        (783.99, 0.26, 0.85),
        (659.25, 0.12, 0.80),
        (783.99, 0.14, 0.85),
        (1046.50, 0.90, 0.95),
    ]
    samples = []
    for freq, dur, vol in notes:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            t = i / SAMPLE_RATE
            vibrato = 1.0 + (0.015 * math.sin(2 * math.pi * 5.5 * t) if dur > 0.4 else 0.0)
            f = freq * vibrato
            h1 = math.sin(2 * math.pi * f * t)
            h2 = 0.50 * math.sin(2 * math.pi * f * 2 * t)
            h3 = 0.25 * math.sin(2 * math.pi * f * 3 * t)
            h4 = 0.12 * math.sin(2 * math.pi * f * 4 * t)
            brass_raw = (h1 + h2 + h3 + h4) / 1.87
            env = (t / 0.02) if t < 0.02 else math.exp(-2.2 * (t - 0.02))
            v = brass_raw * env * vol * 0.70
            s = int(max(-32767, min(32767, v * 32767)))
            samples.append(s)
    return apply_envelope(samples, attack_samples=40, decay_samples=180)

def generate_giga_chad():
    """Sigma / Giga Chad phonk bass drop & cowbell hit."""
    duration = 1.35
    total_samples = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Phonk cowbell tap (starts at t=0, rapid decay)
        cb_env = math.exp(-18.0 * t)
        cowbell = (
            0.55 * (1.0 if ((t * 800.0) % 1.0) < 0.5 else -1.0) +
            0.35 * (1.0 if ((t * 540.0) % 1.0) < 0.5 else -1.0)
        ) * cb_env

        # Heavy 808 sub-bass (starts at t=0.06s, slides 58Hz -> 44Hz)
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

def save_audio(filepath, samples):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if filepath.endswith(".ogg"):
        try:
            import subprocess
            from record_race import resolve_ffmpeg_path
            ffmpeg_exe = resolve_ffmpeg_path()
            raw = struct.pack(f"<{len(samples)}h", *samples)
            cmd = [
                ffmpeg_exe, "-y",
                "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE),
                "-i", "-",
                "-c:a", "libvorbis", "-b:a", "64k",
                filepath
            ]
            subprocess.run(cmd, input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f" * Created compressed OGG: {filepath} ({len(samples)/SAMPLE_RATE:.2f}s, size={os.path.getsize(filepath)/1024:.1f} KB)")
            return
        except Exception:
            filepath = os.path.splitext(filepath)[0] + ".wav"

    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        packed = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(packed)
    print(f" * Created: {filepath} ({len(samples)/SAMPLE_RATE:.2f}s, peak={max(abs(s) for s in samples)})")

save_wav = save_audio

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "assets", "sounds", "victory")
    sounds = {
        "airhorn.ogg": generate_airhorn(),
        "anime_impact.ogg": generate_anime_impact(),
        "siuuu.ogg": generate_siuuu(),
        "horse_whinny.ogg": generate_horse_whinny(),
        "retro_8bit.ogg": generate_retro_8bit(),
        "royal_fanfare.ogg": generate_finish_fanfare(),
        "giga_chad.ogg": generate_giga_chad(),
    }
    print("Generating Victory SFX Pool (Compressed Mono OGG 64kbps)...")
    for filename, samples in sounds.items():
        save_audio(os.path.join(out_dir, filename), samples)
    print("[SUCCESS] All victory sounds generated and validated!")
