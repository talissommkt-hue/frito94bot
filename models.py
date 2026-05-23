# models.py - Funcoes de consulta e manipulacao do banco de dados
import logging
from datetime import date
from database import get_connection
logger = logging.getLogger(__name__)

def registrar_usuario(telegram_id, nome, perfil="operador"):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO usuarios (telegram_id, nome, perfil) VALUES (?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET nome=excluded.nome", (str(telegram_id), nome, perfil))
        conn.commit()
        return buscar_usuario(telegram_id)
    finally:
        conn.close()

def buscar_usuario(telegram_id):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (str(telegram_id),))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def criar_produto(nome, preco_venda, descricao="", categoria_id=None):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO produtos (nome, descricao, preco_venda, categoria_id) VALUES (?, ?, ?, ?)", (nome, descricao, preco_venda, categoria_id))
        conn.commit()
        pid = c.lastrowid
        c.execute("SELECT * FROM produtos WHERE id = ?", (pid,))
        return dict(c.fetchone())
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def listar_produtos(apenas_ativos=True):
    conn = get_connection()
    try:
        c = conn.cursor()
        q = "SELECT p.*, c.nome as categoria_nome FROM produtos p LEFT JOIN categorias c ON p.categoria_id = c.id" + (" WHERE p.ativo = 1" if apenas_ativos else "") + " ORDER BY p.nome"
        c.execute(q)
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()

def buscar_produto(produto_id):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT p.*, cat.nome as categoria_nome FROM produtos p LEFT JOIN categorias cat ON p.categoria_id = cat.id WHERE p.id = ?", (produto_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def calcular_custo_produto(produto_id):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(ft.quantidade * i.custo_unitario), 0) as custo FROM fichas_tecnicas ft JOIN insumos i ON ft.insumo_id = i.id WHERE ft.produto_id = ?", (produto_id,))
        return c.fetchone()["custo"] or 0.0
    finally:
        conn.close()

def criar_insumo(nome, unidade, custo_unitario, estoque_atual=0, estoque_minimo=0):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO insumos (nome, unidade, custo_unitario, estoque_atual, estoque_minimo) VALUES (?, ?, ?, ?, ?)", (nome, unidade, custo_unitario, estoque_atual, estoque_minimo))
        conn.commit()
        iid = c.lastrowid
        c.execute("SELECT * FROM insumos WHERE id = ?", (iid,))
        return dict(c.fetchone())
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def listar_insumos():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM insumos ORDER BY nome")
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()

def buscar_insumo(insumo_id):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM insumos WHERE id = ?", (insumo_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def insumos_abaixo_minimo():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM insumos WHERE estoque_atual <= estoque_minimo ORDER BY nome")
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()

def baixar_estoque_insumos(produto_id, quantidade):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT insumo_id, quantidade FROM fichas_tecnicas WHERE produto_id = ?", (produto_id,))
        for item in c.fetchall():
            conn.execute("UPDATE insumos SET estoque_atual = MAX(0, estoque_atual - ?) WHERE id = ?", (item["quantidade"] * quantidade, item["insumo_id"]))
        conn.commit()
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def criar_ficha_tecnica(produto_id, insumo_id, quantidade):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO fichas_tecnicas (produto_id, insumo_id, quantidade) VALUES (?, ?, ?) ON CONFLICT(produto_id, insumo_id) DO UPDATE SET quantidade=excluded.quantidade", (produto_id, insumo_id, quantidade))
        conn.commit()
        c.execute("SELECT ft.*, p.nome as produto_nome, i.nome as insumo_nome, i.unidade FROM fichas_tecnicas ft JOIN produtos p ON ft.produto_id=p.id JOIN insumos i ON ft.insumo_id=i.id WHERE ft.produto_id=? AND ft.insumo_id=?", (produto_id, insumo_id))
        return dict(c.fetchone())
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def buscar_ficha_tecnica(produto_id):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT ft.*, i.nome as insumo_nome, i.unidade, i.custo_unitario, (ft.quantidade * i.custo_unitario) as custo_item FROM fichas_tecnicas ft JOIN insumos i ON ft.insumo_id=i.id WHERE ft.produto_id=?", (produto_id,))
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()

def criar_pedido(cliente_nome, cliente_telefone, canal, forma_pagamento, taxa_entrega, desconto, subtotal, total, observacao, itens):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COALESCE(MAX(numero_pedido), 0) + 1 FROM pedidos")
        numero = c.fetchone()[0]
        c.execute("INSERT INTO pedidos (numero_pedido, cliente_nome, cliente_telefone, canal, forma_pagamento, taxa_entrega, desconto, subtotal, total, observacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (numero, cliente_nome, cliente_telefone, canal, forma_pagamento, taxa_entrega, desconto, subtotal, total, observacao))
        pedido_id = c.lastrowid
        for item in itens:
            c.execute("INSERT INTO pedido_itens (pedido_id, produto_id, quantidade, preco_unitario, custo_unitario, subtotal) VALUES (?, ?, ?, ?, ?, ?)", (pedido_id, item["produto_id"], item["quantidade"], item["preco_unitario"], item["custo_unitario"], item["subtotal"]))
            baixar_estoque_insumos(item["produto_id"], item["quantidade"])
        c.execute("INSERT INTO caixa_lancamentos (tipo, categoria, descricao, valor, forma_pagamento, pedido_id) VALUES ('entrada', 'venda', ?, ?, ?, ?)", (f"Pedido #{numero} - {cliente_nome}", total, forma_pagamento, pedido_id))
        conn.commit()
        c.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
        return dict(c.fetchone())
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def listar_pedidos_do_dia():
    conn = get_connection()
    try:
        c = conn.cursor()
        hoje = date.today().isoformat()
        c.execute("SELECT p.*, COUNT(pi.id) as total_itens FROM pedidos p LEFT JOIN pedido_itens pi ON p.id=pi.pedido_id WHERE date(p.created_at)=? GROUP BY p.id ORDER BY p.created_at DESC", (hoje,))
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()

def buscar_pedido(pedido_id):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
        p = c.fetchone()
        if not p: return None
        pd = dict(p)
        c.execute("SELECT pi.*, pr.nome as produto_nome FROM pedido_itens pi JOIN produtos pr ON pi.produto_id=pr.id WHERE pi.pedido_id=?", (pedido_id,))
        pd["itens"] = [dict(r) for r in c.fetchall()]
        return pd
    finally:
        conn.close()

def lancar_caixa(tipo, categoria, descricao, valor, forma_pagamento=None, pedido_id=None):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO caixa_lancamentos (tipo, categoria, descricao, valor, forma_pagamento, pedido_id) VALUES (?, ?, ?, ?, ?, ?)", (tipo, categoria, descricao, valor, forma_pagamento, pedido_id))
        conn.commit()
        lid = c.lastrowid
        c.execute("SELECT * FROM caixa_lancamentos WHERE id = ?", (lid,))
        return dict(c.fetchone())
    except:
        conn.rollback(); raise
    finally:
        conn.close()

def resumo_caixa_dia(data=None):
    if not data: data = date.today().isoformat()
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(valor),0) FROM caixa_lancamentos WHERE tipo='entrada' AND data=?", (data,))
        ent = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(valor),0) FROM caixa_lancamentos WHERE tipo='saida' AND data=?", (data,))
        sai = c.fetchone()[0]
        c.execute("SELECT forma_pagamento, COALESCE(SUM(valor),0) as total FROM caixa_lancamentos WHERE tipo='entrada' AND data=? GROUP BY forma_pagamento", (data,))
        pp = {r["forma_pagamento"]: r["total"] for r in c.fetchall()}
        c.execute("SELECT * FROM caixa_lancamentos WHERE data=? ORDER BY created_at DESC LIMIT 10", (data,))
        ul = [dict(r) for r in c.fetchall()]
        return {"data": data, "total_entradas": ent, "total_saidas": sai, "saldo": ent - sai, "por_pagamento": pp, "ultimos_lancamentos": ul}
    finally:
        conn.close()

def calcular_cmv_periodo(data_inicio, data_fim):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT pr.nome as produto_nome, SUM(pi.quantidade) as qtd_vendida, SUM(pi.subtotal) as receita_total, SUM(pi.quantidade * pi.custo_unitario) as custo_total, AVG(pi.preco_unitario) as preco_medio, AVG(pi.custo_unitario) as custo_medio FROM pedido_itens pi JOIN pedidos p ON pi.pedido_id=p.id JOIN produtos pr ON pi.produto_id=pr.id WHERE date(p.created_at) BETWEEN ? AND ? AND p.status != 'cancelado' GROUP BY pi.produto_id ORDER BY custo_total DESC", (data_inicio, data_fim))
        prods = [dict(r) for r in c.fetchall()]
        receita = sum(p["receita_total"] for p in prods)
        custo = sum(p["custo_total"] for p in prods)
        for p in prods:
            p["margem_contribuicao"] = p["preco_medio"] - p["custo_medio"]
            p["margem_percentual"] = ((p["preco_medio"] - p["custo_medio"]) / p["preco_medio"] * 100) if p["preco_medio"] > 0 else 0
        return {"data_inicio": data_inicio, "data_fim": data_fim, "receita_total": receita, "custo_total": custo, "cmv_percentual": (custo/receita*100) if receita > 0 else 0, "lucro_bruto": receita - custo, "produtos": prods}
    finally:
        conn.close()

def gerar_dre(data_inicio, data_fim):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total),0) FROM pedidos WHERE date(created_at) BETWEEN ? AND ?", (data_inicio, data_fim))
        rb = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(total),0) FROM pedidos WHERE date(created_at) BETWEEN ? AND ? AND status='cancelado'", (data_inicio, data_fim))
        canc = c.fetchone()[0]
        rl = rb - canc
        c.execute("SELECT COALESCE(SUM(pi.quantidade * pi.custo_unitario),0) FROM pedido_itens pi JOIN pedidos p ON pi.pedido_id=p.id WHERE date(p.created_at) BETWEEN ? AND ? AND p.status != 'cancelado'", (data_inicio, data_fim))
        cmv = c.fetchone()[0]
        lb = rl - cmv
        c.execute("SELECT categoria, COALESCE(SUM(valor),0) as total FROM caixa_lancamentos WHERE tipo='saida' AND data BETWEEN ? AND ? GROUP BY categoria", (data_inicio, data_fim))
        desp = {r["categoria"]: r["total"] for r in c.fetchall()}
        td = sum(desp.values())
        res = lb - td
        c.execute("SELECT COUNT(*) FROM pedidos WHERE date(created_at) BETWEEN ? AND ? AND status != 'cancelado'", (data_inicio, data_fim))
        np = c.fetchone()[0]
        return {"data_inicio": data_inicio, "data_fim": data_fim, "receita_bruta": rb, "cancelamentos": canc, "receita_liquida": rl, "cmv_total": cmv, "lucro_bruto": lb, "despesas_por_categoria": desp, "total_despesas": td, "resultado_liquido": res, "margem_liquida": (res/rl*100) if rl > 0 else 0, "num_pedidos": np, "ticket_medio": (rl/np) if np > 0 else 0}
    finally:
        conn.close()

def gerar_relatorio_completo(data_inicio, data_fim):
    dre = gerar_dre(data_inicio, data_fim)
    cmv = calcular_cmv_periodo(data_inicio, data_fim)
    alertas = insumos_abaixo_minimo()
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT pr.nome, SUM(pi.quantidade) as qtd, SUM(pi.subtotal) as receita FROM pedido_itens pi JOIN produtos pr ON pi.produto_id=pr.id JOIN pedidos p ON pi.pedido_id=p.id WHERE date(p.created_at) BETWEEN ? AND ? AND p.status != 'cancelado' GROUP BY pi.produto_id ORDER BY qtd DESC LIMIT 5", (data_inicio, data_fim))
        mv = [dict(r) for r in c.fetchall()]
    finally:
        conn.close()
    return {"dre": dre, "cmv": cmv, "alertas_estoque": alertas, "mais_vendidos": mv}

def listar_categorias(apenas_ativas=True):
    conn = get_connection()
    try:
        c = conn.cursor()
        q = "SELECT * FROM categorias" + (" WHERE ativo=1" if apenas_ativas else "") + " ORDER BY nome"
        c.execute(q)
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()
