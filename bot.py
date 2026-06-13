import os
import json
import threading
import datetime
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
MY_CHAT_ID = os.environ.get("MY_CHAT_ID") # Tu identificador personal

# Inicializar Firebase
if FIREBASE_CREDENTIALS:
    cred_dict = json.loads(FIREBASE_CREDENTIALS)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

# Inicializar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    system_instruction=(
        "Eres el asistente personal de Mario. Eres proactivo, natural y honesto. "
        "No pareces un robot. Estás al tanto de sus proyectos tecnológicos de salud, "
        "el simulador JRPG, sus ventas y sus gustos. Mantén las charlas fluidas."
    )
)

# --- SERVIDOR FALSO PARA KOYEB ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot corriendo, recordando y siendo proactivo!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# --- NUEVO: FUNCIÓN PROACTIVA ESPONTÁNEA ---
async def mensaje_espontaneo(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID:
        return

    try:
        # Leemos la memoria para tener contexto
        doc_ref = db.collection('conversaciones').document(MY_CHAT_ID)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        chat = model.start_chat(history=gemini_history)

        # Le damos una instrucción "invisible" para que genere el mensaje
        prompt_oculto = (
            "Genera un mensaje proactivo y casual para iniciar la conversación conmigo hoy. "
            "Revisa nuestro historial reciente. Puedes preguntarme cómo va mi día, "
            "si he avanzado en mis códigos, si hay noticias de Fórmula 1, o simplemente saludar. "
            "Hazlo muy natural, corto y fluido, como un amigo que te escribe de la nada."
        )
        
        response = chat.send_message(prompt_oculto)
        bot_response = response.text

        # Guardamos este nuevo mensaje en Firebase para que no se le olvide que te lo mandó
        historial_firebase.append({"role": "model", "content": bot_response})
        doc_ref.set({'mensajes': historial_firebase[-40:]}, merge=True)

        # Te lo enviamos a Telegram
        await context.bot.send_message(chat_id=MY_CHAT_ID, text=bot_response)
    except Exception as e:
        print(f"Error en mensaje espontáneo: {e}")

# --- LÓGICA REACTIVA (Cuando tú le hablas) ---
# ... (Aquí va tu función start y handle_message exactamente igual que antes) ...
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Sistema proactivo en línea. Ahora puedo escribirte yo también.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        doc_ref = db.collection('conversaciones').document(chat_id)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        chat = model.start_chat(history=gemini_history)
        
        response = chat.send_message(user_message)
        bot_response = response.text
        
        historial_firebase.append({"role": "user", "content": user_message})
        historial_firebase.append({"role": "model", "content": bot_response})
        doc_ref.set({'mensajes': historial_firebase[-40:]}, merge=True)

        await update.message.reply_text(bot_response)
    except Exception as e:
        await update.message.reply_text(f"Ups, error: {str(e)}")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # Añadimos JobQueue a la aplicación
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Configuramos el despertador interno (Ejemplo: Ejecutar una vez al día o cada X horas)
    # Aquí lo pongo para que se ejecute cada 8 horas (8 * 60 * 60 segundos)
    application.job_queue.run_repeating(mensaje_espontaneo, interval=28800, first=10) 

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
