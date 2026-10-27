import logging
from datetime import datetime
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
import gspread
from google.oauth2.service_account import Credentials

# Configuração de logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONEXÃO COM O GOOGLE SHEETS ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS = Credentials.from_service_account_file("credenciais.json", scopes=SCOPES)
CLIENT = gspread.authorize(CREDS)

# Abre a planilha pelo nome exato
SHEET = CLIENT.open("Controle de Visitas - Equipe").worksheet("Visitas")

# Estados atualizados da Conversa
(
    ESCOLHER_TIPO, 
    CLIENTE_FORA_NOME, 
    RECEBER_GPS, 
    RECEBER_FOTO, 
    RECEBER_STATUS, 
    PEDIR_COMPRADOR, 
    PEDIR_VALOR, 
    PEDIR_OBS
) = range(8)

async def start(update, context):
    user = update.effective_user
    context.user_data['vendedor'] = user.first_name
    
    teclado = [['🗺️ Minha Rota', '⚡ Fora da Rota']]
    await update.message.reply_text(
        f"Olá, {user.first_name}! Bem-vindo ao Bela vista controle de visitas.\n\nEscolha uma opção abaixo:",
        reply_markup=ReplyKeyboardMarkup(teclado, one_time_keyboard=True, resize_keyboard=True)
    )
    return ESCOLHER_TIPO

async def escolher_tipo(update, context):
    texto = update.message.text
    if "Minha Rota" in texto:
        context.user_data['tipo'] = 'Rota'
        await update.message.reply_text("Digite o **nome do cliente** da sua lista de hoje:", reply_markup=ReplyKeyboardRemove())
        return CLIENTE_FORA_NOME
    elif "Fora da Rota" in texto:
        context.user_data['tipo'] = 'Fora da Rota'
        await update.message.reply_text("Você está em uma visita espontânea!\n\nDigite o **nome do estabelecimento**:", reply_markup=ReplyKeyboardRemove())
        return CLIENTE_FORA_NOME

async def receber_nome_cliente(update, context):
    context.user_data['cliente'] = update.message.text
    await update.message.reply_text(
        "Perfeito! 📍 Agora clique no clipe 📎 no Telegram, vá em **Localização** e envie sua **Localização Atual**."
    )
    return RECEBER_GPS

async def receber_gps(update, context):
    if not update.message.location:
        await update.message.reply_text("Por favor, envie a localização usando o botão de GPS do Telegram.")
        return RECEBER_GPS
        
    context.user_data['lat'] = update.message.location.latitude
    context.user_data['lon'] = update.message.location.longitude
    
    await update.message.reply_text("Localização capturada! 📍\n\nAgora, envie a **foto da fachada** do estabelecimento (tire direto pela câmera do Telegram).")
    return RECEBER_FOTO

async def receber_foto(update, context):
    if not update.message.photo:
        await update.message.reply_text("Por favor, envie uma foto válida do estabelecimento.")
        return RECEBER_FOTO
        
    foto_file = update.message.photo[-1]
    context.user_data['foto'] = f"Foto ID: {foto_file.file_id}"
    
    teclado_status = [
        ['✅ Venda Realizada', '📦 Estoque Cheio'],
        ['🚪 Fechado / Ausente', '🔄 Retornar Outro Dia']
    ]
    await update.message.reply_text(
        "Foto recebida com sucesso! 📸\n\nQual foi o **resultado / status** da visita?",
        reply_markup=ReplyKeyboardMarkup(teclado_status, one_time_keyboard=True, resize_keyboard=True)
    )
    return RECEBER_STATUS

async def receber_status(update, context):
    status = update.message.text
    context.user_data['status'] = status
    
    if "Venda Realizada" in status:
        await update.message.reply_text(
            "💰 Ótima notícia!\n\nPor favor, digite o **nome do comprador** responsável:",
            reply_markup=ReplyKeyboardRemove()
        )
        return PEDIR_COMPRADOR
    else:
        context.user_data['comprador'] = "-"
        context.user_data['valor'] = "-"
        context.user_data['obs'] = "Nenhuma observação extra"
        return await finalizar_e_salvar(update, context)

async def pedir_comprador(update, context):
    context.user_data['comprador'] = update.message.text
    await update.message.reply_text("Qual foi o **valor do pedido**? (Ex: 350.00 ou 1200):")
    return PEDIR_VALOR

async def pedir_valor(update, context):
    context.user_data['valor'] = update.message.text
    await update.message.reply_text("Deseja deixar alguma **observação** sobre o pedido ou cliente? (Se não houver, digite 'Nenhuma'):")
    return PEDIR_OBS

async def pedir_obs(update, context):
    context.user_data['obs'] = update.message.text
    return await finalizar_e_salvar(update, context)

async def finalizar_e_salvar(update, context):
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    vendedor = context.user_data.get('vendedor', '')
    tipo = context.user_data.get('tipo', '')
    cliente = context.user_data.get('cliente', '')
    status = context.user_data.get('status', '')
    comprador = context.user_data.get('comprador', '-')
    valor = context.user_data.get('valor', '-')
    lat = str(context.user_data.get('lat', ''))
    lon = str(context.user_data.get('lon', ''))
    foto = context.user_data.get('foto', '')
    obs = context.user_data.get('obs', 'Nenhuma observação extra')
    
    # --- GRAVA NA PLANILHA GOOGLE SHEETS ---
    SHEET.append_row([
        data_hora,   # A
        vendedor,    # B
        tipo,        # C
        cliente,     # D
        status,      # E
        comprador,   # F
        str(valor),  # G
        lat,         # H
        lon,         # I
        foto,        # J
        obs          # K
    ])
    
    await update.message.reply_text(
        "✅ **Visita e pedido registados com sucesso na planilha!**\n\nBom trabalho e bora para proxima venda! 🚀",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def cancelar(update, context):
    await update.message.reply_text("Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    TELEGRAM_TOKEN = "8954673009:AAFqLvqHiMufxBXEB9CrnrS_A5gk8G2LjSM"
    
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    conv_handler = ConversationHandler(
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
    )
    
    application.add_handler(conv_handler)
    
    print("Bot pronto!")
    application.run_polling()

if __name__ == '__main__':
    main()