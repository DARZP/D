import os
import json
import threading
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

# Inicializar Firebase
if FIREBASE_CREDENTIALS:
    cred_dict = json.loads(FIREBASE_CREDENTIALS)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

# =====================================================================
# LA MAGIA: HERRAMIENTA AUTÓNOMA PARA EL BOT (FUNCTION CALLING)
# =====================================================================
def guardar_memoria_permanente(categoria: str, informacion: str) -> str:
    """
    Usa esta herramienta EXCLUSIVAMENTE para guardar datos CRÍTICOS y permanentes sobre Mario.
    Ejemplo de categorías: 'proyectos_tecnologicos', 'fechas_importantes', 'preferencias', 'salud'.
    """
    if not MY_CHAT_ID:
        return "Error: MY_CHAT_ID no configurado."
    
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    doc = doc_ref.get()
    
    # Extraemos lo que ya existe o creamos un diccionario nuevo
    data = doc.to_dict() if doc.exists else {}
    
    # Agregamos la nueva información a la categoría correspondiente
    if categoria in data:
        if informacion not in data[categoria]: # Evitamos duplicados
            data[categoria].append(informacion)
    else:
        data[categoria] = [informacion]
        
    doc_ref.set(data, merge=True)
    print(f"BOT AUTÓNOMO ACCIONADO: Guardó '{informacion}' en '{categoria}'")
    return f"Éxito: La información '{informacion}' ha sido guardada en la memoria a largo plazo."

# =====================================================================

# Inicializar Gemini asignándole la herramienta
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    tools=[guardar_memoria_permanente], # ¡Aquí le damos la herramienta al bot!
    system_instruction=(
        "Eres el asistente personal avanzado de Mario. Eres proactivo e inteligente. "
        "TIENES ACCESO A UNA HERRAMIENTA: 'guardar_memoria_permanente'. "
        "Úsala de manera autónoma cuando el usuario te comparta información clave que no deba "
        "olvidarse (ej. lógica de códigos, fechas límite, detalles de sus emprendimientos o avances médicos). "
        "No preguntes si debes guardarlo, hazlo si lo consideras de alto valor."
    )
)

# --- SERVIDOR FALSO ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot V2.0: Memoria a largo plazo activada.")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# --- LÓGICA PROACTIVA ---
async def mensaje_espontaneo(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    try:
        # Recuperar perfil permanente para inyectarlo como contexto
        perfil_ref = db.collection('perfiles').document(MY_CHAT_ID).get()
        contexto_permanente = perfil_ref.to_dict() if perfil_ref.exists else "Aún no hay datos permanentes."

        doc_ref = db.collection('conversaciones').document(MY_CHAT_ID)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        
        # Habilitamos la ejecución automática de funciones
        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)

        prompt_oculto = (
            f"CONTEXTO DE MEMORIA A LARGO PLAZO: {contexto_permanente} \n\n"
            "Teniendo en cuenta lo anterior, genera un mensaje proactivo y natural para iniciar la conversación. "
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
    await update.message.reply_text("Arquitectura V2 lista. Ahora analizo y guardo lo importante por mi cuenta.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # 1. Recuperamos la Memoria a Largo Plazo
        perfil_ref = db.collection('perfiles').document(chat_id).get()
        contexto_permanente = perfil_ref.to_dict() if perfil_ref.exists else "No hay datos."

        # 2. Recuperamos el hilo de la conversación a corto plazo
        doc_ref = db.collection('conversaciones').document(chat_id)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        
        # 3. Encendemos el chat con la capacidad de usar herramientas de forma automática
        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)
        
        # 4. Inyectamos la memoria permanentemente en silencio junto con tu mensaje
        mensaje_con_contexto = f"[Memoria Permanente Actual: {contexto_permanente}]\n\nMensaje del usuario: {user_message}"
        
        response = chat.send_message(mensaje_con_contexto)
        bot_response = response.text
        
        historial_firebase.append({"role": "user", "content": user_message})
        historial_firebase.append({"role": "model", "content": bot_response})
        doc_ref.set({'mensajes': historial_firebase[-40:]}, merge=True)

        await update.message.reply_text(bot_response)
    except Exception as e:
        await update.message.reply_text(f"Ups, error de base de datos: {str(e)}")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Configuración del despertador (ej. cada 8 horas)
    application.job_queue.run_repeating(mensaje_espontaneo, interval=28800, first=10) 

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
    
