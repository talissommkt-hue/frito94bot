# main.py - Arquivo principal do bot FRITO94
import logging, os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from database import criar_tabelas
from handlers import (
    start, pedido_start, pedido_canal, pedido_canal_callback, pedido_item_callback,
    pedido_quantidade, pedido_pagamento_callback, pedido_taxa, pedido_confirmar_callback, pedido_cancelar,
    listar_pedidos, ver_caixa, lancamento_start, lancamento_categoria_callback,
    lancamento_descricao, lancamento_valor,
    ver_cmv, ver_dre, ver_estoque, ver_alertas, ver_relatorio,
    produto_start, produto_preco, produto_descricao,
    insumo_start, insumo_unidade, insumo_custo, insumo_estoque, insumo_minimo,
    ficha_start, ficha_insumo, ficha_quantidade,
    mensagem_livre,
    PEDIDO_CLIENTE, PEDIDO_CANAL, PEDIDO_ITENS, PEDIDO_QUANTIDADE,
    PEDIDO_PAGAMENTO, PEDIDO_TAXA, PEDIDO_CONFIRMAR,
    PRODUTO_NOME, PRODUTO_PRECO, PRODUTO_DESCRICAO,
    INSUMO_NOME, INSUMO_UNIDADE, INSUMO_CUSTO, INSUMO_ESTOQUE, INSUMO_MINIMO,
    FICHA_PRODUTO, FICHA_INSUMO, FICHA_QUANTIDADE,
    CAIXA_CATEGORIA, CAIXA_DESCRICAO, CAIXA_VALOR
)

load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    criar_tabelas()
    logger.info('Banco de dados inicializado')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError('TELEGRAM_BOT_TOKEN nao encontrado no .env')
    app = Application.builder().token(token).build()

    # ConversationHandler para /pedido
    conv_pedido = ConversationHandler(
        entry_points=[CommandHandler('pedido', pedido_start)],
        states={
            PEDIDO_CLIENTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedido_canal)],
            PEDIDO_CANAL: [CallbackQueryHandler(pedido_canal_callback, pattern='^canal_')],
            PEDIDO_ITENS: [CallbackQueryHandler(pedido_item_callback, pattern='^prod_')],
            PEDIDO_QUANTIDADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedido_quantidade)],
            PEDIDO_PAGAMENTO: [CallbackQueryHandler(pedido_pagamento_callback, pattern='^pag_')],
            PEDIDO_TAXA: [MessageHandler(filters.TEXT & ~filters.COMMAND, pedido_taxa)],
            PEDIDO_CONFIRMAR: [CallbackQueryHandler(pedido_confirmar_callback, pattern='^pedido_')],
        },
        fallbacks=[CommandHandler('cancelar', pedido_cancelar)],
    )

    # ConversationHandler para /produto
    conv_produto = ConversationHandler(
        entry_points=[CommandHandler('produto', produto_start)],
        states={
            PRODUTO_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, produto_preco)],
            PRODUTO_PRECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, produto_descricao)],
            PRODUTO_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, produto_descricao)],
        },
        fallbacks=[CommandHandler('cancelar', pedido_cancelar)],
    )

    # ConversationHandler para /insumo
    conv_insumo = ConversationHandler(
        entry_points=[CommandHandler('insumo', insumo_start)],
        states={
            INSUMO_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, insumo_unidade)],
            INSUMO_UNIDADE: [CallbackQueryHandler(insumo_custo, pattern='^un_')],
            INSUMO_CUSTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, insumo_estoque)],
            INSUMO_ESTOQUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, insumo_minimo)],
            INSUMO_MINIMO: [MessageHandler(filters.TEXT & ~filters.COMMAND, insumo_minimo)],
        },
        fallbacks=[CommandHandler('cancelar', pedido_cancelar)],
    )

    # ConversationHandler para /ficha
    conv_ficha = ConversationHandler(
        entry_points=[CommandHandler('ficha', ficha_start)],
        states={
            FICHA_PRODUTO: [CallbackQueryHandler(ficha_insumo, pattern='^fp_')],
            FICHA_INSUMO: [CallbackQueryHandler(ficha_quantidade, pattern='^fi_')],
            FICHA_QUANTIDADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ficha_quantidade)],
        },
        fallbacks=[CommandHandler('cancelar', pedido_cancelar)],
    )

    # ConversationHandler para /entrada e /saida
    conv_caixa = ConversationHandler(
        entry_points=[CommandHandler('entrada', lancamento_start), CommandHandler('saida', lancamento_start)],
        states={
            CAIXA_CATEGORIA: [CallbackQueryHandler(lancamento_categoria_callback, pattern='^cat_')],
            CAIXA_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, lancamento_descricao)],
            CAIXA_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, lancamento_valor)],
        },
        fallbacks=[CommandHandler('cancelar', pedido_cancelar)],
    )

    # Comandos simples
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('pedidos', listar_pedidos))
    app.add_handler(CommandHandler('caixa', ver_caixa))
    app.add_handler(CommandHandler('cmv', ver_cmv))
    app.add_handler(CommandHandler('dre', ver_dre))
    app.add_handler(CommandHandler('estoque', ver_estoque))
    app.add_handler(CommandHandler('alerta', ver_alertas))
    app.add_handler(CommandHandler('relatorio', ver_relatorio))

    # Conversation handlers
    app.add_handler(conv_pedido)
    app.add_handler(conv_produto)
    app.add_handler(conv_insumo)
    app.add_handler(conv_ficha)
    app.add_handler(conv_caixa)

    # Mensagens livres (IA)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem_livre))

    logger.info('Bot FRITO94 iniciado!')
    app.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()
