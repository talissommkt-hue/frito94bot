# database.py - Criacao e conexao com o banco de dados SQLite
import sqlite3
import logging

logger = logging.getLogger(__name__)
DATABASE_NAME = "frito94.db"

def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def criar_tabelas():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                telegram_id TEXT UNIQUE NOT NULL,
                perfil TEXT NOT NULL DEFAULT 'operador',
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                preco_venda REAL NOT NULL,
                categoria_id INTEGER,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insumos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                unidade TEXT NOT NULL,
                custo_unitario REAL NOT NULL DEFAULT 0,
                estoque_atual REAL NOT NULL DEFAULT 0,
                estoque_minimo REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fichas_tecnicas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                insumo_id INTEGER NOT NULL,
                quantidade REAL NOT NULL,
                FOREIGN KEY (produto_id) REFERENCES produtos(id),
                FOREIGN KEY (insumo_id) REFERENCES insumos(id),
                UNIQUE(produto_id, insumo_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_pedido INTEGER NOT NULL UNIQUE,
                cliente_nome TEXT NOT NULL,
                cliente_telefone TEXT,
                canal TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'recebido',
                forma_pagamento TEXT NOT NULL,
                taxa_entrega REAL NOT NULL DEFAULT 0,
                desconto REAL NOT NULL DEFAULT 0,
                subtotal REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                observacao TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedido_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL DEFAULT 1,
                preco_unitario REAL NOT NULL,
                custo_unitario REAL NOT NULL DEFAULT 0,
                subtotal REAL NOT NULL,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS caixa_lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                categoria TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                forma_pagamento TEXT,
                pedido_id INTEGER,
                data TEXT NOT NULL DEFAULT (date('now','localtime')),
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
            )
        """)
        conn.commit()
        logger.info("Tabelas criadas com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
