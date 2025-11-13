import requests

API_URL = "https://c19ujpu1gbrok3-8000.proxy.runpod.net"

# Synthétiser de la parole
data = {
    "text": "Njokoo, ndam nu mbi'u koy, ɓaanu no we njegaajam, mi de, kaa naamtaa, nam waagumu fi boo ret saax laa neel le joofyoor.",
    "temperature": 0.8,
    "top_k": 50,
    "top_p": 1.0
}

print("📤 Envoi de la requête TTS...")
response = requests.post(f"{API_URL}/synthesize", json=data, timeout=180)

print(f"\n📡 Status Code: {response.status_code}")
print(f"📋 Headers: {dict(response.headers)}")
print(f"📊 Content Length: {len(response.content)} bytes")
print(f"🔤 Content Type: {response.headers.get('content-type', 'N/A')}")

# Afficher le contenu si ce n'est pas du binaire
if response.headers.get('content-type', '').startswith('application/json'):
    print(f"\n⚠️  La réponse est du JSON (probablement une erreur):")
    print(response.json())
elif len(response.content) == 0:
    print(f"\n❌ La réponse est vide!")
    print(f"Response text: {response.text}")
else:
    # Sauvegarder l'audio
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print(f"\n✅ Audio sauvegardé dans output.wav ({len(response.content)} bytes)")

    # Vérifier si c'est un vrai fichier WAV
    with open("output.wav", "rb") as f:
        header = f.read(4)
        if header == b'RIFF':
            print("✅ Fichier WAV valide détecté")
        else:
            print(f"⚠️  En-tête inattendu: {header}")


