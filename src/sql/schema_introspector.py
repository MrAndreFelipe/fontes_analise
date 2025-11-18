# src/sql/schema_introspector.py
"""
Schema Introspector - Sistema RAG Cativa Textil
Extrai e formata schema do Oracle para consumo pelo LLM
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SchemaIntrospector:
    """
    Extrai schema do Oracle e formata para o LLM entender
    """
    
    def __init__(self):
        """Inicializa com schema hardcoded da view principal"""
        
        # Schema da view principal (pode ser expandido)
        self.schema = {
            'VW_RAG_VENDAS_ESTRUTURADA': {
                'description': 'View principal com dados de vendas estruturados dos ultimos 730 dias',
                'columns': [
                    {
                        'name': 'NUMERO_PEDIDO',
                        'type': 'NUMBER',
                        'description': 'Numero do pedido de venda'
                    },
                    {
                        'name': 'NOME_CLIENTE',
                        'type': 'VARCHAR2',
                        'description': 'Nome completo do cliente'
                    },
                    {
                        'name': 'NOME_REPRESENTANTE',
                        'type': 'VARCHAR2',
                        'description': 'Nome completo do representante comercial'
                    },
                    {
                        'name': 'VALOR_ITEM_LIQUIDO',
                        'type': 'NUMBER',
                        'description': 'Valor liquido da venda (valor final pos descontos)'
                    },
                    {
                        'name': 'VALOR_ITEM_BRUTO',
                        'type': 'NUMBER',
                        'description': 'Valor bruto da venda (valor antes dos descontos)',
                        'alias': 'VL_ITEM_BRUTO'
                    },
                    {
                        'name': 'DATA_VENDA',
                        'type': 'DATE',
                        'description': 'Data da venda (dt_digitacao)',
                        'notes': 'Usar TRUNC() para comparar datas'
                    },
                    {
                        'name': 'DESCRICAO_REGIAO',
                        'type': 'VARCHAR2',
                        'description': 'Nome da regiao comercial (ex: MG, SP, PR, SUL)',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    },
                    {
                        'name': 'DESCRICAO_REGIONAL',
                        'type': 'VARCHAR2',
                        'description': 'Descricao detalhada da regional',
                        'notes': 'Contem informacoes complementares da regiao'
                    },
                    {
                        'name': 'CNPJ_CLIENTE',
                        'type': 'VARCHAR2',
                        'description': 'CNPJ do cliente'
                    },
                    {
                        'name': 'CNPJ_REPRESENTANTE',
                        'type': 'VARCHAR2',
                        'description': 'CNPJ do representante'
                    },
                    {
                        'name': 'EMPRESA',
                        'type': 'VARCHAR2',
                        'description': 'Empresa (Cativa Pomerode ou Cativa MS)'
                    },
                    {
                        'name': 'MES_VENDA',
                        'type': 'NUMBER',
                        'description': 'Mes da venda (1-12)'
                    },
                    {
                        'name': 'ANO_VENDA',
                        'type': 'NUMBER',
                        'description': 'Ano da venda (ex: 2025)'
                    },
                    {
                        'name': 'CODIGO_COLECAO',
                        'type': 'VARCHAR2',
                        'description': 'Codigo da colecao do produto (ex: 202603, 202504, 202403)',
                        'notes': 'Formato AAAAMM + sequencial (ano/mes + numero)'
                    },
                    {
                        'name': 'DESCRICAO_COLECAO',
                        'type': 'VARCHAR2',
                        'description': 'Nome da colecao (ex: VERAO 2027, ALTO VERAO 2026, TRANSITION 2025)',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    }
                ],
                'examples': {
                    'DESCRICAO_REGIAO': ['MG', 'SP', 'PR - LONDRINA E', 'PE - SERTAO', 'SUL', 'NORDESTE'],
                    'NOME_REPRESENTANTE': ['JOAO SILVA', 'MARIA SANTOS', 'PEDRO OLIVEIRA'],
                    'NOME_CLIENTE': ['CONFECCOES ABC LTDA', 'TEXTIL XYZ SA', 'COMERCIO DEF ME'],
                    'CODIGO_COLECAO': ['202603', '202504', '202403', '202304', '202203', '202103', '202003', '201903'],
                    'DESCRICAO_COLECAO': ['VERAO 2027', 'ALTO VERAO 2026', 'VERAO 2025', 'TRANSITION 2024', 'OUTONO 2024', 'ESSENCIAL', 'CATIVA BEM ESTAR']
                },
                'notes': [
                    'Para data de hoje: TRUNC(DATA_VENDA) = TRUNC(SYSDATE)',
                    'Para mes atual: EXTRACT(MONTH FROM DATA_VENDA) = EXTRACT(MONTH FROM SYSDATE)',
                    'Para comparar valores monetarios use VALOR_ITEM_LIQUIDO (pos-desconto)',
                    'LIMITACAO - Sem ORDER BY: WHERE ROWNUM <= N no final',
                    'LIMITACAO - Com ORDER BY: SELECT * FROM (SELECT ... ORDER BY ...) WHERE ROWNUM <= N',
                    'NUNCA coloque WHERE ROWNUM apos ORDER BY (sintaxe invalida Oracle 11g)',
                    'IMPORTANTE - Filtros de DESCRICAO_REGIAO (formato: ESTADO - REGIAO detalhes):',
                    '  - Todas regioes de estado: UPPER(DESCRICAO_REGIAO) LIKE \'PE - %\'',
                    '  - Regiao especifica: UPPER(DESCRICAO_REGIAO) LIKE \'PE - SERTAO%\'',
                    '  - NUNCA use LIKE \'%PE%\' (pega PELOTAS, PARANA, etc - falsos positivos)',
                    'Filtros de nomes (NOME_CLIENTE, NOME_REPRESENTANTE):',
                    '  - Use % em ambos lados: UPPER(NOME_CLIENTE) LIKE \'%CONFEC%\'',
                    '  - Exemplo: UPPER(NOME_REPRESENTANTE) LIKE \'%SILVA%\'',
                    'Filtros de colecoes:',
                    '  - Por codigo exato: CODIGO_COLECAO = \'202603\'',
                    '  - Por nome: UPPER(DESCRICAO_COLECAO) LIKE \'%VERAO%\'',
                    '  - Multiplas colecoes: CODIGO_COLECAO IN (\'202603\', \'202504\', \'202403\')'
                ]
            },
            'VW_RAG_CONTAS_APAGAR': {
                'description': 'View com dados completos de contas a pagar (todos os titulos, pagos e em aberto, sem filtro de periodo)',
                'columns': [
                    {
                        'name': 'EMPRESA',
                        'type': 'VARCHAR2',
                        'description': 'Empresa (Catival Textil ou Catival MS)'
                    },
                    {
                        'name': 'CHAVE_CONTAS_APAGAR',
                        'type': 'NUMBER',
                        'description': 'Chave unica do titulo a pagar (AP)'
                    },
                    {
                        'name': 'TITULO',
                        'type': 'VARCHAR2',
                        'description': 'Numero do titulo a pagar'
                    },
                    {
                        'name': 'CNPJ_FORNECEDOR',
                        'type': 'VARCHAR2',
                        'description': 'CNPJ do fornecedor'
                    },
                    {
                        'name': 'NOME_FORNECEDOR',
                        'type': 'VARCHAR2',
                        'description': 'Nome completo do fornecedor'
                    },
                    {
                        'name': 'DATA_EMISSAO',
                        'type': 'DATE',
                        'description': 'Data de emissao do titulo',
                        'notes': 'Usar TRUNC() para comparar datas'
                    },
                    {
                        'name': 'DATA_VENCIMENTO',
                        'type': 'DATE',
                        'description': 'Data de vencimento do titulo',
                        'notes': 'Usar TRUNC() para comparar datas. Para titulos vencidos: TRUNC(DATA_VENCIMENTO) < TRUNC(SYSDATE)'
                    },
                    {
                        'name': 'VALOR_TITULO',
                        'type': 'NUMBER',
                        'description': 'Valor total original do titulo'
                    },
                    {
                        'name': 'VALOR_SALDO',
                        'type': 'NUMBER',
                        'description': 'Saldo atual do titulo (valor pendente a pagar)',
                        'notes': 'VALOR_SALDO > 0 indica titulo em aberto. VALOR_SALDO = 0 indica titulo pago'
                    },
                    {
                        'name': 'GRUPO',
                        'type': 'VARCHAR2',
                        'description': 'Codigo do grupo de despesa'
                    },
                    {
                        'name': 'DESCRICAO_GRUPO',
                        'type': 'VARCHAR2',
                        'description': 'Descricao do grupo de despesa',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    },
                    {
                        'name': 'SUBGRUPO',
                        'type': 'VARCHAR2',
                        'description': 'Codigo do subgrupo de despesa'
                    },
                    {
                        'name': 'DESCRICAO_SUBGRUPO',
                        'type': 'VARCHAR2',
                        'description': 'Descricao do subgrupo de despesa',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    },
                    {
                        'name': 'BANCO',
                        'type': 'VARCHAR2',
                        'description': 'Codigo do banco'
                    },
                    {
                        'name': 'DESCRICAO_BANCO',
                        'type': 'VARCHAR2',
                        'description': 'Nome do banco',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    }
                ],
                'examples': {
                    'EMPRESA': ['Catival Textil', 'Catival MS'],
                    'NOME_FORNECEDOR': ['FORNECEDOR ABC LTDA', 'EMPRESA XYZ SA', 'COMERCIO DEF ME'],
                    'DESCRICAO_GRUPO': ['MATERIA PRIMA', 'DESPESAS OPERACIONAIS', 'SERVICOS'],
                    'DESCRICAO_SUBGRUPO': ['FIOS', 'ENERGIA', 'MANUTENCAO'],
                    'DESCRICAO_BANCO': ['BANCO DO BRASIL', 'CAIXA ECONOMICA', 'ITAU']
                },
                'notes': [
                    'Para titulos em aberto: WHERE VALOR_SALDO > 0',
                    'Para titulos pagos: WHERE VALOR_SALDO = 0',
                    'Para titulos vencidos: WHERE TRUNC(DATA_VENCIMENTO) < TRUNC(SYSDATE) AND VALOR_SALDO > 0',
                    'Para titulos a vencer hoje: WHERE TRUNC(DATA_VENCIMENTO) = TRUNC(SYSDATE) AND VALOR_SALDO > 0',
                    'Para titulos a vencer no mes: WHERE EXTRACT(MONTH FROM DATA_VENCIMENTO) = EXTRACT(MONTH FROM SYSDATE) AND VALOR_SALDO > 0',
                    'Para comparar valores use VALOR_SALDO (saldo pendente) ou VALOR_TITULO (valor original)',
                    'Filtros de nome de fornecedor: UPPER(NOME_FORNECEDOR) LIKE \'%TEXTO%\'',
                    'Filtros de descricao de grupo/subgrupo: UPPER(DESCRICAO_GRUPO) LIKE \'%TEXTO%\'',
                    'LIMITACAO - Sem ORDER BY: WHERE ROWNUM <= N no final',
                    'LIMITACAO - Com ORDER BY: SELECT * FROM (SELECT ... ORDER BY ...) WHERE ROWNUM <= N'
                ]
            },
            'VW_RAG_CONTAS_RECEBER': {
                'description': 'View com dados completos de contas a receber (duplicatas a receber dos ultimos 730 dias)',
                'columns': [
                    {
                        'name': 'EMPRESA',
                        'type': 'VARCHAR2',
                        'description': 'Empresa (Cativa Textil ou Cativa MS)'
                    },
                    {
                        'name': 'CHAVE_DUPLICATA',
                        'type': 'NUMBER',
                        'description': 'Chave unica da duplicata a receber'
                    },
                    {
                        'name': 'CHAVE_AP',
                        'type': 'NUMBER',
                        'description': 'Chave AP relacionada'
                    },
                    {
                        'name': 'FATURA',
                        'type': 'VARCHAR2',
                        'description': 'Numero da fatura'
                    },
                    {
                        'name': 'ORDEM',
                        'type': 'NUMBER',
                        'description': 'Numero da ordem'
                    },
                    {
                        'name': 'CHAVE_FATURA',
                        'type': 'NUMBER',
                        'description': 'Chave da fatura (pk_movfat)'
                    },
                    {
                        'name': 'CNPJ_CLIENTE',
                        'type': 'VARCHAR2',
                        'description': 'CNPJ do cliente'
                    },
                    {
                        'name': 'NOME_CLIENTE',
                        'type': 'VARCHAR2',
                        'description': 'Nome completo do cliente'
                    },
                    {
                        'name': 'OPERACAO',
                        'type': 'VARCHAR2',
                        'description': 'Tipo de operacao (Saida ou Entrada)'
                    },
                    {
                        'name': 'CNPJ_REPRESENTANTE',
                        'type': 'VARCHAR2',
                        'description': 'CNPJ do representante comercial'
                    },
                    {
                        'name': 'NOME_REPRESENTANTE',
                        'type': 'VARCHAR2',
                        'description': 'Nome completo do representante'
                    },
                    {
                        'name': 'BANCO',
                        'type': 'VARCHAR2',
                        'description': 'Codigo do banco'
                    },
                    {
                        'name': 'DESCRICAO_BANCO',
                        'type': 'VARCHAR2',
                        'description': 'Nome do banco',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    },
                    {
                        'name': 'COMICAO_1',
                        'type': 'NUMBER',
                        'description': 'Percentual de comissao 1'
                    },
                    {
                        'name': 'COMICAO_2',
                        'type': 'NUMBER',
                        'description': 'Percentual de comissao 2'
                    },
                    {
                        'name': 'DATA_DIGITACAO',
                        'type': 'DATE',
                        'description': 'Data de digitacao da duplicata',
                        'notes': 'Usar TRUNC() para comparar datas'
                    },
                    {
                        'name': 'DATA_VENCIMENTO',
                        'type': 'DATE',
                        'description': 'Data de vencimento da duplicata',
                        'notes': 'Usar TRUNC() para comparar datas. Para duplicatas vencidas: TRUNC(DATA_VENCIMENTO) < TRUNC(SYSDATE)'
                    },
                    {
                        'name': 'DATA_EMISSAO',
                        'type': 'DATE',
                        'description': 'Data de emissao da duplicata',
                        'notes': 'Usar TRUNC() para comparar datas'
                    },
                    {
                        'name': 'VALOR_DUPLICATA',
                        'type': 'NUMBER',
                        'description': 'Valor total original da duplicata'
                    },
                    {
                        'name': 'SITUACAO_DUPLICATA',
                        'type': 'VARCHAR2',
                        'description': 'Descricao da situacao da duplicata (ex: EM ABERTO, PAGA, VENCIDA)',
                        'notes': 'Usar UPPER() e LIKE para buscar'
                    },
                    {
                        'name': 'SALDO',
                        'type': 'NUMBER',
                        'description': 'Saldo atual da duplicata (valor pendente a receber)',
                        'notes': 'SALDO > 0 indica duplicata em aberto. SALDO = 0 indica duplicata recebida'
                    }
                ],
                'examples': {
                    'EMPRESA': ['Cativa Textil', 'Cativa MS'],
                    'NOME_CLIENTE': ['CLIENTE ABC LTDA', 'EMPRESA XYZ SA', 'COMERCIO DEF ME'],
                    'NOME_REPRESENTANTE': ['JOAO SILVA', 'MARIA SANTOS', 'PEDRO OLIVEIRA'],
                    'OPERACAO': ['Saida', 'Entrada'],
                    'SITUACAO_DUPLICATA': ['EM ABERTO', 'PAGA', 'VENCIDA', 'PARCIAL'],
                    'DESCRICAO_BANCO': ['BANCO DO BRASIL', 'CAIXA ECONOMICA', 'ITAU']
                },
                'notes': [
                    'Para duplicatas em aberto: WHERE SALDO > 0',
                    'Para duplicatas recebidas: WHERE SALDO = 0',
                    'Para duplicatas vencidas: WHERE TRUNC(DATA_VENCIMENTO) < TRUNC(SYSDATE) AND SALDO > 0',
                    'Para duplicatas a vencer hoje: WHERE TRUNC(DATA_VENCIMENTO) = TRUNC(SYSDATE) AND SALDO > 0',
                    'Para duplicatas a vencer no mes: WHERE EXTRACT(MONTH FROM DATA_VENCIMENTO) = EXTRACT(MONTH FROM SYSDATE) AND SALDO > 0',
                    'Para comparar valores use SALDO (saldo pendente) ou VALOR_DUPLICATA (valor original)',
                    'Filtros de nome de cliente: UPPER(NOME_CLIENTE) LIKE \'%TEXTO%\'',
                    'Filtros de nome de representante: UPPER(NOME_REPRESENTANTE) LIKE \'%TEXTO%\'',
                    'Filtros de situacao: UPPER(SITUACAO_DUPLICATA) LIKE \'%TEXTO%\'',
                    'LIMITACAO - Sem ORDER BY: WHERE ROWNUM <= N no final',
                    'LIMITACAO - Com ORDER BY: SELECT * FROM (SELECT ... ORDER BY ...) WHERE ROWNUM <= N'
                ]
            }
        }
    
    def get_schema_for_llm(self) -> str:
        """
        Retorna schema formatado para o LLM
        
        Returns:
            String com schema formatado em texto claro
        """
        
        output = []
        output.append("=== SCHEMA DO BANCO DE DADOS ORACLE ===\n")
        
        for view_name, view_info in self.schema.items():
            output.append(f"VIEW: {view_name}")
            output.append(f"Descricao: {view_info['description']}\n")
            
            output.append("COLUNAS:")
            for col in view_info['columns']:
                col_line = f"  - {col['name']} ({col['type']}): {col['description']}"
                if 'notes' in col:
                    col_line += f" | NOTA: {col['notes']}"
                output.append(col_line)
            
            if view_info.get('examples'):
                output.append("\nEXEMPLOS DE VALORES:")
                for col_name, values in view_info['examples'].items():
                    output.append(f"  - {col_name}: {', '.join(map(str, values))}")
            
            if view_info.get('notes'):
                output.append("\nREGRAS IMPORTANTES:")
                for note in view_info['notes']:
                    output.append(f"  * {note}")
        
        return "\n".join(output)
    
    def get_column_info(self, column_name: str) -> Dict[str, Any]:
        """
        Retorna informacoes de uma coluna especifica
        
        Args:
            column_name: Nome da coluna
            
        Returns:
            Dicionario com info da coluna ou None
        """
        for view_info in self.schema.values():
            for col in view_info['columns']:
                if col['name'] == column_name.upper():
                    return col
        return None
    
    def get_available_views(self) -> List[str]:
        """Retorna lista de views disponiveis"""
        return list(self.schema.keys())
    
    def validate_view(self, view_name: str) -> bool:
        """Valida se a view existe no schema"""
        return view_name.upper() in [v.upper() for v in self.schema.keys()]
