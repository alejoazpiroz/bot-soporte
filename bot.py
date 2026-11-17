import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import database

# Configuración de logs para seguimiento en consola durante la defensa
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Reemplazar con el Token entregado por @BotFather en Telegram
TOKEN = "token privdo"

# Definición de los estados de la Máquina de Estados (Memoria del proceso)
ESTADO_INICIO = "INICIO"
ESTADO_ESPERANDO_DNI = "ESPERANDO_DNI"
ESTADO_ESPERANDO_DIAGNOSTICO = "ESPERANDO_DIAGNOSTICO"

# Diccionario en memoria para rastrear el estado y datos temporales de cada chat_id
sesiones_usuarios = {}

def obtener_sesion(chat_id: int) -> dict:
    """Obtiene o inicializa la sesión de un usuario."""
    if chat_id not in sesiones_usuarios:
        sesiones_usuarios[chat_id] = {"estado": ESTADO_INICIO, "dni": None, "nombre": None}
    return sesiones_usuarios[chat_id]

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Evento de Inicio BPMN: Saluda y solicita el DNI."""
    chat_id = update.effective_chat.id
    sesion = obtener_sesion(chat_id)
    sesion["estado"] = ESTADO_ESPERANDO_DNI
    sesion["dni"] = None

    mensaje = (
        "👋 ¡Hola! Bienvenido al *Asistente Virtual de Soporte Técnico de NetNor Fibra S.A.*\n\n"
        "Para comenzar con el diagnóstico de tu servicio, por favor ingresá tu **DNI** (solo números, sin puntos ni espacios).\n"
        "_(Podés escribir /cancelar en cualquier momento para reiniciar)_."
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite abortar el flujo y volver al estado inicial."""
    chat_id = update.effective_chat.id
    sesiones_usuarios[chat_id] = {"estado": ESTADO_INICIO, "dni": None, "nombre": None}
    await update.message.reply_text("🔄 Consulta cancelada. Escribí /start cuando quieras iniciar un nuevo reclamo.")

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Controlador principal de la Máquina de Estados y Gateways BPMN."""
    chat_id = update.effective_chat.id
    texto = update.message.text.strip()
    sesion = obtener_sesion(chat_id)
    estado_actual = sesion["estado"]

    # ---------------------------------------------------------
    # ESTADO 1: INICIO (Si el usuario escribe "Hola" sin /start)
    # ---------------------------------------------------------
    if estado_actual == ESTADO_INICIO:
        await cmd_start(update, context)
        return

    # ---------------------------------------------------------
    # ESTADO 2: ESPERANDO_DNI (Validación + Gateways 1 y 2)
    # ---------------------------------------------------------
    elif estado_actual == ESTADO_ESPERANDO_DNI:
        # Validación de formato (Camino Infeliz: entrada no numérica)
        if not texto.isdigit() or not (7 <= len(texto) <= 8):
            await update.message.reply_text(
                "⚠️ *Error de formato:* El DNI debe contener únicamente entre 7 y 8 números (ej: `11111111`).\n"
                "Por favor, intentá ingresarlo nuevamente:",
                parse_mode="Markdown"
            )
            return  # Mantiene el estado ESPERANDO_DNI

        dni_ingresado = int(texto)
        cliente = database.consultar_cliente(dni_ingresado)

        # GATEWAY 1: ¿Existe el cliente en la Base de Datos?
        if cliente is None:
            await update.message.reply_text(
                "❌ No encontramos ningún titular registrado con el DNI ingresado en NetNor Fibra S.A.\n"
                "Verificá el número y volvé a escribirlo, o usá /cancelar para salir."
            )
            return  # Mantiene el estado ESPERANDO_DNI para reintento

        # Desempaquetar datos obtenidos de SQLite
        dni, nombre, estado_cuenta, saldo_deuda, nodo_id, estado_red, tiempo_estimado = cliente
        sesion["dni"] = dni
        sesion["nombre"] = nombre

        # GATEWAY 2: ¿Estado del servicio? (Mora / Falla Masiva / Activo)
        if estado_cuenta == "MORA":
            await update.message.reply_text(
                f"Hola *{nombre}*. Detectamos que tu cuenta presenta un saldo vencido de *${saldo_deuda:,.2f}*.\n\n"
                "💳 Para restablecer el servicio automáticamente, regularizá tu pago en: https://pagos.netnorfibra.example/abonar\n"
                "_(Proceso finalizado. Escribí /start para realizar otra consulta)_.",
                parse_mode="Markdown"
            )
            sesion["estado"] = ESTADO_INICIO  # Evento de Fin por Mora
            return

        if estado_red == "FALLA_MASIVA":
            await update.message.reply_text(
                f"Hola *{nombre}*. Tu cuenta está al día, pero registramos una *falla masiva en tu zona ({nodo_id})*.\n\n"
                f"🛠️ Nuestro equipo técnico ya está trabajando en el sector. Tiempo estimado de normalización: *{tiempo_estimado}*.\n"
                "No es necesario generar un reclamo individual.\n"
                "_(Proceso finalizado. Escribí /start para realizar otra consulta)_.",
                parse_mode="Markdown"
            )
            sesion["estado"] = ESTADO_INICIO  # Evento de Fin Falla Zonal
            return

        # Si el cliente está ACTIVO y el nodo OPERATIVO -> Avanza al diagnóstico guiado
        sesion["estado"] = ESTADO_ESPERANDO_DIAGNOSTICO
        await update.message.reply_text(
            f"✅ ¡Gracias *{nombre}*! Tu cuenta está activa y no hay cortes reportados en tu zona (*{nodo_id}*).\n\n"
            "Por favor, realizá los siguientes pasos en tu equipo (ONU/Router):\n"
            "1️⃣ Desenchufalo de la corriente por 10 segundos y volvelo a conectar.\n"
            "2️⃣ Esperá 1 minuto y observá las luces LED.\n\n"
            "Respondé con el **número** de lo que ocurre ahora:\n"
            "👉 *1* - Ya volvió internet (funciona correctamente)\n"
            "👉 *2* - La luz roja *LOS* está parpadeando\n"
            "👉 *3* - Las luces están verdes/normales pero sigo sin internet",
            parse_mode="Markdown"
        )
        return

    # ---------------------------------------------------------
    # ESTADO 3: ESPERANDO_DIAGNOSTICO (Gateway 3 y Persistencia)
    # ---------------------------------------------------------
    elif estado_actual == ESTADO_ESPERANDO_DIAGNOSTICO:
        # Validación de opción (Camino Infeliz: texto distinto de 1, 2 o 3)
        if texto not in ("1", "2", "3"):
            await update.message.reply_text(
                "⚠️ *Opción inválida.* Por favor respondé únicamente con el número *1*, *2* o *3* según el estado de tu equipo.",
                parse_mode="Markdown"
            )
            return  # Mantiene el estado ESPERANDO_DIAGNOSTICO

        dni = sesion["dni"]
        nombre = sesion["nombre"]

        # GATEWAY 3: ¿Se resolvió el problema?
        if texto == "1":
            ticket_id = database.crear_ticket(dni, "RESUELTO_EN_LINEA", "CERRADO")
            await update.message.reply_text(
                f"🎉 ¡Excelente, *{nombre}*! Nos alegra que el servicio se haya restablecido.\n"
                f"Registramos la atención bajo el comprobante *#{ticket_id}* (Estado: Cerrado).\n\n"
                "¡Gracias por comunicarte con NetNor Fibra S.A.! Escribí /start si necesitás ayuda nuevamente.",
                parse_mode="Markdown"
            )
        else:
            motivo = "LUZ_ROJA_LOS_FIBRA_CORTADA" if texto == "2" else "SIN_NAVEGACION_LUCES_OK"
            ticket_id = database.crear_ticket(dni, motivo, "DERIVADO_TECNICO")
            await update.message.reply_text(
                f"📋 Entendido, *{nombre}*. Hemos generado automáticamente una orden de visita técnica prioritaria.\n\n"
                f"🆔 *N° de Ticket:* `#{ticket_id}`\n"
                f"🔍 *Diagnóstico:* `{motivo}`\n"
                f"📌 *Estado:* Derivado a cuadrilla técnica\n\n"
                "Un técnico de NetNor Fibra S.A. se contactará dentro de las próximas 24 hs hábiles. ¡Gracias por tu paciencia!",
                parse_mode="Markdown"
            )

        # Evento de Fin: Reiniciar estado del usuario
        sesion["estado"] = ESTADO_INICIO
        sesion["dni"] = None
        sesion["nombre"] = None

def main():
    # Asegurar que la BD exista antes de encender el bot
    database.inicializar_bd()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    print("🤖 Bot de NetNor Fibra S.A. iniciado y escuchando mensajes...")
    app.run_polling()

if __name__ == "__main__":
    main()