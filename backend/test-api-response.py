import requests
import json

API_URL = "https://c19ujpu1gbrok3-8000.proxy.runpod.net"

# Test avec un fichier audio
with open("static/examples/GEN_01_seg002.wav", "rb") as f:
    files = {"file": ("audio.wav", f, "audio/wav")}

    try:
        response = requests.post(
            f"{API_URL}/transcribe",
            files=files,
            timeout=180
        )

        print(f"Status Code: {response.status_code}")
        print(f"Headers: {response.headers}")
        print(f"\n📥 Réponse brute:")
        print(response.text[:1000])

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"\n📦 JSON parsé:")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                print(f"\n🔍 Structure:")
                print(f"Type: {type(data)}")
                if isinstance(data, dict):
                    print(f"Clés: {list(data.keys())}")
                    for key, value in data.items():
                        print(f"  {key}: {type(value)} = {str(value)[:100]}")

            except ValueError as e:
                print(f"❌ Erreur parsing JSON: {e}")
        else:
            print(f"❌ Erreur API: {response.text}")

    except Exception as e:
        print(f"❌ Erreur: {e}")