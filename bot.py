import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Configuración de variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 1. EL SERVIDOR "FALSO" PARA KOYEB ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running y Koyeb esta feliz!")

def run_dummy_server():
    # Koyeb asigna un puerto dinámico, por defecto suele ser 8000 u 8080
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
# -----------------------------------------

# --- 2. EL CEREBRO DEL BOT ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=(
        "Eres un asistente personal proactivo, inteligente y empático. "
        "Conversas de forma natural, haces preguntas para conocer mejor al usuario "
        "y recuerdas los detalles que te comparte."
    )
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Ya logramos esquivar la seguridad de Koyeb. ¿De qué hablamos hoy?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        # Esto imprimirá el error real en la consola de Koyeb
        print(f"ERROR DE GEMINI: {e}") 
        # Esto te mandará el error real por Telegram para que lo veas inmediato
        await update.message.reply_text(f"Ups, error de conexión: {str(e)}")


def main():
    # Arrancar el servidor web falso n un proceso paralelo
    threading.Thread(target=run_dummy_server, daemon=True).start()

    # Arrancar el bot de Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
