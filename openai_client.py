# openai_client.py - Integracao com a API da OpenAI
import logging, json
from datetime import date, timedelta
from openai import OpenAI
from models import listar_produtos, listar_insumos, calcular_cmv_periodo, gerar_dre, resumo_caixa_dia, insumos_abaixo_minimo, listar_pedidos_do_dia

logger = logging.getLogger(__name__)
client = OpenAI()

SYSTEM_PROMPT = 'Voce e o assistente de gestao do delivery FRITO94. Responda em portugues brasileiro de forma objetiva. Use tabelas para dados financeiros. Formate valores como R$ X,XX.'

def buscar_contexto_negocio():
    hoje = date.today().isoformat()
    semana_inicio = (date.today() - timedelta(days=7)).isoformat()
    mes_inicio = date.today().replace(day=1).isoformat()
    try:
        pedidos = listar_pedidos_do_dia()
        caixa = resumo_caixa_dia(hoje)
        alertas = insumos_abaixo_minimo()
        cmv = calcular_cmv_periodo(semana_inicio, hoje)
        dre = gerar_dre(mes_inicio, hoje)
        produtos = listar_produtos()
        insumos = listar_insumos()
        ctx = '=== FRITO94 ' + hoje + ' ===\n'
        ctx += 'PEDIDOS HOJE: ' + str(len(pedidos)) + '\n'
        ctx += 'CAIXA: Entradas R$' + str(round(caixa['total_entradas'],2)) + ' | Saidas R$' + str(round(caixa['total_saidas'],2)) + ' | Saldo R$' + str(round(caixa['saldo'],2)) + '\n'
        ctx += 'CMV SEMANA: Receita R$' + str(round(cmv['receita_total'],2)) + ' | CMV ' + str(round(cmv['cmv_percentual'],1)) + '% | Lucro R$' + str(round(cmv['lucro_bruto'],2)) + '\n'
        ctx += 'DRE MES: Receita R$' + str(round(dre['receita_liquida'],2)) + ' | Resultado R$' + str(round(dre['resultado_liquido'],2)) + ' | Margem ' + str(round(dre['margem_liquida'],1)) + '%\n'
        ctx += 'PEDIDOS MES: ' + str(dre['num_pedidos']) + ' | Ticket Medio R$' + str(round(dre['ticket_medio'],2)) + '\n'
        ctx += 'ALERTAS ESTOQUE: ' + str(len(alertas)) + ' insumos abaixo do minimo\n'
        ctx += 'PRODUTOS: ' + json.dumps([{'id':p['id'],'nome':p['nome'],'preco':p['preco_venda']} for p in produtos], ensure_ascii=False) + '\n'
        ctx += 'DETALHES PEDIDOS: ' + json.dumps(pedidos, ensure_ascii=False) + '\n'
        ctx += 'CMV PRODUTOS: ' + json.dumps(cmv['produtos'], ensure_ascii=False) + '\n'
        ctx += 'ALERTAS: ' + json.dumps(alertas, ensure_ascii=False)
        return ctx
    except Exception as e:
        logger.error('Erro contexto: ' + str(e))
        return 'Dados indisponiveis: ' + str(e)

def perguntar_ia(pergunta, contexto_extra=''):
    try:
        contexto = buscar_contexto_negocio()
        extra = ('Contexto extra: ' + contexto_extra + '\n') if contexto_extra else ''
        msg = contexto + '\n\n' + extra + 'Pergunta: ' + pergunta
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': msg}],
            max_tokens=1500, temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error('Erro OpenAI: ' + str(e))
        return 'Erro ao consultar IA: ' + str(e)

def analisar_dados_financeiros(tipo, dados):
    prompts = {
        'dre': 'Analise este DRE e de 3 insights praticos: ' + json.dumps(dados, ensure_ascii=False),
        'cmv': 'Analise CMV e identifique melhores/piores margens: ' + json.dumps(dados, ensure_ascii=False),
        'caixa': 'Analise o fluxo de caixa e aponte atencoes: ' + json.dumps(dados, ensure_ascii=False),
        'estoque': 'Analise estoque e priorize reposicao urgente: ' + json.dumps(dados, ensure_ascii=False)
    }
    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompts.get(tipo, str(dados))}],
            max_tokens=800, temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        return 'Erro na analise: ' + str(e)
