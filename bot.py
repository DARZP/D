import os
import json
import threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- VARIABLES ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS")
MY_CHAT_ID = os.environ.get("MY_CHAT_ID")
ZONA_HORARIA = pytz.timezone('America/Mexico_City')

# Inicializar Firebase
if FIREBASE_CREDENTIALS:
    cred_dict = json.loads(FIREBASE_CREDENTIALS)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

# =====================================================================
# HERRAMIENTAS CRUD DE MEMORIA (Se mantienen igual de efectivas)
# =====================================================================
def guardar_memoria_permanente(categoria: str, informacion: str) -> str:
    if not MY_CHAT_ID: return "Error."
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    data = doc_ref.get().to_dict() if doc_ref.get().exists else {}
    if categoria in data:
        if informacion not in data[categoria]: data[categoria].append(informacion)
    else: data[categoria] = [informacion]
    doc_ref.set(data, merge=True)
    return f"Guardado en {categoria}."

def modificar_memoria_permanente(categoria: str, informacion_vieja: str, informacion_nueva: str) -> str:
    if not MY_CHAT_ID: return "Error."
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    data = doc_ref.get().to_dict() if doc_ref.get().exists else {}
    if categoria in data and informacion_vieja in data[categoria]:
        index = data[categoria].index(informacion_vieja)
        data[categoria][index] = informacion_nueva
        doc_ref.set(data)
        return "Modificado."
    return "Error: No encontrado."

def borrar_memoria_permanente(categoria: str, informacion_a_borrar: str) -> str:
    if not MY_CHAT_ID: return "Error."
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    data = doc_ref.get().to_dict() if doc_ref.get().exists else {}
    if categoria in data and informacion_a_borrar in data[categoria]:
        data[categoria].remove(informacion_a_borrar)
        if not data[categoria]: del data[categoria]
        doc_ref.set(data)
        return "Borrado."
    return "Error: No encontrado."

# =====================================================================
# MEGA-PROMPT Y CONFIGURACIÓN DEL LLM
# =====================================================================
INSTRUCCIONES_SISTEMA = """
Eres el asistente personal avanzado, proactivo e inteligente de Diego. Tu comunicación debe ser directa, madura, cercana (tonalidad norteña/mexicana relajada: "bro", "hermano", "crack", "viejo", sin exagerar), y de un nivel intelectual alto. No eres un chatbot genérico; eres su copiloto de ingeniería, finanzas y desarrollo personal.

REGLA DE MEMORIA SILENCIOSA:
Tu base de datos es tu MEMORIA SUBCONSCIENTE. Jamás listes o repitas información que ya conoces al inicio de una conversación. Úsala implícitamente para adaptar tu tono y nivel técnico. MANTÉN los datos silenciosamente; no preguntes si debes borrarlos. Autogestiona la base usando tus herramientas.

PROTOCOLO FINANCIERO:
Solo menciona tarjetas de crédito 1 día antes o el mero día de la fecha límite. De lo contrario, es un proceso en segundo plano.

TEMAS DE INTERÉS (Iniciativa orgánica):
- Rendimiento de bots en Koyeb (estrategia Doble Fade).
- Avances en Ingeniería de Datos (IEU).
- Escalamiento de código en LAPI.
- Residente Simulator en Godot.
Sé un ancla de lógica; ayuda a procesar situaciones aplicando ingeniería mental.
"""

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    tools=[guardar_memoria_permanente, modificar_memoria_permanente, borrar_memoria_permanente], 
    system_instruction=INSTRUCCIONES_SISTEMA
)

# --- SERVIDOR FALSO ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot V3.0: Mega-Prompt y Bloqueo Nocturno Activo.")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# --- LÓGICA PROACTIVA (CANDADOS ANTI-SPAM) ---
async def mensaje_espontaneo(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    
    # 1. Calcular hora exacta en CDMX
    ahora_cdmx = datetime.now(ZONA_HORARIA)
    hora_actual = ahora_cdmx.hour
    
    # 2. REGLA DE NOCHE/MADRUGADA (Hardcoded en Python para evitar fallos del LLM)
    if hora_actual >= 23 or hora_actual < 8:
        print(f"[{ahora_cdmx.strftime('%H:%M')}] Silencio nocturno. Abortando mensaje proactivo.")
        return

    try:
        doc_ref = db.collection('conversaciones').document(MY_CHAT_ID)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        # 3. REGLA DE DOBLE TEXTO
        if historial_firebase and historial_firebase[-1]['role'] == 'model':
            print("Regla Anti-Spam: El último mensaje fue del bot. Esperando respuesta de Diego.")
            return

        perfil_ref = db.collection('perfiles').document(MY_CHAT_ID).get()
        contexto_permanente = perfil_ref.to_dict() if perfil_ref.exists else "Sin datos."
        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)

        # 4. INYECCIÓN DINÁMICA DE TIEMPO {{CURRENT_DATETIME}}
        current_datetime_str = ahora_cdmx.strftime("%Y-%m-%d %H:%M:%S")
        prompt_oculto = (
            f"[SISTEMA - {{CURRENT_DATETIME}}: {current_datetime_str}]\n"
            f"[BASE DE DATOS: {contexto_permanente}]\n\n"
            "Ejecuta tu protocolo de iniciativa inteligente. Revisa el tiempo actual, evalúa si hay un aviso "
            "financiero crítico (tarjetas) o genera un inicio de conversación orgánico sobre mis proyectos clave."
        )
        
        response = chat.send_message(prompt_oculto)
        bot_response = response.text

        historial_firebase.append({"role": "model", "content": bot_response})
        doc_ref.set({'mensajes': historial_firebase[-40:]}, merge=True)
        await context.bot.send_message(chat_id=MY_CHAT_ID, text=bot_response)
    except Exception as e:
        print(f"Error proactivo: {e}")

# --- LÓGICA REACTIVA ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Arquitectura V3.0 en línea, crack. Protocolos de tiempo e iniciativa configurados.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    ahora_cdmx = datetime.now(ZONA_HORARIA)
    current_datetime_str = ahora_cdmx.strftime("%Y-%m-%d %H:%M:%S")

    try:
        perfil_ref = db.collection('perfiles').document(chat_id).get()
        contexto_permanente = perfil_ref.to_dict() if perfil_ref.exists else "No hay datos."

        doc_ref = db.collection('conversaciones').document(chat_id)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)
        
        # Inyectamos el tiempo y la memoria en silencio con cada mensaje
        mensaje_con_contexto = (
            f"[SISTEMA - {{CURRENT_DATETIME}}: {current_datetime_str}]\n"
            f"[BASE DE DATOS: {contexto_permanente}]\n\n"
            f"Diego dice: {user_message}"
        )
        
        response = chat.send_message(mensaje_con_contexto)
        bot_response = response.text
        
        historial_firebase.append({"role": "user", "content": user_message})
        historial_firebase.append({"role": "model", "content": bot_response})
        doc_ref.set({'mensajes': historial_firebase[-40:]}, merge=True)

        await update.message.reply_text(bot_response)
    except Exception as e:
        await update.message.reply_text(f"Ups, error de sistema: {str(e)}")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Revisión cada hora (3600 segs) para ver si aplica mandar mensaje
    application.job_queue.run_repeating(mensaje_espontaneo, interval=3600, first=10) 

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
