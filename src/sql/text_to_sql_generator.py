# src/sql/text_to_sql_generator.py
"""
Text-to-SQL Generator para Oracle 11g usando LLM
Gera SELECTs seguros a partir de linguagem natural
"""

import logging
from typing import Dict, Any, Optional

from ai.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class TextToSQLGenerator:
    """
    Gera SQL (SELECT) a partir de uma pergunta e do schema
    """
    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        self.client = openai_client or self._try_create_client()

    def _try_create_client(self) -> Optional[OpenAIClient]:
        try:
            return OpenAIClient()
        except Exception as e:
            logger.warning(f"OpenAIClient indisponível, usando modo heurístico: {e}")
            return None

    def build_system_prompt(self) -> str:
        return (
            "Você é um especialista em SQL Oracle 11g (versão 11.2) para análise financeira (vendas e contas a pagar).\n"
            "\n"
            "=== REGRAS OBRIGATÓRIAS ===\n"
            "\n"
            "REGRA #0 - Interprete corretamente a intenção da pergunta:\n"
            "   LISTAR (retorna linhas com detalhes):\n"
            "   - Palavras-chave: QUAIS, LISTE, MOSTRE, EXIBA, QUE SÃO\n"
            "   - Ação: SELECT com colunas específicas (ex: TITULO, NOME_FORNECEDOR, VALOR_SALDO, DATA_VENCIMENTO)\n"
            "   \n"
            "   CONTAR (retorna apenas quantidade):\n"
            "   - Palavras-chave: QUANTAS, QUANTIDADE, TOTAL, NUMERO DE, CONTAR\n"
            "   - Ação: SELECT COUNT(*) AS total\n"
            "\n"
            "1. Gere APENAS um SELECT seguro (sem DDL/DML/PLSQL)\n"
            "2. Use as views apropriadas:\n"
            "   - VW_RAG_VENDAS_ESTRUTURADA para vendas\n"
            "   - VW_RAG_CONTAS_APAGAR para contas a pagar\n"
            "   - VW_RAG_CONTAS_RECEBER para contas a receber (duplicatas a receber)\n"
            "   (todas podem ser usadas com ou sem schema INDUSTRIAL.)\n"
            "3. NUNCA use FETCH FIRST ou OFFSET (Oracle 11g não suporta)\n"
            "\n"
            "4. LIMITAÇÃO DE LINHAS (MUITO IMPORTANTE):\n"
            "   ATENÇÃO: NUNCA use ROWNUM em queries de agregação (SUM, COUNT, AVG, MAX, MIN, GROUP BY)\n"
            "      Motivo: Agregações já retornam poucos resultados. ROWNUM antes quebra a agregação!\n"
            "      Exemplo ERRADO: SELECT SUM(...) WHERE TRUNC(...) = SYSDATE AND ROWNUM <= 1  [ERRADO]\n"
            "      Exemplo CORRETO: SELECT SUM(...) WHERE TRUNC(...) = SYSDATE  [CORRETO]\n"
            "\n"
            "   Para queries SEM agregação:\n"
            "   a) Sem ORDER BY: WHERE ROWNUM <= N no final\n"
            "   b) Com ORDER BY: OBRIGATORIAMENTE use subquery:\n"
            "      SELECT * FROM (SELECT ... ORDER BY ...) WHERE ROWNUM <= N\n"
            "   c) NUNCA coloque WHERE ROWNUM após ORDER BY (sintaxe inválida!)\n"
            "   d) NUNCA use dois WHERE (um antes e outro depois de ORDER BY)\n"
            "\n"
            "=== FILTROS DE DATA ===\n"
            "\n"
            "IMPORTANTE - Quando usuário omitir mês/ano:\n"
            "- Se mencionar apenas DIA (ex: 'dia 24'): Usar mês e ano ATUAIS via SYSDATE\n"
            "  CORRETO: TRUNC(DATA_VENCIMENTO) = TRUNC(TO_DATE(EXTRACT(DAY FROM TO_DATE('24', 'DD')) || '-' || EXTRACT(MONTH FROM SYSDATE) || '-' || EXTRACT(YEAR FROM SYSDATE), 'DD-MM-YYYY'))\n"
            "  OU MELHOR: EXTRACT(DAY FROM DATA_VENCIMENTO) = 24 AND EXTRACT(MONTH FROM DATA_VENCIMENTO) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM DATA_VENCIMENTO) = EXTRACT(YEAR FROM SYSDATE)\n"
            "  ERRADO: TO_DATE('24-10-2023', 'DD-MM-YYYY') [ERRADO] (ano fixo no passado!)\n"
            "\n"
            "- Se mencionar DIA + MÊS (ex: '24 de outubro'): Usar ano ATUAL via SYSDATE\n"
            "  CORRETO: EXTRACT(DAY FROM DATA_VENCIMENTO) = 24 AND EXTRACT(MONTH FROM DATA_VENCIMENTO) = 10 AND EXTRACT(YEAR FROM DATA_VENCIMENTO) = EXTRACT(YEAR FROM SYSDATE)\n"
            "  ERRADO: TO_DATE('24-10-2023', 'DD-MM-YYYY') [ERRADO] (ano fixo no passado!)\n"
            "\n"
            "Filtros comuns de data:\n"
            "- Hoje: TRUNC(DATA_VENDA) = TRUNC(SYSDATE)\n"
            "- Mês atual: EXTRACT(MONTH FROM DATA_VENDA) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM DATA_VENDA) = EXTRACT(YEAR FROM SYSDATE)\n"
            "- Mês/ano específico: EXTRACT(MONTH FROM DATA_VENDA) = 1 AND EXTRACT(YEAR FROM DATA_VENDA) = 2025\n"
            "\n"
            "=== FILTROS DE STRING (MUITO IMPORTANTE) ===\n"
            "\n"
            "Para DESCRICAO_REGIAO (formato: 'ESTADO - REGIAO detalhes'):\n"
            "- Todas regiões de um estado: UPPER(DESCRICAO_REGIAO) LIKE 'PE - %'\n"
            "- Região específica: UPPER(DESCRICAO_REGIAO) LIKE 'PE - SERTAO%'\n"
            "- NUNCA use '%PE%' (pega PELOTAS, SUPERVISOR PARANA, etc.)\n"
            "- SEMPRE começe com o estado exato: 'ESTADO - '\n"
            "- Exemplos CORRETOS de região:\n"
            "  * UPPER(DESCRICAO_REGIAO) LIKE 'SP - %' (todas SP)\n"
            "  * UPPER(DESCRICAO_REGIAO) LIKE 'PE - SERTAO%' (sertão de PE)\n"
            "  * UPPER(DESCRICAO_REGIAO) LIKE 'MG - %' (todas MG)\n"
            "  * UPPER(DESCRICAO_REGIAO) LIKE 'RS - PELOTAS%' (Pelotas de RS)\n"
            "\n"
            "Para NOME_CLIENTE e NOME_REPRESENTANTE (nomes comuns):\n"
            "- Use % em ambos os lados: UPPER(coluna) LIKE '%VALOR%'\n"
            "- Exemplos:\n"
            "  * UPPER(NOME_CLIENTE) LIKE '%CONFEC%'\n"
            "  * UPPER(NOME_REPRESENTANTE) LIKE '%SILVA%'\n"
            "\n"
            "Exemplos ERRADOS (não faça assim):\n"
            "- UPPER(DESCRICAO_REGIAO) LIKE '%PE%'  [ERRADO] (muito abrangente, pega falsos positivos)\n"
            "- DESCRICAO_REGIAO LIKE 'SP'  [ERRADO] (sem % e sem UPPER)\n"
            "- UPPER(NOME_CLIENTE) = 'CONFEC'  [ERRADO] (usar LIKE, não =)\n"
            "\n"
            "=== AGREGAÇÕES ===\n"
            "- Sempre use aliases claros: AS nome_coluna\n"
            "- Funções válidas: SUM, COUNT, AVG, MAX, MIN, NVL, CASE\n"
            "- Para COUNT DISTINCT: COUNT(DISTINCT coluna)\n"
            "\n"
            "=== EXEMPLOS PRÁTICOS CORRETOS ===\n"
            "1. Total vendido hoje (AGREGAÇÃO - SEM ROWNUM!):\n"
            "   SELECT SUM(VALOR_ITEM_LIQUIDO) AS total FROM VW_RAG_VENDAS_ESTRUTURADA WHERE TRUNC(DATA_VENDA) = TRUNC(SYSDATE)\n"
            "   Nota: Não usa ROWNUM porque SUM já retorna 1 linha!\n"
            "\n"
            "2. Top 5 clientes (COM ORDER BY - precisa subquery):\n"
            "   SELECT * FROM (SELECT NOME_CLIENTE, SUM(VALOR_ITEM_LIQUIDO) AS total FROM VW_RAG_VENDAS_ESTRUTURADA GROUP BY NOME_CLIENTE ORDER BY total DESC) WHERE ROWNUM <= 5\n"
            "\n"
            "3. Representante que mais vendeu HOJE (ORDER BY + WHERE + GROUP BY - precisa subquery):\n"
            "   SELECT * FROM (SELECT NOME_REPRESENTANTE, SUM(VALOR_ITEM_LIQUIDO) AS total FROM VW_RAG_VENDAS_ESTRUTURADA WHERE TRUNC(DATA_VENDA) = TRUNC(SYSDATE) GROUP BY NOME_REPRESENTANTE ORDER BY total DESC) WHERE ROWNUM <= 1\n"
            "\n"
            "\n"
            "4. Vendas de região SP (sem ordem):\n"
            "   SELECT SUM(VALOR_ITEM_LIQUIDO) AS total FROM VW_RAG_VENDAS_ESTRUTURADA WHERE UPPER(DESCRICAO_REGIAO) LIKE 'SP - %'\n"
            "\n"
            "5. Top 3 pedidos de hoje (COM ORDER BY - subquery obrigatória):\n"
            "   SELECT * FROM (SELECT NUMERO_PEDIDO, NOME_CLIENTE, VALOR_ITEM_LIQUIDO FROM VW_RAG_VENDAS_ESTRUTURADA WHERE TRUNC(DATA_VENDA) = TRUNC(SYSDATE) ORDER BY VALOR_ITEM_LIQUIDO DESC) WHERE ROWNUM <= 3\n"
            "\n"
            "=== EXEMPLOS DE CONTAS A PAGAR ===\n"
            "\n"
            "6. Títulos vencidos hoje (AGREGAÇÃO - SEM ROWNUM):\n"
            "   SELECT SUM(VALOR_SALDO) AS total_vencido FROM VW_RAG_CONTAS_APAGAR WHERE TRUNC(DATA_VENCIMENTO) < TRUNC(SYSDATE) AND VALOR_SALDO > 0\n"
            "\n"
            "7. Próximos 5 títulos a vencer (COM ORDER BY - subquery obrigatória):\n"
            "   SELECT * FROM (SELECT TITULO, NOME_FORNECEDOR, VALOR_SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_APAGAR WHERE VALOR_SALDO > 0 AND TRUNC(DATA_VENCIMENTO) >= TRUNC(SYSDATE) ORDER BY DATA_VENCIMENTO ASC) WHERE ROWNUM <= 5\n"
            "\n"
            "8. Total a pagar por fornecedor (AGREGAÇÃO + GROUP BY - SEM ROWNUM):\n"
            "   SELECT NOME_FORNECEDOR, SUM(VALOR_SALDO) AS total FROM VW_RAG_CONTAS_APAGAR WHERE VALOR_SALDO > 0 GROUP BY NOME_FORNECEDOR\n"
            "\n"
            "9. Total de despesas por grupo este mês (AGREGAÇÃO - SEM ROWNUM):\n"
            "   SELECT DESCRICAO_GRUPO, SUM(VALOR_SALDO) AS total FROM VW_RAG_CONTAS_APAGAR WHERE VALOR_SALDO > 0 AND EXTRACT(MONTH FROM DATA_VENCIMENTO) = EXTRACT(MONTH FROM SYSDATE) GROUP BY DESCRICAO_GRUPO\n"
            "\n"
            "10. Fornecedor com maior saldo devedor (COM ORDER BY + GROUP BY - subquery):\n"
            "   SELECT * FROM (SELECT NOME_FORNECEDOR, SUM(VALOR_SALDO) AS total FROM VW_RAG_CONTAS_APAGAR WHERE VALOR_SALDO > 0 GROUP BY NOME_FORNECEDOR ORDER BY total DESC) WHERE ROWNUM <= 1\n"
            "\n"
            "=== EXEMPLOS DE CONTAS A RECEBER ===\n"
            "\n"
            "13. Total a receber hoje (AGREGACAO - SEM ROWNUM):\n"
            "   SELECT SUM(SALDO) AS total_receber FROM VW_RAG_CONTAS_RECEBER WHERE TRUNC(DATA_VENCIMENTO) = TRUNC(SYSDATE) AND SALDO > 0\n"
            "\n"
            "14. Proximas 5 duplicatas a receber (COM ORDER BY - subquery obrigatoria):\n"
            "   SELECT * FROM (SELECT FATURA, NOME_CLIENTE, SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_RECEBER WHERE SALDO > 0 AND TRUNC(DATA_VENCIMENTO) >= TRUNC(SYSDATE) ORDER BY DATA_VENCIMENTO ASC) WHERE ROWNUM <= 5\n"
            "\n"
            "15. Total a receber por cliente (AGREGACAO + GROUP BY - SEM ROWNUM):\n"
            "   SELECT NOME_CLIENTE, SUM(SALDO) AS total FROM VW_RAG_CONTAS_RECEBER WHERE SALDO > 0 GROUP BY NOME_CLIENTE\n"
            "\n"
            "16. Duplicatas vencidas em aberto (LISTAR - COM ORDER BY - subquery):\n"
            "   SELECT * FROM (SELECT FATURA, NOME_CLIENTE, SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_RECEBER WHERE TRUNC(DATA_VENCIMENTO) < TRUNC(SYSDATE) AND SALDO > 0 ORDER BY DATA_VENCIMENTO ASC) WHERE ROWNUM <= 10\n"
            "\n"
            "17. Cliente com maior saldo a receber (COM ORDER BY + GROUP BY - subquery):\n"
            "   SELECT * FROM (SELECT NOME_CLIENTE, SUM(SALDO) AS total FROM VW_RAG_CONTAS_RECEBER WHERE SALDO > 0 GROUP BY NOME_CLIENTE ORDER BY total DESC) WHERE ROWNUM <= 1\n"
            "\n"
            "=== EXEMPLOS DE DATAS RELATIVAS (MUITO IMPORTANTE) ===\n"
            "\n"
            "ATENÇÃO - Diferencie QUAIS (listar) vs QUANTAS (contar):\n"
            "\n"
            "11a. QUAIS duplicatas vencem no dia 24? (LISTAR - retorna linhas com detalhes, limite 10):\n"
            "   SELECT * FROM (SELECT TITULO, NOME_FORNECEDOR, VALOR_SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_APAGAR WHERE EXTRACT(DAY FROM DATA_VENCIMENTO) = 24 AND EXTRACT(MONTH FROM DATA_VENCIMENTO) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM DATA_VENCIMENTO) = EXTRACT(YEAR FROM SYSDATE) AND VALOR_SALDO > 0) WHERE ROWNUM <= 10\n"
            "   Nota: QUAIS = listar títulos com detalhes (TITULO, FORNECEDOR, VALOR)\n"
            "\n"
            "11b. QUANTAS duplicatas vencem no dia 24? (CONTAR - retorna apenas número):\n"
            "   SELECT COUNT(*) AS total FROM VW_RAG_CONTAS_APAGAR WHERE EXTRACT(DAY FROM DATA_VENCIMENTO) = 24 AND EXTRACT(MONTH FROM DATA_VENCIMENTO) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM DATA_VENCIMENTO) = EXTRACT(YEAR FROM SYSDATE) AND VALOR_SALDO > 0\n"
            "   Nota: QUANTAS = apenas contar (COUNT)\n"
            "\n"
            "12. Títulos que vencem dia 15 de março (dia + mês, sem ano - LISTAR, limite 10):\n"
            "   SELECT * FROM (SELECT TITULO, NOME_FORNECEDOR, VALOR_SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_APAGAR WHERE EXTRACT(DAY FROM DATA_VENCIMENTO) = 15 AND EXTRACT(MONTH FROM DATA_VENCIMENTO) = 3 AND EXTRACT(YEAR FROM DATA_VENCIMENTO) = EXTRACT(YEAR FROM SYSDATE) AND VALOR_SALDO > 0) WHERE ROWNUM <= 10\n"
            "   Nota: Usa ano ATUAL quando usuário omite!\n"
            "\n"
            "=== EXEMPLO ERRADO (NUNCA FAÇA ASSIM) ===\n"
            "ERRADO: SELECT ... WHERE ... ORDER BY ... WHERE ROWNUM <= 1  [ERRADO] (dois WHERE!)\n"
            "CORRETO: SELECT * FROM (SELECT ... WHERE ... ORDER BY ...) WHERE ROWNUM <= 1  [CORRETO] (subquery)\n"
        )

    def build_user_prompt(self, question: str, schema_text: str, constraints: Optional[str]) -> str:
        parts = []
        parts.append("Contexto do Schema (Oracle 11g):")
        parts.append(schema_text)
        parts.append("")
        parts.append("Instruções OBRIGATÓRIAS:")
        parts.append("- Retorne apenas o SQL final, sem explicações.")
        parts.append("- Somente SELECT. Sem ponto-e-vírgula no fim.")
        parts.append("- Use apenas as colunas existentes no schema.")
        parts.append("")
        parts.append("LIMITAÇÃO DE LINHAS (CRÍTICO):")
        parts.append("REGRA #1: NUNCA use ROWNUM em queries de AGREGAÇÃO (SUM, COUNT, AVG, MAX, MIN, GROUP BY)")
        parts.append("   - Agregações já retornam poucos resultados")
        parts.append("   - ROWNUM antes da agregação QUEBRA o resultado!")
        parts.append("   - Exemplo ERRADO: SELECT SUM(VALOR) ... WHERE ROWNUM <= 1  [ERRADO]")
        parts.append("   - Exemplo CORRETO: SELECT SUM(VALOR) ... (sem ROWNUM)  [CORRETO]")
        parts.append("")
        parts.append("Para queries SEM agregação:")
        parts.append("- Se NÃO tem ORDER BY: WHERE ROWNUM <= N no final da query")
        parts.append("- Se TEM ORDER BY: OBRIGATÓRIO usar subquery:")
        parts.append("  SELECT * FROM (SELECT ... ORDER BY ...) WHERE ROWNUM <= N")
        parts.append("- NUNCA coloque WHERE ROWNUM depois de ORDER BY (inválido!)")
        parts.append("- NUNCA faça: ... WHERE x ORDER BY y WHERE ROWNUM (dois WHERE!)")
        parts.append("")
        parts.append("ATENÇÃO ESPECIAL - Filtros de região (DESCRICAO_REGIAO):")
        parts.append("- Formato da região: 'ESTADO - REGIAO detalhes' (ex: 'PE - SERTAO E OESTE P + M + Y')")
        parts.append("- Para todas regiões de um estado: UPPER(DESCRICAO_REGIAO) LIKE 'PE - %'")
        parts.append("- Para região específica: UPPER(DESCRICAO_REGIAO) LIKE 'PE - SERTAO%'")
        parts.append("- NUNCA use '%PE%' (muito abrangente, pega falsos positivos como PELOTAS, PARANA)")
        parts.append("- Sempre começe com 'ESTADO - ' e termine com %")
        parts.append("")
        parts.append("Filtros de nomes (NOME_CLIENTE, NOME_REPRESENTANTE):")
        parts.append("- Use % em ambos os lados: UPPER(coluna) LIKE '%VALOR%'")
        parts.append("- Exemplo: UPPER(NOME_CLIENTE) LIKE '%CONFEC%'")
        parts.append("")
        parts.append("CRÍTICO - Datas relativas (quando usuário omite mês/ano):")
        parts.append("- Se usuário mencionar APENAS DIA (ex: 'dia 24'): usar mês/ano ATUAIS via EXTRACT(...FROM SYSDATE)")
        parts.append("  CORRETO: EXTRACT(DAY FROM coluna) = 24 AND EXTRACT(MONTH FROM coluna) = EXTRACT(MONTH FROM SYSDATE) AND EXTRACT(YEAR FROM coluna) = EXTRACT(YEAR FROM SYSDATE)")
        parts.append("  ERRADO: TO_DATE('24-10-2023', 'DD-MM-YYYY') [ERRADO] (ano fixo!)")
        parts.append("- Se mencionar DIA+MÊS (ex: '24 de outubro'): usar ano ATUAL via EXTRACT(YEAR FROM SYSDATE)")
        parts.append("- NUNCA use datas hardcoded no passado (2023, 2022, etc)!")
        parts.append("")
        parts.append("CRÍTICO - Diferencie QUAIS (listar) vs QUANTAS (contar):")
        parts.append("- QUAIS/LISTE/MOSTRE = SELECT com colunas específicas")
        parts.append("- QUANTAS/QUANTIDADE/TOTAL = SELECT COUNT(*) AS total")
        parts.append("- Exemplos:")
        parts.append("  * 'QUAIS títulos a pagar vencem...' → SELECT TITULO, NOME_FORNECEDOR, VALOR_SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_APAGAR...")
        parts.append("  * 'QUANTAS duplicatas a pagar vencem...' → SELECT COUNT(*) AS total FROM VW_RAG_CONTAS_APAGAR...")
        parts.append("  * 'QUAIS duplicatas a receber vencem...' → SELECT FATURA, NOME_CLIENTE, SALDO, DATA_VENCIMENTO FROM VW_RAG_CONTAS_RECEBER...")
        parts.append("  * 'QUANTAS duplicatas a receber vencem...' → SELECT COUNT(*) AS total FROM VW_RAG_CONTAS_RECEBER...")
        parts.append("")
        if constraints:
            parts.append("Restrições/Contexto adicional:")
            parts.append(constraints)
            parts.append("")
        parts.append(f"Pergunta: {question}")
        parts.append("")
        parts.append("Responda somente com um SELECT Oracle 11g válido.")
        return "\n".join(parts)

    def generate_sql(self, question: str, schema_text: str, constraints: Optional[str] = None) -> str:
        """
        Gera SQL via LLM (ou heurística se indisponível)
        """
        if not self.client or not getattr(self.client, 'client', None):
            # Heurística simples: retorna SELECT básico, usuário pode editar
            logger.info("LLM indisponível, retornando SQL heurístico")
            return (
                "SELECT NUMERO_PEDIDO, NOME_CLIENTE, NOME_REPRESENTANTE, VALOR_ITEM_LIQUIDO, DATA_VENDA "
                "FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA"
            )

        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(question, schema_text, constraints)

        try:
            response = self.client.client.chat.completions.create(
                model=self.client.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=600,
            )
            content = response.choices[0].message.content.strip()
            sql = self._extract_sql(content)
            return sql
        except Exception as e:
            logger.error(f"Erro ao gerar SQL via LLM: {e}")
            # Fallback heurístico
            return (
                "SELECT NUMERO_PEDIDO, NOME_CLIENTE, NOME_REPRESENTANTE, VALOR_ITEM_LIQUIDO, DATA_VENDA "
                "FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA"
            )

    def _extract_sql(self, content: str) -> str:
        """Extrai SQL de possíveis blocos de código ou retorna conteúdo direto"""
        import re
        # Captura bloco ```sql ... ```
        match = re.search(r"```sql[\s\S]*?```", content, re.IGNORECASE)
        if match:
            block = match.group(0)
            sql = re.sub(r"```sql|```", "", block, flags=re.IGNORECASE).strip()
            return sql
        # Captura bloco ``` ... ```
        match = re.search(r"```[\s\S]*?```", content)
        if match:
            block = match.group(0)
            sql = re.sub(r"```", "", block).strip()
            return sql
        # Caso contrário, assume que todo o conteúdo é o SQL
        return content.strip()