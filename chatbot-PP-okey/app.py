from fastapi import FastAPI , UploadFile, File, Form
import json
from PIL import Image
import io
from pydantic import BaseModel
from data import DATA
import string
import os
import cv2
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
import speech_recognition as sr
from pydub import AudioSegment

# =====================
# CONFIGURAR GEMINI
# =====================
os.environ["GOOGLE_API_KEY"] = "AIzaSyDhW2oBDeIZtaQUnuOwY1lPBx4BlwEtQzA"
client = genai.Client()

app = FastAPI()

# 🔓 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    text: str
    state: dict = {}

@app.post("/chat")
def chat(msg: Message):
    text = msg.text.strip().lower()
    state = msg.state

    # =====================
    # BOTONES DE NAVEGACIÓN (COMANDOS LIMPIOS)
    # =====================
    if text == "volver año":
        return {
            "reply": (
                "👉 ¿De qué año sos?\n\n"
                "1️⃣ Primer año\n"
                "2️⃣ Segundo año\n\n"
                "3️⃣ 📘 Manual de usuario\n\n"
                "✏️ Escribí 1, 2 o 3"
            ),
            "state": {}
        }

    if text == "volver a materias" and "year" in state:
        materias = list(DATA[state["year"]].keys())
        letras = string.ascii_lowercase

        respuesta = "📚 Materias:\n\n"
        for i, m in enumerate(materias):
            respuesta += f"{letras[i]}. {m}\n"

        respuesta += "\n✏️ Escribí la letra de la materia"

        return {
            "reply": respuesta,
            "state": {"year": state["year"]},
            "buttons": ["🔙 Volver año"]
        }

    if text == "elegir otro tema" and "year" in state and "materia" in state:
        temas = DATA[state["year"]][state["materia"]]["temas"]
        respuesta = f"📖 {state['materia']}\n\n"

        for i, t in enumerate(temas, 1):
            respuesta += f"{i}. {t}\n"

        respuesta += "\n✏️ Escribí el número del tema"

        return {
            "reply": respuesta,
            "state": {
                "year": state["year"],
                "materia": state["materia"]
            },
            "buttons": ["🔙 Volver año", "📚 Volver a materias"]
        }

    # =====================
    # MENSAJE INICIAL
    # =====================
    if text == "" and not state:
        return {
            "reply": (
                "👋 Hola, soy el asistente de técnicas de estudio.\n\n"
                "👉 ¿De qué año sos?\n\n"
                "1️⃣ Primer año\n"
                "2️⃣ Segundo año\n\n"
                "3️⃣ 📘 Manual de usuario\n\n"
                "✏️ Escribí 1, 2 o 3"
            ),
            "state": {}
        }

    # =====================
    # PASO 1: AÑO
    # =====================
    if "year" not in state:
        if text == "3":
            return {
                "reply": (
                    "📘 MANUAL DE USUARIO\n\n"
                    "✔ Elegí primero el año y la materia.\n"
                    "✔ Se elegi la categoria con numero o letra (da igual si es mayuscula o minuscula).\n"
                    "✔ Luego seleccioná un tema para estudiar.\n"
                    "✔ Podés hacer preguntas libremente sobre el tema.\n\n"
                    "🖼️ Cuando estés en un tema, podés enviar imágenes.\n"
                    "🎥 También podés enviar videos relacionados.\n\n"
                    "🔘 Usá los botones para volver atrás sin perderte.\n"
                ),
                "state": {},
                "buttons": ["🔙 Volver año"]
            }

        if text not in ["1", "2"]:
            return {
                "reply": "❌ Categoría inválida. Ingrese una opcion valida",
                "state": state
            }

        state["year"] = text
        materias = list(DATA[text].keys())
        letras = string.ascii_lowercase

        respuesta = "📚 Materias:\n\n"
        for i, materia in enumerate(materias):
            respuesta += f"{letras[i]}. {materia}\n"

        respuesta += "\n✏️ Escribí la letra de la materia"

        return {
            "reply": respuesta,
            "state": state,
            "buttons": ["🔙 Volver año"]
        }

    # =====================
    # PASO 2: MATERIA
    # =====================
    if "materia" not in state:
        materias = list(DATA[state["year"]].keys())
        letras = string.ascii_lowercase

        if text not in letras[:len(materias)]:
            return {
                "reply": "❌ Categoría inválida.",
                "state": state,
                "buttons": ["❌ Categoría inválida – ingresar opción correcta", "🔙 Volver año"]
            }

        materia = materias[letras.index(text)]
        state["materia"] = materia

        temas = DATA[state["year"]][materia]["temas"]
        respuesta = f"📖 {materia}\n\n"

        for i, tema in enumerate(temas, 1):
            respuesta += f"{i}. {tema}\n"

        respuesta += "\n✏️ Escribí el número del tema"

        return {
            "reply": respuesta,
            "state": state,
            "buttons": ["🔙 Volver año", "📚 Volver a materias"]
        }

    # =====================
    # PASO 3: TEMA + IA
    # =====================
    if "tema" not in state:
        temas = DATA[state["year"]][state["materia"]]["temas"]
        tecnicas = DATA[state["year"]][state["materia"]]["tecnicas"]

        if not text.isdigit() or not (1 <= int(text) <= len(temas)):
            return {
                "reply": "❌ Categoría inválida.",
                "state": state,
                "buttons": [
                    "❌ Categoría inválida – ingresar opción correcta",
                    "🔙 Volver año",
                    "📚 Volver a materias"
                ]
            }

        tema = temas[int(text) - 1]
        state["tema"] = tema

        prompt = f"""
Sos un asistente educativo para alumnos de secundaria técnica.

Materia: {state['materia']}
Tema: {tema}

Explicá el tema con lenguaje simple, paso a paso.
Luego recomendá estas técnicas de estudio:
{', '.join(tecnicas)}
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        return {
            "reply": f"🧠 {tema}\n\n{response.text}",
            "state": state,
            "buttons": ["🔙 Volver año", "📚 Volver a materias", "📖 Elegir otro tema"]
        }

    # =====================
    # PASO 4: PREGUNTAS LIBRES
    # =====================
    prompt = f"""
El alumno está estudiando:
Materia: {state['materia']}
Tema: {state['tema']}

Pregunta del alumno:
{text}

Respondé de forma clara y con ejemplos simples.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    return {
        "reply": response.text,
        "state": state,
        "buttons": ["🔙 Volver año", "📚 Volver a materias", "📖 Elegir otro tema"]
    }

# ==================================================
# 🔥 NUEVO ENDPOINT: IMÁGENES (NO TOCA NADA ANTERIOR)
# ==================================================
@app.post("/chat-image")
async def chat_image(
    image: UploadFile = File(...),
    state: str = Form(...)
):
    state = json.loads(state)

    image_bytes = await image.read()
    img = Image.open(io.BytesIO(image_bytes))

    prompt = f"""
Sos un asistente educativo para alumnos de secundaria técnica.

Materia: {state.get('materia', 'No definida')}
Tema: {state.get('tema', 'No definido')}

Analizá la imagen y explicá qué se ve y qué conceptos escolares aparecen.
Usá lenguaje simple.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, img]
    )

    return {
        "reply": "🖼️ Análisis de la imagen:\n\n" + response.text,
        "state": state,
        "buttons": ["🔙 Volver año", "📚 Volver a materias", "📖 Elegir otro tema"]
    }

# ==================================================
# 🎥 NUEVO ENDPOINT: VIDEOS (NO TOCA NADA ANTERIOR)
# ==================================================
@app.post("/chat-video")
async def chat_video(
    video: UploadFile = File(...),
    state: str = Form(...)
):
    state = json.loads(state)

    # Guardar video temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(await video.read())
        video_path = tmp.name

    cap = cv2.VideoCapture(video_path)

    frames = []
    frame_count = 0

    while cap.isOpened() and len(frames) < 3:
        ret, frame = cap.read()
        if not ret:
            break

        # Tomar 1 frame cada ~2 segundos
        if frame_count % 60 == 0:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            frames.append(img)

        frame_count += 1

    cap.release()
    os.remove(video_path)

    prompt = f"""
Sos un asistente educativo para alumnos de secundaria técnica.

Materia: {state.get('materia', 'No definida')}
Tema: {state.get('tema', 'No definido')}

Analizá las imágenes extraídas del video.
Explicá qué se observa y qué conceptos escolares aparecen.
Usá lenguaje simple y claro.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, *frames]
    )

    return {
        "reply": "🎥 Análisis real del video:\n\n" + response.text,
        "state": state,
        "buttons": ["🔙 Volver año", "📚 Volver a materias", "📖 Elegir otro tema"]
    }
@app.post("/chat-image-question")
async def chat_image_question(
    image: UploadFile = File(...),
    question: str = Form(...),
    state: str = Form(...)
):
    state = json.loads(state)

    image_bytes = await image.read()
    img = Image.open(io.BytesIO(image_bytes))

    prompt = f"""
Sos un asistente educativo para alumnos de secundaria técnica.

Materia: {state.get('materia', 'No definida')}
Tema: {state.get('tema', 'No definido')}

El alumno cargó una imagen y pregunta lo siguiente:
"{question}"

Analizá la imagen y respondé específicamente a la consulta del alumno.
Usá lenguaje claro y ejemplos simples.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, img]
    )

    return {
        "reply": response.text,
        "state": state,
        "buttons": ["🔙 Volver año", "📚 Volver a materias", "📖 Elegir otro tema"]
    }
# ==================================================
# 🔊 NUEVO ENDPOINT: AUDIO (NO TOCA NADA ANTERIOR)
# ==================================================
@app.post("/chat-audio")
async def chat_audio(
    audio: UploadFile = File(...),
    state: str = Form(...),
    question: str = Form(None)  # 👈 NUEVO (opcional)
):
    state = json.loads(state)

    # Guardar audio temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_bytes = await audio.read()
        tmp.write(audio_bytes)
        audio_path = tmp.name

    # Convertir a WAV si hace falta
    sound = AudioSegment.from_file(audio_path)
    sound.export(audio_path, format="wav")

    # Speech to text
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio_data = recognizer.record(source)

    try:
        texto = recognizer.recognize_google(audio_data, language="es-ES")
    except:
        os.remove(audio_path)
        return {
            "reply": "❌ No se pudo reconocer el audio. Probá con otro archivo.",
            "state": state
        }

    os.remove(audio_path)

    # Prompt educativo
    if question:
        prompt = f"""
Sos un asistente educativo para alumnos de secundaria técnica.

Materia: {state.get('materia', 'No definida')}
Tema: {state.get('tema', 'No definido')}

El siguiente texto fue obtenido de un audio:

\"\"\"{texto}\"\"\"


El alumno hizo la siguiente pregunta:
\"\"\"{question}\"\"\"


Respondé específicamente a la pregunta del alumno
y explicá el contenido del audio de forma clara.
"""
    else:
        prompt = f"""
Sos un asistente educativo para alumnos de secundaria técnica.

Materia: {state.get('materia', 'No definida')}
Tema: {state.get('tema', 'No definido')}

El siguiente texto fue obtenido de un audio:

\"\"\"{texto}\"\"\"


Explicá con palabras simples qué se dice en el audio
y qué conceptos escolares aparecen.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    return {
        "reply": "🔊 Explicación del audio:\n\n" + response.text,
        "state": state,
        "buttons": ["🔙 Volver año", "📚 Volver a materias", "📖 Elegir otro tema"]
    }
