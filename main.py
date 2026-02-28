from fastapi import FastAPI, UploadFile, File, Body
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from openai import OpenAI
import os
import json 
from dotenv import load_dotenv # NOUVEAU : Pour lire le fichier .env

# --- CHARGEMENT DES VARIABLES D'ENVIRONNEMENT ---
load_dotenv()

# --- CONFIGURATION ---
# On récupère les clés depuis le fichier .env
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) 

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CHARGEMENT DU DATASET ---
dataset_examples = ""
try:
    with open("dataset_senior_voice.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)
        for category in dataset.get("data", []):
            for sample in category.get("samples", [])[:2]: 
                dataset_examples += f"User: {sample['raw']} -> Intent: {sample['intent']}, Action: {sample.get('action', sample.get('target', ''))}\n"
except Exception as e:
    print("Attention: Fichier dataset_senior_voice.json introuvable ou mal formaté.")

@app.post("/process-voice")
async def process_voice(file: UploadFile = File(...)):
    temp_filename = "temp_audio.wav"
    try:
        content = await file.read()
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)

        # 1. Transcription avec Groq
        with open(temp_filename, "rb") as audio_file:
            transcript = groq_client.audio.transcriptions.create(
                file=(temp_filename, audio_file),
                model="whisper-large-v3",
                response_format="verbose_json",
                prompt="Transcrire exactement les mots prononcés, que ce soit en arabe tunisien (Darja) ou en français. Ne pas traduire."
            )
        
        text_detected = transcript.text

        # 2. Analyse avec tes propres exemples injectés
        system_prompt = f"""Tu es SeniorVoice, un assistant vocal pour un senior TUNISIEN.
        Voici des exemples de ce que le senior peut dire et de l'intention que tu dois détecter (inspirés de notre base de données) :
        
        {dataset_examples}
        
        RÈGLES STRICTES :
        1. Corrige l'orthographe de Whisper si besoin (le senior parle en Darja tunisienne et français).
        2. Déduis l'intention ('intent') exactement comme dans les exemples ci-dessus.
        3. Ta réponse ('reply') DOIT être amicale, compatissante, et rédigée en VRAI dialecte tunisien (en lettres arabes, ex: 'باهي، تو نكلمولك').
        4. Retourne UNIQUEMENT un JSON de cette forme : 
        {{
            "corrected_text": "le texte corrigé",
            "intent": "l'intention détectée", 
            "reply": "ta réponse en arabe tunisien"
        }}"""

        response = ai_client.chat.completions.create(
            model="openai/gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_detected}
            ],
            response_format={ "type": "json_object" },
            max_tokens=250
        )

        return {
            "raw_text": text_detected, 
            "ai_interpretation": response.choices[0].message.content
        }

    except Exception as e:
        print(f"Erreur : {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)

@app.post("/text-to-speech")
async def text_to_speech(text: str = Body(embed=True)):
    speech_file_path = "response.mp3"
    
    # Utilisation d'OpenAI pour une voix naturelle (ou gTTS pour du gratuit)
    response = ai_client.audio.speech.create(
        model="tts-1",
        voice="alloy", # Voix calme et claire pour les seniors
        input=text
    )
    
    response.stream_to_file(speech_file_path)
    return FileResponse(speech_file_path, media_type="audio/mpeg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)