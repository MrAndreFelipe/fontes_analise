# src/sql/sql_validator.py
"""
SQL Validator/Sanitizer para Text-to-SQL (Oracle 11g)
Garante segurança (somente SELECT) e aplica limite de linhas via ROWNUM
"""

import re
from typing import Tuple

class SQLValidator:
    """
    Validador de SQL seguro para Oracle 11g
    - Permite apenas SELECT
    - Bloqueia DDL/DML/PLSQL
    - Restringe acesso a views/tabelas permitidas
    - Aplica LIMIT (ROWNUM) se ausente
    """

    # Palavras-chave proibidas (PL/SQL, DDL, DML)
    FORBIDDEN_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'DROP', 'ALTER', 'CREATE', 'RENAME',
        'EXECUTE', 'COMMIT', 'ROLLBACK', 'GRANT', 'REVOKE',
        'TRUNCATE', 'CALL', 'DBMS_', 'UTL_', 'SYNONYM', 'PACKAGE', 'PROCEDURE', 'FUNCTION'
    ]
    
    # Palavras que só são proibidas em contextos específicos
    # BEGIN...END é PL/SQL (proibido), mas CASE...END é SQL válido (permitido)
    CONTEXTUAL_KEYWORDS = {
        'BEGIN': r'\bBEGIN\b(?!.*\bCASE\b)',  # Bloqueia BEGIN se não tiver CASE
        'END': r'\bEND\b(?<!\bCASE\b.*\bEND\b)'  # Permite END após CASE
    }

    # Objetos permitidos (fully qualified ou não)
    ALLOWED_OBJECTS = [
        'INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA',
        'VW_RAG_VENDAS_ESTRUTURADA',
        'INDUSTRIAL.VW_RAG_CONTAS_APAGAR',
        'VW_RAG_CONTAS_APAGAR',
        'INDUSTRIAL.VW_RAG_CONTAS_RECEBER',
        'VW_RAG_CONTAS_RECEBER'
    ]

    def is_safe_select(self, sql: str) -> Tuple[bool, str]:
        """
        Verifica se o SQL é seguro e somente SELECT
        Returns (ok, motivo_ou_sql_limpo)
        """
        if not sql or not sql.strip():
            return False, 'SQL vazio'

        # Remove comentários
        cleaned = self._strip_comments(sql)
        up = cleaned.upper().strip()

        # Sem múltiplos statements
        if ';' in up[:-1]:
            return False, 'Múltiplos statements encontrados'

        # Somente SELECT
        if not up.startswith('SELECT '):
            return False, 'Somente SELECT é permitido'

        # Bloqueia palavras proibidas
        for kw in self.FORBIDDEN_KEYWORDS:
            # DBMS_ e UTL_ sao prefixos: buscar qualquer ocorrencia
            if kw.endswith('_'):
                if kw in up:
                    return False, f'Palavra proibida detectada: {kw}'
            else:
                if re.search(rf'\b{kw}\b', up):
                    return False, f'Palavra proibida detectada: {kw}'
        
        # Verifica BEGIN...END (PL/SQL) mas permite CASE...END (SQL válido)
        if re.search(r'\bBEGIN\b', up) and not re.search(r'\bCASE\b', up):
            return False, 'Bloco PL/SQL BEGIN...END não permitido'

        # Sem SELECT INTO
        if re.search(r'\bSELECT\b.*\bINTO\b', up):
            return False, 'SELECT INTO não permitido'

        # Sem dblink
        if '@' in up:
            return False, 'Database links não permitidos'

        # Verifica objetos referenciados no FROM/JOIN
        # Ignora FROM dentro de funções como EXTRACT(... FROM ...)
        # Ignora aliases (AS nome)
        
        # Estratégia: buscar apenas FROM/JOIN na query principal (não em subqueries)
        # Remove subqueries completas (tudo entre parênteses externos)
        sql_no_subquery = up
        # Remove subqueries aninhadas recursivamente
        while '(' in sql_no_subquery:
            sql_no_subquery = re.sub(r'\([^()]*\)', '', sql_no_subquery)
        
        # Agora busca FROM/JOIN apenas no SQL sem subqueries
        # Mas ignora se vier depois de AS (alias)
        objects = re.findall(r'\bFROM\b\s+([\w\.]+)|\bJOIN\b\s+([\w\.]+)', sql_no_subquery)
        referenced = set([o for pair in objects for o in pair if o and o.upper() != 'AS'])
        
        if referenced:
            for obj in referenced:
                # Ignora palavras reservadas que podem aparecer incorretamente
                if obj.upper() in ['AS', 'WHERE', 'ORDER', 'GROUP', 'SELECT']:
                    continue
                if not any(obj.endswith(allowed) or obj == allowed for allowed in self.ALLOWED_OBJECTS):
                    return False, f'Objeto não permitido: {obj}'

        return True, cleaned.strip().rstrip(';')

    def enforce_limit(self, sql: str, limit: int = 100) -> str:
        """
        Garante que a query tenha LIMIT via ROWNUM (Oracle 11g)
        - Se já usa ROWNUM ou FETCH FIRST, mantém
        - Caso contrário, embrulha a query: SELECT * FROM (<sql>) WHERE ROWNUM <= :limit
        """
        cleaned = sql.strip().rstrip(';').strip()
        up = cleaned.upper()

        if 'ROWNUM' in up or 'FETCH FIRST' in up:
            return cleaned

        # Evita duplicar se já tem WHERE com ROWNUM
        wrapped = f"SELECT * FROM ({cleaned}) WHERE ROWNUM <= {int(limit)}"
        return wrapped

    def sanitize_and_limit(self, sql: str, limit: int = 100, force_limit: bool = False) -> Tuple[bool, str]:
        """Combina validação e aplicação opcional de limite
        
        Args:
            sql: SQL a validar
            limit: Limite máximo de linhas
            force_limit: Se True, força ROWNUM mesmo em agregações (use com cuidado)
        """
        ok, res = self.is_safe_select(sql)
        if not ok:
            return False, res
        
        # Só aplica limite se for forçado OU se a query claramente não tem limite/agregação
        if force_limit:
            return True, self.enforce_limit(res, limit)
        
        # Verifica se já tem limite ou é agregação
        up = res.upper()
        has_limit = 'ROWNUM' in up or 'FETCH FIRST' in up
        is_aggregation = any(
            pattern in up for pattern in ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN(', 'GROUP BY']
        )
        
        if has_limit or is_aggregation:
            # Já tem limite ou é agregação: retorna sem modificar
            return True, res
        
        # Query normal sem limite: aplica ROWNUM
        return True, self.enforce_limit(res, limit)

    def _strip_comments(self, sql: str) -> str:
        """Remove comentários de linha e bloco"""
        # Remove -- comentários
        no_line = re.sub(r'--.*', '', sql)
        # Remove /* */ comentários
        no_block = re.sub(r'/\*.*?\*/', '', no_line, flags=re.S)
        return no_block