from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from database import get_db, engine
from models import Base, User as UserModel, TranslationHistory
from auth import get_current_user
from schemas import (
    User, UserCreate, UserLogin, Token,
    AudioToTextRequest, AudioToTextResponse,
    TextToAudioRequest, TranslationHistoryItem
)
from auth import verify_password, get_password_hash, create_access_token
from datetime import timedelta
from config import settings
import os
import base64
import time as time_module
import soundfile as sf
import numpy as np
import io
import requests
import re
import traceback

# Note: pydub est optionnel mais recommandé pour supporter plus de formats
# pip install pydub
# Sous Windows, installer aussi ffmpeg: https://ffmpeg.org/download.html

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sérère Translation API", version="1.0.0")

# CORS middleware - CONFIGURATION UNIQUE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        print(f"❌ Exception non gérée: {exc}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erreur interne du serveur: {str(exc)}"},
            headers={
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
            }
        )

# Servir les fichiers statiques
os.makedirs("static/audio", exist_ok=True)
os.makedirs("static/examples", exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.abspath("static")), name="static")

# Constants
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
MAX_TEXT_LENGTH = 1000
API_URL = "https://c19ujpu1gbrok3-8000.proxy.runpod.net"


# ==================== HELPER FUNCTIONS ====================
def validate_filename(filename: str) -> bool:
    """Valide le nom de fichier pour éviter path traversal"""
    if not filename:
        print("⚠️  Nom de fichier vide")
        return False

    if '..' in filename or '/' in filename or '\\' in filename:
        print(f"⚠️  Tentative de path traversal: {filename}")
        return False

    if not re.match(r'^[\w\-\.]+$', filename):
        print(f"⚠️  Nom de fichier invalide: {filename}")
        return False

    return True

def process_audio_for_api(audio_data: bytes) -> bytes:
    """Traite l'audio pour qu'il soit compatible avec l'API (16kHz, mono, max 30s)"""
    try:
        # Validation minimale des données
        if len(audio_data) < 100:
            raise ValueError("Données audio trop courtes")

        # ✅ Essayer plusieurs méthodes de lecture
        audio = None
        sr = None

        # Méthode 1: Lire directement avec soundfile
        try:
            audio, sr = sf.read(io.BytesIO(audio_data))
            print(f"✅ Audio lu avec soundfile - Format: {audio.shape if audio is not None else 'N/A'}, SR: {sr}")
        except Exception as e1:
            print(f"⚠️  Échec soundfile natif: {e1}")
            # Méthode 2: Essayer avec pydub
            try:
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
                wav_io = io.BytesIO()
                audio_segment.export(wav_io, format='wav')
                wav_io.seek(0)
                audio, sr = sf.read(wav_io)
                print(f"✅ Audio lu avec pydub - SR: {sr}")
            except Exception as e2:
                raise ValueError(f"Format audio non supporté. Erreurs: soundfile={e1}, pydub={e2}")

        # Vérifications
        if sr <= 0:
            raise ValueError(f"Fréquence d'échantillonnage invalide: {sr}")

        if len(audio) == 0:
            raise ValueError("Audio vide après lecture")

        # Convertir en mono si stéréo
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
            print(f"✅ Audio converti en mono")

        # Resampler à 16kHz si nécessaire
        if sr != 16000:
            from scipy import signal
            if len(audio) > 0:
                number_of_samples = round(len(audio) * float(16000) / sr)
                audio = signal.resample(audio, number_of_samples)
                sr = 16000
                print(f"✅ Audio resamplé à 16000 Hz")

        # Limiter la durée à 20 secondes (plus court)
        max_duration = 20
        if len(audio) > sr * max_duration:
            audio = audio[:sr * max_duration]
            print(f"⚠️  Audio tronqué à {max_duration} secondes")

        # Réduire la qualité pour diminuer la taille
        buffer = io.BytesIO()
        sf.write(buffer, audio, sr, format='WAV', subtype='PCM_16')
        buffer.seek(0)
        processed_data = buffer.read()

        print(f"✅ Audio traité: {len(processed_data)} bytes, {sr}Hz, {len(audio)/sr:.2f}s")
        return processed_data

    except Exception as e:
        print(f"❌ Erreur traitement audio: {str(e)}")
        raise HTTPException(500, f"Erreur lors du traitement audio: {str(e)}")


# ==================== AUTH ENDPOINTS ====================
@app.post("/api/v1/auth/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = db.query(UserModel).filter(UserModel.email == user.email).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        db_user = db.query(UserModel).filter(UserModel.username == user.username).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

        hashed_password = get_password_hash(user.password)
        db_user = UserModel(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during registration: {str(e)}"
        )


@app.post("/api/v1/auth/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(UserModel).filter(UserModel.email == user_credentials.email).first()
        if not user or not verify_password(user_credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during login: {str(e)}"
        )


@app.get("/api/v1/auth/me", response_model=User)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


# ==================== ENDPOINT 1: AUDIO → TEXTE ====================
@app.post("/api/v1/transcribe", response_model=AudioToTextResponse)
async def audio_to_text_serere(
        request: AudioToTextRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    tmp_file = None

    try:
        print(f"🎤 Début transcription audio pour {current_user.username}")

        # Vérification obligatoire
        if not request.audio_data:
            raise HTTPException(400, "Champ 'audio_data' manquant")

        # 📌 CAS 1 : l'utilisateur a envoyé un nom de fichier exemple .wav
        if request.audio_data.endswith(".wav"):
            example_path = f"static/examples/{request.audio_data}"
            if not os.path.exists(example_path):
                raise HTTPException(404, f"Fichier exemple introuvable: {request.audio_data}")

            print(f"📁 Lecture fichier exemple: {example_path}")
            with open(example_path, "rb") as f:
                audio_bytes = f.read()

        # 📌 CAS 2 : c'est une base64 envoyée par le frontend
        else:
            try:
                audio_bytes = base64.b64decode(request.audio_data)
            except Exception as e:
                print(f"❌ Erreur décodage base64: {e}")
                raise HTTPException(400, f"Erreur décodage base64: {str(e)}")

        # Validation taille
        if len(audio_bytes) > MAX_AUDIO_SIZE:
            raise HTTPException(400, "Fichier audio trop volumineux (max 10MB)")

        if len(audio_bytes) < 100:
            raise HTTPException(400, "Fichier audio invalide (trop court)")

        print(f"📦 Audio reçu : {len(audio_bytes)} bytes")

        # Traitement du son
        try:
            processed_audio = process_audio_for_api(audio_bytes)
            print(f"✅ Audio traité: {len(processed_audio)} bytes")
        except Exception as e:
            print(f"❌ Erreur traitement audio: {e}")
            traceback.print_exc()
            raise HTTPException(500, f"Erreur traitement audio: {str(e)}")

        # Sauvegarde temporaire
        tmp_file = f"static/audio/tmp_{current_user.id}_{int(time_module.time())}.wav"
        try:
            with open(tmp_file, "wb") as f:
                f.write(processed_audio)
            print(f"💾 Fichier temporaire créé: {tmp_file}")
        except Exception as e:
            print(f"❌ Erreur sauvegarde fichier: {e}")
            raise HTTPException(500, f"Erreur sauvegarde fichier: {str(e)}")

        # ✅ Envoi à l'API RunPod
        print(f"📤 Envoi vers {API_URL}/transcribe")

        response = None
        last_error = None

        # Méthode avec fichier
        try:
            with open(tmp_file, 'rb') as f:
                files = {'file': ('audio.wav', f, 'audio/wav')}
                response = requests.post(
                    f"{API_URL}/transcribe",
                    files=files,
                    timeout=300,
                    headers={'Connection': 'close'}
                )

            if response.status_code == 200:
                print("✅ Succès avec méthode files")
            else:
                print(f"⚠️ Échec méthode files: {response.status_code}")
                last_error = f"API returned {response.status_code}: {response.text[:200]}"
                response = None

        except requests.exceptions.Timeout:
            print(f"⏰ Timeout")
            last_error = "Timeout de l'API (5 minutes)"
        except requests.exceptions.ConnectionError as e:
            print(f"🔌 Erreur connexion: {e}")
            last_error = f"Erreur de connexion: {str(e)}"
        except Exception as e:
            print(f"❌ Erreur requête: {e}")
            last_error = str(e)

        if not response or response.status_code != 200:
            error_msg = last_error or "Aucune réponse valide de l'API"
            print(f"❌ Échec API: {error_msg}")
            raise HTTPException(500, f"Échec de la transcription: {error_msg}")

        # ✅ Traiter la réponse
        try:
            result = response.json()
            print(f"📥 Réponse API: {result}")

            transcription = None

            if isinstance(result, dict):
                # Format de votre API: {"text": "...", "success": true}
                if "text" in result:
                    transcription = result["text"]
                    print(f"✅ Format détecté: text")
                elif "transcription" in result:
                    transcription = result["transcription"]
                    print(f"✅ Format détecté: transcription")
                elif "output" in result and isinstance(result["output"], dict):
                    transcription = result["output"].get("text") or result["output"].get("transcription")
                    print(f"✅ Format détecté: output.*")
                else:
                    print(f"⚠️ Format inconnu. Clés: {list(result.keys())}")
            elif isinstance(result, str):
                transcription = result
                print(f"✅ Format détecté: string directe")

            # Validation
            if not transcription or not isinstance(transcription, str):
                error_detail = f"Format inattendu: {type(result)}"
                if isinstance(result, dict):
                    error_detail += f", Clés: {list(result.keys())}"
                print(f"❌ {error_detail}")
                raise HTTPException(500, error_detail)

            transcription = transcription.strip()

            if not transcription:
                raise HTTPException(500, "Transcription vide")

            print(f"✅ Transcription ({len(transcription)} chars): {transcription[:100]}...")

        except ValueError as e:
            print(f"❌ Erreur parsing JSON: {e}")
            print(f"   Réponse brute: {response.text[:500]}")
            raise HTTPException(500, f"JSON invalide: {e}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Erreur extraction: {e}")
            traceback.print_exc()
            raise HTTPException(500, f"Erreur traitement: {str(e)}")

        # Historique
        try:
            history_item = TranslationHistory(
                user_id=current_user.id,
                translation_type="audio_to_text",
                input_text="[Audio]",
                output_text=transcription
            )
            db.add(history_item)
            db.commit()
            print(f"✅ Historique sauvegardé")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde historique: {e}")
            # Ne pas faire échouer la requête pour ça
            db.rollback()

        return {"transcription": transcription, "success": True}

    except HTTPException as he:
        print(f"⚠️ HTTPException: {he.status_code} - {he.detail}")
        db.rollback()
        raise

    except Exception as e:
        print(f"❌ ERREUR CRITIQUE: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(500, f"Erreur interne: {str(e)}")

    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
                print(f"🗑️ Fichier temporaire supprimé")
            except Exception as e:
                print(f"⚠️ Impossible de supprimer {tmp_file}: {e}")


# ==================== ENDPOINT 2: TEXTE → AUDIO ====================
@app.post("/api/v1/synthesize")
async def text_to_audio_serere(
        request: TextToAudioRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        req: Request = None
):
    try:
        # Validation plus stricte
        if not request.text or not request.text.strip():
            raise HTTPException(400, "Le texte ne peut pas être vide")

        text_clean = request.text.strip()
        if len(text_clean) > MAX_TEXT_LENGTH:
            raise HTTPException(400, f"Texte trop long (max {MAX_TEXT_LENGTH} caractères)")

        # Validation des caractères spéciaux dangereux
        if any(char in text_clean for char in ['\x00', '\r']):
            raise HTTPException(400, "Caractères invalides dans le texte")

        print(f"📝 Texte à synthétiser ({len(text_clean)} chars): {text_clean[:100]}...")

        # Préparer données pour RunPod
        data = {
            "text": text_clean,
            "voice": "serere"
        }

        print(f"📤 Envoi vers {API_URL}/synthesize")
        response = requests.post(
            f"{API_URL}/synthesize",
            json=data,
            timeout=180,
            headers={'Connection': 'close'},
            stream=True
        )

        if response.status_code != 200:
            error_msg = response.text[:200] if response.text else "Erreur inconnue"
            raise HTTPException(500, f"Erreur API TTS: {error_msg}")

        # Vérifier si on a reçu des données
        content = b''
        for chunk in response.iter_content(1024):
            if chunk:
                content += chunk

        if len(content) == 0:
            raise HTTPException(500, "Aucune donnée audio reçue de l'API")

        # Validation du format WAV
        if not content.startswith(b'RIFF'):
            print(f"⚠️  Format reçu: {content[:20]}")
            raise HTTPException(500, "Le fichier audio reçu n'est pas un WAV valide")

        # Sauvegarder l'audio
        timestamp = int(time_module.time())
        filename = f"{current_user.id}_{timestamp}.wav"
        file_path = f"static/audio/{filename}"

        with open(file_path, "wb") as f:
            f.write(content)

        print(f"✅ Audio sauvegardé: {file_path} ({len(content)} bytes)")

        # Construction URL plus robuste
        base_url = str(req.base_url).rstrip('/') if req else "http://localhost:8000"
        audio_url = f"{base_url}/static/audio/{filename}"

        # Historique
        target_lang = request.target_language if hasattr(request, 'target_language') else 'serere'
        history_item = TranslationHistory(
            user_id=current_user.id,
            translation_type="text_to_audio",
            input_text=text_clean,
            output_text=f"Audio généré en {target_lang}",
            audio_url=audio_url
        )
        db.add(history_item)
        db.commit()
        db.refresh(history_item)

        return {"audio_url": audio_url, "success": True}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur interne synthèse: {str(e)}")
        raise HTTPException(500, f"Erreur interne: {str(e)}")


# ==================== ENDPOINT 3: STREAMING AUDIO ====================
@app.get("/api/v1/audio/stream/{filename}")
async def stream_audio(
        filename: str,
        current_user: User = Depends(get_current_user)
):
    # SÉCURITÉ: Validation du nom de fichier
    if not validate_filename(filename):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    file_path = f"static/audio/{filename}"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier audio introuvable")

    def iterfile():
        with open(file_path, mode="rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type="audio/x-wav",
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Accept-Ranges": "bytes"
        }
    )


# ==================== ENDPOINT 4: TÉLÉCHARGEMENT AUDIO ====================
@app.get("/api/v1/audio/download/{filename}")
async def download_audio(
        filename: str,
        current_user: User = Depends(get_current_user)
):
    # SÉCURITÉ: Validation du nom de fichier
    if not validate_filename(filename):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    file_path = f"static/audio/{filename}"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier audio introuvable")

    return FileResponse(
        file_path,
        media_type="audio/wav",
        filename=filename
    )


# ==================== ENDPOINT 5: HISTORIQUE ====================
@app.get("/api/v1/history", response_model=list[TranslationHistoryItem])
def get_translation_history(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        limit: int = 20,
        translation_type: str = None
):
    try:
        query = db.query(TranslationHistory).filter(
            TranslationHistory.user_id == current_user.id
        )

        if translation_type:
            query = query.filter(TranslationHistory.translation_type == translation_type)

        history = query.order_by(
            TranslationHistory.created_at.desc()
        ).limit(limit).all()

        return history
    except Exception as e:
        print(f"❌ Erreur récupération historique: {str(e)}")
        raise HTTPException(500, f"Erreur lors de la récupération de l'historique: {str(e)}")


# ==================== HEALTH CHECK ====================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API Sérère Translation en ligne"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Démarrage du serveur Sérère Translation API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)