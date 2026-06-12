import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Configuración de variables de entorno (las configurarás en Koyeb)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Inicializar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=(
        "Eres un asistente personal proactivo, inteligente y empático. "
        "No eres un buscador de tareas robótico; conversas de forma natural, "
        "haces preguntas para conocer mejor al usuario y recuerdas los detalles "
        "que te comparte para construir una relación a largo plazo."
    )
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Aquí estoy. A partir de ahora, este es nuestro espacio para platicar, planear y lo que necesites. ¿De qué tienes ganas de hablar hoy?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    # Indicar que el bot está "escribiendo"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Generar respuesta con Gemini
        # Nota: Para el MVP es unicelular, en la Fase 2 le añadiremos el historial de Firebase
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("Ups, tuve un pequeño pestañeo digital. ¿Me lo repites?")

def main():
    # Crear la aplicación de Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Iniciar el bot (Polling para desarrollo local, luego cambiaremos a Webhook en Koyeb)
    application.run_polling()

if __name__ == "__main__":
    main()
