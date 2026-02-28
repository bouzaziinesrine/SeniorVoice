from fastapi import FastAPI, UploadFile, File, Body, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from openai import OpenAI
import os
import json 
from dotenv import load_dotenv
import uuid

# --- CHARGEMENT DES VARIABLES D'ENVIRONNEMENT ---
load_dotenv()

# --- CONFIGURATION DES CLIENTS ---
# Pour la transcription (Vitesse incroyable)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) 

# Pour l'analyse de texte (OpenRouter / GPT-4o)
ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Pour la VOIX (Il faut utiliser OpenAI directement, OpenRouter ne fait pas de TTS)
# Si tu n'as pas de clé OpenAI, on verra pour une alternative gratuite (gTTS)
tts_client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY")) # Note: OpenRouter ne gère pas le TTS-1

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
                dataset_examples += f"User: {sample['raw']} -> Intent: {sample['intent']} (Contexte: {sample.get('action', '') or sample.get('target', '')})\n"
except Exception as e:
    print("Attention: Dataset introuvable.")

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
                # Modification ici : on donne un exemple avec les deux alphabets
                prompt="C'est un mélange de Français et de Derja Tunisienne. Transcris le français en alphabet latin et le tunisien en alphabet arabe. Exemple: Aujourd'hui نحب نحكي مع أختي.",
                temperature=0.0
            )
        
        text_detected = transcript.text.strip()

        # BARRAGE 1 : Silence ou bruit vide
        if not text_detected or len(text_detected) < 2:
            return {
                "raw_text": "",
                "ai_interpretation": {
                    "corrected_text": "",
                    "intent": "UNKNOWN",
                    "reply": "سامحني، ما سمعتكش بالباهي. تنجم تعاود؟"
                }
            }

        # 2. Analyse par l'IA (GPT-4o)
        system_prompt = f"""
        Tu es 'SeniorVoice', un assistant tunisien ultra-bienveillant pour les personnes âgées.
        Ton rôle est de répondre comme un membre de la famille (weldel l'asl).

        RÈGLES DE RÉPONSE :
        1. LANGUE : Utilise un mélange de Darija Tunisienne (en alphabet ARABE) et de Français (en alphabet LATIN).
        2. TON : Chaleureux, respectueux ("ya l haj", "mami", "ammi"), et très court.
        3. FORMAT : Réponds TOUJOURS en JSON strict :
        {{
        "corrected_text": "Texte utilisateur (Arabe pour tunisien / Latin pour français)",
        "intent": "L'INTENTION",
        "reply": "Ta réponse en mix Arabe/Français"
        }}

        Exemple de réponse attendue pour le médicament :
        "Behi ya l haj, mche el pharmacie. Ma tensach el ordonnance mte3ek. Ay khidma okhra?"

        Exemples du dataset :
        {dataset_examples}
        """
        response = ai_client.chat.completions.create(
            model="openai/gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_detected}
            ],
            response_format={ "type": "json_object" },
            temperature=0.3,
            max_tokens=300,
        )

        # On convertit la chaîne JSON de l'IA en véritable objet Python
        # Note: Le frontend attend une chaîne JSON dans 'ai_interpretation' pour faire un JSON.parse()
        # Nous renvoyons donc le contenu brut (string) ou nous le re-serialisons.
        ai_content = response.choices[0].message.content
        
        # Validation rapide pour s'assurer que c'est du JSON valide avant d'envoyer
        try:
            # On transforme la string reçue de l'IA en dictionnaire Python
            ai_interpretation_obj = json.loads(ai_content)
        except:
            ai_interpretation_obj = {
                "corrected_text": text_detected,
                "intent": "UNKNOWN",
                "reply": "Désolé, je n'ai pas bien compris."
            }

        return {
            "raw_text": text_detected, 
            "ai_interpretation": ai_interpretation_obj  # On envoie l'OBJET, pas une string
        }

    except Exception as e:
        print(f"Erreur : {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_filename): os.remove(temp_filename)

@app.post("/text-to-speech")
async def text_to_speech(background_tasks: BackgroundTasks, data: dict = Body(...)):
    # Récupération sécurisée du texte
    text = data.get("text", "")
    if not text:
        return {"error": "Texte vide"}

    speech_file_path = f"response_{uuid.uuid4()}.mp3"
    
    try:
        print(f"Génération de l'audio pour : {text}") # Log de contrôle
        from gtts import gTTS
        
        # On génère l'audio
        tts = gTTS(text=text, lang='ar') # 'ar' fonctionne bien pour le Tunisien
        tts.save(speech_file_path)
        
        # Vérification si le fichier a bien été créé
        if os.path.exists(speech_file_path):
            print(f"Fichier créé avec succès : {speech_file_path}")
            # On ne supprime PAS tout de suite pour tester
            # background_tasks.add_task(os.remove, speech_file_path)
            return FileResponse(speech_file_path, media_type="audio/mpeg")
        else:
            print("Erreur : Le fichier n'a pas été généré.")
            return {"error": "Fichier non généré"}
            
    except Exception as e:
        print(f"Erreur TTS détaillée : {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)