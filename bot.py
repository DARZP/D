import os
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- VARIABLES Y CONFIGURACIÓN ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS")

# Inicializar Firebase
if FIREBASE_CREDENTIALS:
    # Convertimos el string de Koyeb de vuelta a un diccionario de Python
    cred_dict = json.loads(FIREBASE_CREDENTIALS)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    print("ADVERTENCIA: No se encontró FIREBASE_CREDENTIALS")

# Inicializar Gemini (Usa el modelo que te haya funcionado)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-flash-latest", 
    system_instruction=(
        "Eres un asistente personal proactivo, inteligente y empático. "
        "Conversas de forma natural y recuerdas los detalles "
        "que el usuario te comparte para construir una relación a largo plazo."
    )
)

# --- SERVIDOR WEB FALSO PARA KOYEB ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot corriendo y recordando!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# --- LÓGICA DEL BOT CON MEMORIA ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! He despertado mi hipocampo. Ahora recordaré todo lo que platiquemos. ¿Qué hay de nuevo?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = str(update.effective_chat.id) # Usamos el ID del chat como identificador en la base de datos
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # 1. Recuperar el historial de Firebase
        doc_ref = db.collection('conversaciones').document(chat_id)
        doc = doc_ref.get()
        
        historial_firebase = []
        if doc.exists:
            historial_firebase = doc.to_dict().get('mensajes', [])

        # 2. Formatear el historial para que Gemini lo entienda
        gemini_history = []
        for msg in historial_firebase:
            # Gemini requiere formato {"role": "user" o "model", "parts": ["texto"]}
            gemini_history.append({"role": msg["role"], "parts": [msg["content"]]})

        # 3. Iniciar el chat con el historial inyectado
        chat = model.start_chat(history=gemini_history)
        
        # 4. Enviar el nuevo mensaje y recibir respuesta
        response = chat.send_message(user_message)
        bot_response = response.text
        
        # 5. Guardar la nueva interacción en nuestro registro local
        historial_firebase.append({"role": "user", "content": user_message})
        historial_firebase.append({"role": "model", "content": bot_response})
        
        # 6. Actualizar Firebase (limitamos a los últimos 40 mensajes para no saturar la base)
        doc_ref.set({'mensajes': historial_firebase[-40:]}, merge=True)

        await update.message.reply_text(bot_response)

    except Exception as e:
        print(f"ERROR: {e}")
        await update.message.reply_text(f"Ups, me dolió la cabeza (Error: {str(e)})")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
