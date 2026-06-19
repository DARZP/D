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
# LAS HERRAMIENTAS AUTÓNOMAS DEL BOT (CRUD COMPLETO)
# =====================================================================

def guardar_memoria_permanente(categoria: str, informacion: str) -> str:
    """Guarda información nueva y crítica en la memoria a largo plazo."""
    if not MY_CHAT_ID: return "Error: MY_CHAT_ID no configurado."
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    data = doc_ref.get().to_dict() if doc_ref.get().exists else {}
    
    if categoria in data:
        if informacion not in data[categoria]:
            data[categoria].append(informacion)
    else:
        data[categoria] = [informacion]
        
    doc_ref.set(data, merge=True)
    print(f"✅ GUARDADO: '{informacion}' en '{categoria}'")
    return f"Éxito: Guardado en {categoria}."

def modificar_memoria_permanente(categoria: str, informacion_vieja: str, informacion_nueva: str) -> str:
    """Reemplaza un dato obsoleto por uno nuevo dentro de una categoría existente."""
    if not MY_CHAT_ID: return "Error: MY_CHAT_ID no configurado."
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    data = doc_ref.get().to_dict() if doc_ref.get().exists else {}

    if categoria in data and informacion_vieja in data[categoria]:
        index = data[categoria].index(informacion_vieja)
        data[categoria][index] = informacion_nueva
        doc_ref.set(data) # Aquí sobreescribimos sin el merge para aplicar el cambio exacto
        print(f"🔄 MODIFICADO: '{informacion_vieja}' por '{informacion_nueva}' en '{categoria}'")
        return f"Éxito: Información actualizada en {categoria}."
    return f"Error: No se encontró '{informacion_vieja}' en la categoría '{categoria}'."

def borrar_memoria_permanente(categoria: str, informacion_a_borrar: str) -> str:
    """Elimina por completo un dato de la memoria cuando ya no es relevante (ej. un proyecto terminado)."""
    if not MY_CHAT_ID: return "Error: MY_CHAT_ID no configurado."
    doc_ref = db.collection('perfiles').document(MY_CHAT_ID)
    data = doc_ref.get().to_dict() if doc_ref.get().exists else {}

    if categoria in data and informacion_a_borrar in data[categoria]:
        data[categoria].remove(informacion_a_borrar)
        # Si la categoría se queda vacía, la borramos completa
        if not data[categoria]:
            del data[categoria]
        doc_ref.set(data)
        print(f"🗑️ BORRADO: '{informacion_a_borrar}' de '{categoria}'")
        return f"Éxito: Información borrada de {categoria}."
    return f"Error: No se encontró '{informacion_a_borrar}' en la categoría '{categoria}'."

# =====================================================================

# Inicializar Gemini asignándole TODO el cinturón de herramientas
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    tools=[guardar_memoria_permanente, modificar_memoria_permanente, borrar_memoria_permanente], 
    system_instruction=(
        "Eres el asistente personal avanzado de Mario. Eres proactivo, inteligente y eficiente. "
        "TIENES ACCESO A 3 HERRAMIENTAS DE BASE DE DATOS: "
        "1. 'guardar_memoria_permanente': Para datos nuevos. "
        "2. 'modificar_memoria_permanente': Para actualizar datos obsoletos por nuevos. "
        "3. 'borrar_memoria_permanente': Para eliminar datos que ya no sirven o proyectos terminados. "
        "Úsalas de manera AUTÓNOMA. Mantén tu base de datos limpia, organizada y sin redundancias. "
        "No me preguntes si debes ejecutar la herramienta, hazlo silenciosamente y luego confírmamelo en tu respuesta natural."
    )
)

# --- SERVIDOR FALSO ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot V2.1: CRUD y Memoria Optimizada Activos.")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# --- LÓGICA PROACTIVA ---
async def mensaje_espontaneo(context: ContextTypes.DEFAULT_TYPE):
    if not MY_CHAT_ID: return
    try:
        perfil_ref = db.collection('perfiles').document(MY_CHAT_ID).get()
        contexto_permanente = perfil_ref.to_dict() if perfil_ref.exists else "Aún no hay datos permanentes."

        doc_ref = db.collection('conversaciones').document(MY_CHAT_ID)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)

        prompt_oculto = (
            f"CONTEXTO ACTUAL DE TU BASE DE DATOS (NO LO REPITAS, SOLO ÚSALO): {contexto_permanente} \n\n"
            "Genera un mensaje proactivo y natural para iniciar la conversación. "
            "Si ves algún dato en tu base de datos que podría estar desactualizado, pregúntame por él para usar tus herramientas de limpieza."
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
    await update.message.reply_text("Arquitectura V2.1 lista. Sistema de auto-limpieza y modificación de memoria activado.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        perfil_ref = db.collection('perfiles').document(chat_id).get()
        contexto_permanente = perfil_ref.to_dict() if perfil_ref.exists else "No hay datos."

        doc_ref = db.collection('conversaciones').document(chat_id)
        doc = doc_ref.get()
        historial_firebase = doc.to_dict().get('mensajes', []) if doc.exists else []

        gemini_history = [{"role": msg["role"], "parts": [msg["content"]]} for msg in historial_firebase]
        chat = model.start_chat(history=gemini_history, enable_automatic_function_calling=True)
        
        mensaje_con_contexto = f"[Base de datos actual: {contexto_permanente}]\n\nMensaje: {user_message}"
        
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
    
    application.job_queue.run_repeating(mensaje_espontaneo, interval=28800, first=10) 

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
