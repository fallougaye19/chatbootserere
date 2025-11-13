import soundfile as sf
import requests
import numpy as np

API_URL = "https://c19ujpu1gbrok3-8000.proxy.runpod.net"

# -------------------------
# 🔊 1. Lecture du fichier WAV
# -------------------------
audio, sr = sf.read("2.wav")

# Convertir en mono si stéréo
if len(audio.shape) > 1:
    audio = np.mean(audio, axis=1)

# -------------------------
# 🎚️ 2. Resample à 16 kHz
# -------------------------
if sr != 16000:
    old_sr = sr
    ratio = 16000 / sr
    new_length = int(len(audio) * ratio)
    indices = np.linspace(0, len(audio) - 1, new_length)
    audio = np.interp(indices, np.arange(len(audio)), audio)
    sr = 16000
    print(f"🔁 Audio resamplé de {old_sr} Hz à 16000 Hz")

# -------------------------
# ✂️ 3. Limiter à 30 secondes max
# -------------------------
max_duration = 30
if len(audio) > sr * max_duration:
    audio = audio[:sr * max_duration]
    print(f"⚠️ Audio tronqué à {max_duration} secondes")

# -------------------------
# 💾 4. Sauvegarde du nouveau fichier
# -------------------------
sf.write("audio_compressed.wav", audio, sr)
print(f"💾 Fichier compressé sauvegardé : audio_compressed.wav")

# -------------------------
# 📡 5. Envoi à l’API /transcribe
# -------------------------
print("\n📤 Envoi vers l'API...")

with open("audio_compressed.wav", "rb") as f:
    files = {
        "file": ("audio.wav", f, "audio/wav")
    }

    try:
        response = requests.post(
            f"{API_URL}/transcribe",
            files=files,
            timeout=180,
            headers={"Connection": "close"}
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            print("🎉 Réponse API :", response.json())
        else:
            print("❌ Erreur API :", response.text)

    except requests.exceptions.Timeout:
        print("⏳ Timeout : le serveur n’a pas répondu à temps.")
    except requests.exceptions.RequestException as e:
        print("🚨 Erreur réseau :", e)
