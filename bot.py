import os
import json
import sys
import logging
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8954673009:AAFqLvqHiMufxBXEB9CrnrS_A5gk8G2LjSM"
RENDER_URL = "https://bot-visitasbelavista-1.onrender.com"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

print("Verificando credenciais...")
if "GOOGLE_CREDENTIALS_JSON" not in os.environ:
    print("ERRO FATAL: Variável GOOGLE_CREDENTIALS_JSON não encontrada!")
    sys.exit(1)

try:
    creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    private_key = creds_info.get("private_key", "")
    creds_info["private_key"] = private_key.replace("\\n", "\n")
    
    print(f"Chave carregada! ID: {creds_info.get('private_key_id', 'Desconhecido')}")
    
    CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    CLIENT = gspread.authorize(CREDS)
    SHEET = CLIENT.open("Controle de Visitas - Equipe").worksheet("Visitas")
    print("SUCESSO: Conectado ao Google Sheets!")
except Exception as e:
    print(f"ERRO DE AUTENTICAÇÃO: {e}")
    sys.exit(1)

# Estados da Conversa
(
    ESCOLHER_TIPO, CLIENTE_FORA_NOME, RECEBER_GPS, RECEBER_FOTO, 
    RECEBER_STATUS, PEDIR_COMPRADOR, PEDIR_VALOR, PEDIR_OBS
) = range(8)

async def start(update: Update, context):
    user = update.effective_user
    context.user_data['vendedor'] = user.first_name
    teclado = [['🗺️ Minha Rota', '⚡ Fora da Rota']]
    await update.message.reply_text(
        f"Olá, {user.first_name}! Escolha uma opção abaixo:",
        reply_markup=ReplyKeyboardMarkup(teclado, one_time_keyboard=True, resize_keyboard=True)
    )
    return ESCOLHER_TIPO

async def escolher_tipo(update: Update, context):
    texto = update.message.text
    if "Minha Rota" in texto:
        context.user_data['tipo'] = 'Rota'
        await update.message.reply_text("Digite o **nome do cliente** da sua lista:", reply_markup=ReplyKeyboardRemove())
        return CLIENTE_FORA_NOME
    elif "Fora da Rota" in texto:
        context.user_data['tipo'] = 'Fora da Rota'
        await update.message.reply_text("Digite o **nome do estabelecimento**:", reply_markup=ReplyKeyboardRemove())
        return CLIENTE_FORA_NOME

async def receber_nome_cliente(update: Update, context):
    context.user_data['cliente'] = update.message.text
    await update.message.reply_text("Agora envie sua **Localização Atual**.")
    return RECEBER_GPS

async def receber_gps(update: Update, context):
    if not update.message.location:
        return RECEBER_GPS
    context.user_data['lat'] = update.message.location.latitude
    context.user_data['lon'] = update.message.location.longitude
    await update.message.reply_text("Agora, envie a **foto da fachada**.")
    return RECEBER_FOTO

async def receber_foto(update: Update, context):
    if not update.message.photo:
        return RECEBER_FOTO
    context.user_data['foto'] = f"Foto ID: {update.message.photo[-1].file_id}"
    teclado_status = [['✅ Venda Realizada', '📦 Estoque Cheio'], ['🚪 Fechado', '🔄 Retornar']]
    await update.message.reply_text("Qual foi o **status** da visita?", reply_markup=ReplyKeyboardMarkup(teclado_status, one_time_keyboard=True, resize_keyboard=True))
    return RECEBER_STATUS

async def receber_status(update: Update, context):
    status = update.message.text
    context.user_data['status'] = status
    if "Venda Realizada" in status:
        await update.message.reply_text("Digite o **nome do comprador**:", reply_markup=ReplyKeyboardRemove())
        return PEDIR_COMPRADOR
    else:
        context.user_data['comprador'], context.user_data['valor'], context.user_data['obs'] = "-", "-", "Nenhuma observação extra"
        return await finalizar_e_salvar(update, context)

async def pedir_comprador(update: Update, context):
    context.user_data['comprador'] = update.message.text
    await update.message.reply_text("Qual foi o **valor do pedido**?")
    return PEDIR_VALOR

async def pedir_valor(update: Update, context):
    context.user_data['valor'] = update.message.text
    await update.message.reply_text("Deseja deixar alguma **observação**?")
    return PEDIR_OBS

async def pedir_obs(update: Update, context):
    context.user_data['obs'] = update.message.text
    return await finalizar_e_salvar(update, context)

async def finalizar_e_salvar(update: Update, context):
    from datetime import datetime
    try:
        SHEET.append_row([
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"), context.user_data.get('vendedor', ''), context.user_data.get('tipo', ''),
            context.user_data.get('cliente', ''), context.user_data.get('status', ''), context.user_data.get('comprador', '-'),
            str(context.user_data.get('valor', '-')), str(context.user_data.get('lat', '')), str(context.user_data.get('lon', '')),
            context.user_data.get('foto', ''), context.user_data.get('obs', 'Nenhuma observação extra')
        ])
        await update.message.reply_text("✅ **Visita registada com sucesso!**", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao salvar: {e}")
    return ConversationHandler.END

async def cancelar(update: Update, context):
    await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        ESCOLHER_TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
        CLIENTE_FORA_NOME: [MessageHandler(filters.TEXT & ~filters.command, receber_nome_cliente)],
        RECEBER_GPS: [MessageHandler(filters.LOCATION, receber_gps)],
        RECEBER_FOTO: [MessageHandler(filters.PHOTO, receber_foto)],
        RECEBER_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_status)],
        PEDIR_COMPRADOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedir_comprador)],
        PEDIR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedir_valor)],
        PEDIR_OBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedir_obs)],
    },
    fallbacks=[CommandHandler('cancel', cancelar)]
))

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot Online!"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    import asyncio
    update = Update.de_json(request.get_json(force=True), application.bot)
    async def process():
        await application.initialize()
        await application.process_update(update)
    asyncio.run(process())
    return 'ok'

if __name__ == '__main__':
    import asyncio
    async def setup_webhook():
        await application.initialize()
        await application.bot.set_webhook(url=f"{RENDER_URL}/{TELEGRAM_TOKEN}")
    asyncio.run(setup_webhook())
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
