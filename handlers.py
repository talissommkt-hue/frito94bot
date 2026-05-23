# handlers.py - Todos os handlers dos comandos do bot FRITO94
import logging, os
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from models import (
    registrar_usuario, listar_produtos, criar_produto, criar_insumo, listar_insumos, buscar_insumo,
    criar_ficha_tecnica, buscar_ficha_tecnica, calcular_custo_produto, buscar_produto,
    criar_pedido, listar_pedidos_do_dia, lancar_caixa, resumo_caixa_dia,
    calcular_cmv_periodo, gerar_dre, insumos_abaixo_minimo, gerar_relatorio_completo
)
from openai_client import perguntar_ia

logger = logging.getLogger(__name__)

# Estados ConversationHandler
PEDIDO_CLIENTE, PEDIDO_CANAL, PEDIDO_ITENS, PEDIDO_QUANTIDADE, PEDIDO_PAGAMENTO, PEDIDO_TAXA, PEDIDO_CONFIRMAR = range(7)
PRODUTO_NOME, PRODUTO_PRECO, PRODUTO_DESCRICAO = range(10, 13)
INSUMO_NOME, INSUMO_UNIDADE, INSUMO_CUSTO, INSUMO_ESTOQUE, INSUMO_MINIMO = range(20, 25)
FICHA_PRODUTO, FICHA_INSUMO, FICHA_QUANTIDADE = range(30, 33)
CAIXA_CATEGORIA, CAIXA_DESCRICAO, CAIXA_VALOR = range(40, 43)

def fmt(valor):
    return 'R$ {:,.2f}'.format(valor).replace(',','X').replace('.',',').replace('X','.')

# ==================== START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    tid = str(u.id)
    admin_id = os.getenv('ADMIN_TELEGRAM_ID', '')
    perfil = 'admin' if tid == admin_id else 'operador'
    try: registrar_usuario(tid, u.first_name, perfil)
    except Exception as e: logger.error(f'Erro registro: {e}')
    msg = (f'Ola {u.first_name}! Bem-vindo ao FRITO94 Delivery Bot!\n\n'
           '📦 Comandos:\n'
           '/pedido - Novo pedido\n/pedidos - Pedidos do dia\n'
           '/caixa - Saldo do dia\n/entrada - Lancar entrada\n/saida - Lancar saida\n'
           '/cmv - Ver CMV\n/dre - Ver DRE\n'
           '/estoque - Ver estoque\n/alerta - Alertas\n'
           '/produto - Cadastrar produto\n/insumo - Cadastrar insumo\n/ficha - Ficha tecnica\n'
           '/relatorio - Relatorio completo\n\n'
           'Voce tambem pode me fazer perguntas em linguagem natural!')
    await update.message.reply_text(msg)

# ==================== PEDIDO ====================
async def pedido_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['itens'] = []
    await update.message.reply_text('Novo Pedido\n\nPasso 1/6: Nome do cliente?')
    return PEDIDO_CLIENTE

async def pedido_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cliente_nome'] = update.message.text.strip()
    kb = [[InlineKeyboardButton('Balcao', callback_data='canal_balcao'), InlineKeyboardButton('WhatsApp', callback_data='canal_whatsapp')],
          [InlineKeyboardButton('Link', callback_data='canal_link'), InlineKeyboardButton('Instagram', callback_data='canal_instagram')]]
    await update.message.reply_text(f'Cliente: {context.user_data["cliente_nome"]}\nPasso 2/6: Canal do pedido?', reply_markup=InlineKeyboardMarkup(kb))
    return PEDIDO_CANAL

async def pedido_canal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['canal'] = q.data.replace('canal_', '')
    produtos = listar_produtos(apenas_ativos=True)
    if not produtos:
        await q.edit_message_text('Nenhum produto cadastrado. Use /produto para cadastrar.')
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f'{p["nome"]} - {fmt(p["preco_venda"])}', callback_data=f'prod_{p["id"]}')] for p in produtos]
    kb.append([InlineKeyboardButton('Finalizar itens', callback_data='prod_fim')])
    resumo = ''
    if context.user_data.get('itens'):
        resumo = 'Itens: ' + ', '.join([f'{i["quantidade"]}x prod#{i["produto_id"]}' for i in context.user_data['itens']]) + '\n'
    await q.edit_message_text(f'Canal: {context.user_data["canal"]}\n{resumo}\nPasso 3/6: Selecione um produto:', reply_markup=InlineKeyboardMarkup(kb))
    return PEDIDO_ITENS

async def pedido_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'prod_fim':
        if not context.user_data.get('itens'):
            await q.edit_message_text('Adicione pelo menos um item!')
            return PEDIDO_ITENS
        subtotal = sum(i['subtotal'] for i in context.user_data['itens'])
        context.user_data['subtotal'] = subtotal
        kb = [[InlineKeyboardButton('PIX', callback_data='pag_pix'), InlineKeyboardButton('Dinheiro', callback_data='pag_dinheiro'), InlineKeyboardButton('Cartao', callback_data='pag_cartao')]]
        resumo = 'Itens:\n' + '\n'.join([f'  {i["quantidade"]}x prod#{i["produto_id"]} = {fmt(i["subtotal"])}' for i in context.user_data['itens']])
        await q.edit_message_text(f'{resumo}\nSubtotal: {fmt(subtotal)}\n\nPasso 4/6: Forma de pagamento?', reply_markup=InlineKeyboardMarkup(kb))
        return PEDIDO_PAGAMENTO
    produto_id = int(q.data.replace('prod_', ''))
    produto = buscar_produto(produto_id)
    context.user_data['produto_atual'] = produto_id
    await q.edit_message_text(f'Produto: {produto["nome"]}\nPreco: {fmt(produto["preco_venda"])}\n\nQuantidade?')
    return PEDIDO_QUANTIDADE

async def pedido_quantidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: qtd = int(update.message.text.strip())
    except: await update.message.reply_text('Digite um numero valido.'); return PEDIDO_QUANTIDADE
    if qtd <= 0: await update.message.reply_text('Quantidade deve ser maior que zero.'); return PEDIDO_QUANTIDADE
    pid = context.user_data['produto_atual']
    prod = buscar_produto(pid)
    custo = calcular_custo_produto(pid)
    sub = prod['preco_venda'] * qtd
    itens = context.user_data.get('itens', [])
    existente = next((i for i in itens if i['produto_id'] == pid), None)
    if existente: existente['quantidade'] += qtd; existente['subtotal'] += sub
    else: itens.append({'produto_id': pid, 'quantidade': qtd, 'preco_unitario': prod['preco_venda'], 'custo_unitario': custo, 'subtotal': sub})
    context.user_data['itens'] = itens
    produtos = listar_produtos(apenas_ativos=True)
    kb = [[InlineKeyboardButton(f'{p["nome"]} - {fmt(p["preco_venda"])}', callback_data=f'prod_{p["id"]}')] for p in produtos]
    kb.append([InlineKeyboardButton('Finalizar itens', callback_data='prod_fim')])
    resumo = 'Itens: ' + ', '.join([f'{i["quantidade"]}x prod#{i["produto_id"]}' for i in itens])
    await update.message.reply_text(f'{qtd}x adicionado!\n{resumo}\n\nAdicione mais ou finalize:', reply_markup=InlineKeyboardMarkup(kb))
    return PEDIDO_ITENS

async def pedido_pagamento_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['forma_pagamento'] = q.data.replace('pag_', '')
    canal = context.user_data.get('canal', '')
    sug = '0' if canal == 'balcao' else '5.00'
    await q.edit_message_text(f'Pagamento: {context.user_data["forma_pagamento"]}\n\nPasso 5/6: Taxa de entrega? (ex: 5.00 ou 0)\nSugestao: R$ {sug}')
    return PEDIDO_TAXA

async def pedido_taxa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: taxa = float(update.message.text.strip().replace(',', '.'))
    except: await update.message.reply_text('Digite um valor valido. Ex: 5.00'); return PEDIDO_TAXA
    context.user_data['taxa_entrega'] = taxa
    sub = context.user_data.get('subtotal', 0)
    total = sub + taxa
    context.user_data['total'] = total
    resumo = (f'RESUMO DO PEDIDO\n'
              f'Cliente: {context.user_data["cliente_nome"]}\n'
              f'Canal: {context.user_data["canal"]}\n'
              f'Pagamento: {context.user_data["forma_pagamento"]}\n\n'
              f'Subtotal: {fmt(sub)}\n'
              f'Taxa: {fmt(taxa)}\n'
              f'TOTAL: {fmt(total)}')
    kb = [[InlineKeyboardButton('CONFIRMAR', callback_data='pedido_confirmar'), InlineKeyboardButton('Cancelar', callback_data='pedido_cancelar')]]
    await update.message.reply_text(resumo, reply_markup=InlineKeyboardMarkup(kb))
    return PEDIDO_CONFIRMAR

async def pedido_confirmar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'pedido_cancelar':
        context.user_data.clear()
        await q.edit_message_text('Pedido cancelado.')
        return ConversationHandler.END
    try:
        pedido = criar_pedido(
            cliente_nome=context.user_data['cliente_nome'],
            cliente_telefone='',
            canal=context.user_data['canal'],
            forma_pagamento=context.user_data['forma_pagamento'],
            taxa_entrega=context.user_data['taxa_entrega'],
            desconto=0,
            subtotal=context.user_data['subtotal'],
            total=context.user_data['total'],
            observacao='',
            itens=context.user_data['itens']
        )
        await q.edit_message_text(f'Pedido #{pedido["numero_pedido"]} registrado!\nCliente: {pedido["cliente_nome"]}\nTotal: {fmt(pedido["total"])}\nEstoque baixado e caixa atualizado automaticamente.')
    except Exception as e:
        logger.error(f'Erro ao salvar pedido: {e}')
        await q.edit_message_text(f'Erro ao salvar pedido: {str(e)}')
    context.user_data.clear()
    return ConversationHandler.END

async def pedido_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text('Operacao cancelada.')
    return ConversationHandler.END

# ==================== LISTAR PEDIDOS ====================
async def listar_pedidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pedidos = listar_pedidos_do_dia()
    if not pedidos:
        await update.message.reply_text('Nenhum pedido hoje.')
        return
    status_e = {'recebido':'📥','em_preparo':'👨‍🍳','pronto':'✅','entregue':'🏍️','cancelado':'❌'}
    total = sum(p['total'] for p in pedidos if p['status'] != 'cancelado')
    msg = f'PEDIDOS HOJE - {date.today().strftime("%d/%m/%Y")}\n'
    for p in pedidos:
        e = status_e.get(p['status'], '📦')
        msg += f'{e} #{p["numero_pedido"]} - {p["cliente_nome"]} | {fmt(p["total"])} | {p["canal"]} | {p["forma_pagamento"]}\n'
    msg += f'\nTotal: {len([p for p in pedidos if p["status"] != "cancelado"])} pedidos | Faturamento: {fmt(total)}'
    await update.message.reply_text(msg)

# ==================== CAIXA ====================
async def ver_caixa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = resumo_caixa_dia()
    pp = c.get('por_pagamento', {})
    msg = (f'CAIXA DO DIA - {c["data"]}\n'
           f'Entradas: {fmt(c["total_entradas"])}\n'
           f'  PIX: {fmt(pp.get("pix",0))}\n'
           f'  Dinheiro: {fmt(pp.get("dinheiro",0))}\n'
           f'  Cartao: {fmt(pp.get("cartao",0))}\n'
           f'Saidas: {fmt(c["total_saidas"])}\n'
           f'SALDO: {fmt(c["saldo"])}')
    await update.message.reply_text(msg)

# ==================== LANCAMENTOS ====================
async def lancamento_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = 'entrada' if '/entrada' in update.message.text.lower() else 'saida'
    context.user_data['lancamento_tipo'] = tipo
    cats_e = ['venda', 'outro']
    cats_s = ['compra_insumo','despesa_fixa','despesa_variavel','taxa_plataforma','salario','outro']
    cats = cats_e if tipo == 'entrada' else cats_s
    kb = [[InlineKeyboardButton(cat, callback_data=f'cat_{cat}')] for cat in cats]
    await update.message.reply_text(f'Lancamento de {tipo.upper()}\n\nSelecione a categoria:', reply_markup=InlineKeyboardMarkup(kb))
    return CAIXA_CATEGORIA

async def lancamento_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['lancamento_categoria'] = q.data.replace('cat_', '')
    await q.edit_message_text(f'Categoria: {context.user_data["lancamento_categoria"]}\n\nDescricao do lancamento?')
    return CAIXA_DESCRICAO

async def lancamento_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['lancamento_descricao'] = update.message.text.strip()
    await update.message.reply_text('Valor? (ex: 50.00)')
    return CAIXA_VALOR

async def lancamento_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: valor = float(update.message.text.strip().replace(',', '.'))
    except: await update.message.reply_text('Valor invalido. Ex: 50.00'); return CAIXA_VALOR
    tipo = context.user_data['lancamento_tipo']
    try:
        lancar_caixa(tipo=tipo, categoria=context.user_data['lancamento_categoria'], descricao=context.user_data['lancamento_descricao'], valor=valor)
        e = '📈' if tipo == 'entrada' else '📉'
        await update.message.reply_text(f'{e} Lancamento registrado!\nTipo: {tipo}\nValor: {fmt(valor)}')
    except Exception as ex:
        await update.message.reply_text(f'Erro: {str(ex)}')
    context.user_data.clear()
    return ConversationHandler.END

# ==================== CMV ====================
async def ver_cmv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = date.today().isoformat()
    ini = date.today().replace(day=1).isoformat()
    cmv = calcular_cmv_periodo(ini, hoje)
    msg = (f'CMV DO MES ({ini} a {hoje})\n'
           f'Receita: {fmt(cmv["receita_total"])}\n'
           f'CMV: {fmt(cmv["custo_total"])} ({cmv["cmv_percentual"]:.1f}%)\n'
           f'Lucro Bruto: {fmt(cmv["lucro_bruto"])}\n\n'
           f'POR PRODUTO:\n')
    for p in cmv['produtos']:
        msg += f'  {p["produto_nome"]}: CMV {fmt(p["custo_total"])} | Margem {p["margem_percentual"]:.1f}%\n'
    await update.message.reply_text(msg)

# ==================== DRE ====================
async def ver_dre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    hoje = date.today().isoformat()
    if args and args[0] == 'semana':
        ini = (date.today() - timedelta(days=7)).isoformat()
    elif args and args[0] == 'dia':
        ini = hoje
    else:
        ini = date.today().replace(day=1).isoformat()
    dre = gerar_dre(ini, hoje)
    msg = (f'DRE ({ini} a {hoje})\n'
           f'Receita Bruta: {fmt(dre["receita_bruta"])}\n'
           f'(-) Cancelamentos: {fmt(dre["cancelamentos"])}\n'
           f'= Receita Liquida: {fmt(dre["receita_liquida"])}\n'
           f'(-) CMV: {fmt(dre["cmv_total"])}\n'
           f'= Lucro Bruto: {fmt(dre["lucro_bruto"])}\n'
           f'(-) Despesas: {fmt(dre["total_despesas"])}\n'
           f'= Resultado: {fmt(dre["resultado_liquido"])}\n'
           f'Margem: {dre["margem_liquida"]:.1f}%\n'
           f'Pedidos: {dre["num_pedidos"]} | Ticket Medio: {fmt(dre["ticket_medio"])}')
    await update.message.reply_text(msg)

# ==================== ESTOQUE ====================
async def ver_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    insumos = listar_insumos()
    if not insumos:
        await update.message.reply_text('Nenhum insumo cadastrado.')
        return
    msg = 'ESTOQUE DE INSUMOS\n'
    for i in insumos:
        status = '⚠️' if i['estoque_atual'] <= i['estoque_minimo'] else '✅'
        msg += f'{status} {i["nome"]}: {i["estoque_atual"]} {i["unidade"]} (min: {i["estoque_minimo"]})\n'
    await update.message.reply_text(msg)

async def ver_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alertas = insumos_abaixo_minimo()
    if not alertas:
        await update.message.reply_text('Todos os insumos estao acima do minimo!')
        return
    msg = f'ALERTAS DE ESTOQUE ({len(alertas)} insumos)\n'
    for a in alertas:
        msg += f'⚠️ {a["nome"]}: {a["estoque_atual"]} {a["unidade"]} (min: {a["estoque_minimo"]})\n'
    await update.message.reply_text(msg)

# ==================== RELATORIO ====================
async def ver_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = date.today().isoformat()
    ini = date.today().replace(day=1).isoformat()
    rel = gerar_relatorio_completo(ini, hoje)
    dre = rel['dre']
    msg = (f'RELATORIO COMPLETO - {ini} a {hoje}\n\n'
           f'FINANCEIRO:\n'
           f'Receita: {fmt(dre["receita_liquida"])} | CMV: {fmt(dre["cmv_total"])} | Lucro: {fmt(dre["lucro_bruto"])}\n'
           f'Despesas: {fmt(dre["total_despesas"])} | Resultado: {fmt(dre["resultado_liquido"])} | Margem: {dre["margem_liquida"]:.1f}%\n\n'
           f'PEDIDOS: {dre["num_pedidos"]} | Ticket Medio: {fmt(dre["ticket_medio"])}\n\n'
           f'MAIS VENDIDOS:\n')
    for mv in rel.get('mais_vendidos', []):
        msg += f'  {mv["nome"]}: {mv["qtd"]}x | {fmt(mv["receita"])}\n'
    if rel.get('alertas_estoque'):
        msg += f'\nALERTAS ESTOQUE: {len(rel["alertas_estoque"])} insumos em falta'
    await update.message.reply_text(msg)

# ==================== CADASTRO PRODUTO ====================
async def produto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text('Novo Produto\n\nNome do produto?')
    return PRODUTO_NOME

async def produto_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['produto_nome'] = update.message.text.strip()
    await update.message.reply_text(f'Produto: {context.user_data["produto_nome"]}\n\nPreco de venda? (ex: 15.00)')
    return PRODUTO_PRECO

async def produto_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'produto_preco' not in context.user_data:
        try: context.user_data['produto_preco'] = float(update.message.text.strip().replace(',','.'))
        except: await update.message.reply_text('Preco invalido.'); return PRODUTO_PRECO
        await update.message.reply_text('Descricao do produto? (ou /pular para deixar em branco)')
        return PRODUTO_DESCRICAO
    descricao = '' if update.message.text.strip() == '/pular' else update.message.text.strip()
    try:
        prod = criar_produto(nome=context.user_data['produto_nome'], preco_venda=context.user_data['produto_preco'], descricao=descricao)
        await update.message.reply_text(f'Produto cadastrado!\n{prod["nome"]} - {fmt(prod["preco_venda"])}')
    except Exception as e:
        await update.message.reply_text(f'Erro: {str(e)}')
    context.user_data.clear()
    return ConversationHandler.END

# ==================== CADASTRO INSUMO ====================
async def insumo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text('Novo Insumo\n\nNome do insumo?')
    return INSUMO_NOME

async def insumo_unidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['insumo_nome'] = update.message.text.strip()
    kb = [[InlineKeyboardButton(u, callback_data=f'un_{u}')] for u in ['kg','g','ml','L','unidade']]
    await update.message.reply_text('Unidade de medida?', reply_markup=InlineKeyboardMarkup(kb))
    return INSUMO_UNIDADE

async def insumo_custo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['insumo_unidade'] = q.data.replace('un_', '')
    await q.edit_message_text(f'Unidade: {context.user_data["insumo_unidade"]}\n\nCusto unitario? (ex: 2.50)')
    return INSUMO_CUSTO

async def insumo_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: context.user_data['insumo_custo'] = float(update.message.text.strip().replace(',','.'))
    except: await update.message.reply_text('Custo invalido.'); return INSUMO_CUSTO
    await update.message.reply_text('Estoque atual? (ex: 10.0)')
    return INSUMO_ESTOQUE

async def insumo_minimo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'insumo_estoque' not in context.user_data:
        try: context.user_data['insumo_estoque'] = float(update.message.text.strip().replace(',','.'))
        except: await update.message.reply_text('Valor invalido.'); return INSUMO_ESTOQUE
        await update.message.reply_text('Estoque minimo? (ex: 2.0)')
        return INSUMO_MINIMO
    try:
        minimo = float(update.message.text.strip().replace(',','.'))
        ins = criar_insumo(nome=context.user_data['insumo_nome'], unidade=context.user_data['insumo_unidade'], custo_unitario=context.user_data['insumo_custo'], estoque_atual=context.user_data['insumo_estoque'], estoque_minimo=minimo)
        await update.message.reply_text(f'Insumo cadastrado!\n{ins["nome"]} | {ins["unidade"]} | R${ins["custo_unitario"]}')
    except Exception as e:
        await update.message.reply_text(f'Erro: {str(e)}')
    context.user_data.clear()
    return ConversationHandler.END

# ==================== FICHA TECNICA ====================
async def ficha_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    produtos = listar_produtos()
    if not produtos: await update.message.reply_text('Nenhum produto cadastrado.'); return ConversationHandler.END
    kb = [[InlineKeyboardButton(p['nome'], callback_data=f'fp_{p["id"]}')] for p in produtos]
    await update.message.reply_text('Ficha Tecnica\n\nSelecione o produto:', reply_markup=InlineKeyboardMarkup(kb))
    return FICHA_PRODUTO

async def ficha_insumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['ficha_produto_id'] = int(q.data.replace('fp_', ''))
    insumos = listar_insumos()
    if not insumos: await q.edit_message_text('Nenhum insumo cadastrado.'); return ConversationHandler.END
    kb = [[InlineKeyboardButton(f'{i["nome"]} ({i["unidade"]})', callback_data=f'fi_{i["id"]}')] for i in insumos]
    await q.edit_message_text('Selecione o insumo:', reply_markup=InlineKeyboardMarkup(kb))
    return FICHA_INSUMO

async def ficha_quantidade(update, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(update, 'callback_query') and update.callback_query:
        q = update.callback_query
        await q.answer()
        context.user_data['ficha_insumo_id'] = int(q.data.replace('fi_', ''))
        insumo = buscar_insumo(context.user_data['ficha_insumo_id'])
        await q.edit_message_text(f'Insumo: {insumo["nome"]}\n\nQuantidade por unidade do produto? (em {insumo["unidade"]})')
        return FICHA_QUANTIDADE
    try: qtd = float(update.message.text.strip().replace(',','.'))
    except: await update.message.reply_text('Valor invalido.'); return FICHA_QUANTIDADE
    try:
        ft = criar_ficha_tecnica(produto_id=context.user_data['ficha_produto_id'], insumo_id=context.user_data['ficha_insumo_id'], quantidade=qtd)
        custo = calcular_custo_produto(context.user_data['ficha_produto_id'])
        await update.message.reply_text(f'Ficha tecnica salva!\nProduto: {ft["produto_nome"]}\nInsumo: {ft["insumo_nome"]}\nQtd: {qtd} {ft["unidade"]}\nCusto total produto: {fmt(custo)}')
    except Exception as e:
        await update.message.reply_text(f'Erro: {str(e)}')
    context.user_data.clear()
    return ConversationHandler.END

# ==================== MENSAGEM LIVRE (IA) ====================
async def mensagem_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    await update.message.reply_text('Consultando IA...')
    try:
        resposta = perguntar_ia(texto)
        await update.message.reply_text(resposta)
    except Exception as e:
        await update.message.reply_text(f'Erro ao consultar IA: {str(e)}')
