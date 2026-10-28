# Servidor Flask para manter o Render ativo e receber Webhooks
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot Online!"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    import asyncio
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    
    # Executa a atualização de forma segura sem fechar o loop global
    async def process_update():
        await application.initialize()
        await application.process_update(update)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(process_update(), loop)
        else:
            asyncio.run(process_update())
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        
    return 'ok'

if __name__ == '__main__':
    import asyncio
    async def setup_webhook():
        await application.initialize()
        await application.bot.set_webhook(url=f"{RENDER_URL}/{TELEGRAM_TOKEN}")
    
    try:
        asyncio.run(setup_webhook())
    except Exception as e:
        logger.error(f"Erro ao configurar webhook: {e}")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
