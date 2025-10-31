# tests/unit/test_sql_validator.py
"""
Testes unitarios para SQLValidator
Valida seguranca SQL, deteccao de SQL injection e aplicacao de limites
"""

import pytest
from sql.sql_validator import SQLValidator


@pytest.mark.unit
class TestSQLValidator:
    """Testes para SQLValidator"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup executado antes de cada teste"""
        self.validator = SQLValidator()
    
    # ============================================
    # TESTES - QUERIES VALIDAS
    # ============================================
    
    def test_valid_simple_select(self):
        """Testa SELECT simples valido"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
        assert 'SELECT' in result
    
    def test_valid_select_with_where(self):
        """Testa SELECT com WHERE"""
        sql = "SELECT PEDIDO, VALOR FROM VW_RAG_VENDAS_ESTRUTURADA WHERE VALOR > 1000"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    def test_valid_select_with_join(self):
        """Testa SELECT com JOIN"""
        sql = """
        SELECT v.PEDIDO, v.VALOR
        FROM VW_RAG_VENDAS_ESTRUTURADA v
        JOIN VW_RAG_CONTAS_RECEBER c ON v.PEDIDO = c.PEDIDO
        """
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    def test_valid_select_with_aggregation(self):
        """Testa SELECT com agregacao"""
        sql = "SELECT SUM(VALOR) AS total FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    def test_valid_select_with_group_by(self):
        """Testa SELECT com GROUP BY"""
        sql = "SELECT REGIAO, COUNT(*) FROM VW_RAG_VENDAS_ESTRUTURADA GROUP BY REGIAO"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    def test_valid_select_with_case(self):
        """Testa SELECT com CASE WHEN"""
        sql = """
        SELECT PEDIDO,
               CASE WHEN VALOR > 1000 THEN 'ALTO' ELSE 'BAIXO' END AS categoria
        FROM VW_RAG_VENDAS_ESTRUTURADA
        """
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    def test_valid_select_fully_qualified(self):
        """Testa SELECT com schema qualificado"""
        sql = "SELECT * FROM INDUSTRIAL.VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    def test_valid_select_with_rownum(self):
        """Testa SELECT com ROWNUM existente"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA WHERE ROWNUM <= 10"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
    
    # ============================================
    # TESTES - QUERIES INVALIDAS (DDL)
    # ============================================
    
    def test_invalid_drop_table(self):
        """Testa bloqueio de DROP TABLE"""
        sql = "DROP TABLE VW_RAG_VENDAS_ESTRUTURADA"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'SELECT' in reason or 'DROP' in reason
    
    def test_invalid_create_table(self):
        """Testa bloqueio de CREATE TABLE"""
        sql = "CREATE TABLE test_table (id NUMBER)"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
    
    def test_invalid_alter_table(self):
        """Testa bloqueio de ALTER TABLE"""
        sql = "ALTER TABLE VW_RAG_VENDAS_ESTRUTURADA ADD COLUMN test VARCHAR(10)"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        # Aceita qualquer mensagem de erro (ALTER ou SELECT)
    
    def test_invalid_truncate(self):
        """Testa bloqueio de TRUNCATE"""
        sql = "TRUNCATE TABLE VW_RAG_VENDAS_ESTRUTURADA"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
    
    # ============================================
    # TESTES - QUERIES INVALIDAS (DML)
    # ============================================
    
    def test_invalid_insert(self):
        """Testa bloqueio de INSERT"""
        sql = "INSERT INTO VW_RAG_VENDAS_ESTRUTURADA VALUES (1, 2, 3)"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'INSERT' in reason or 'SELECT' in reason
    
    def test_invalid_update(self):
        """Testa bloqueio de UPDATE"""
        sql = "UPDATE VW_RAG_VENDAS_ESTRUTURADA SET VALOR = 0 WHERE PEDIDO = '123'"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'UPDATE' in reason or 'SELECT' in reason
    
    def test_invalid_delete(self):
        """Testa bloqueio de DELETE"""
        sql = "DELETE FROM VW_RAG_VENDAS_ESTRUTURADA WHERE PEDIDO = '123'"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'DELETE' in reason or 'SELECT' in reason
    
    def test_invalid_merge(self):
        """Testa bloqueio de MERGE"""
        sql = "MERGE INTO VW_RAG_VENDAS_ESTRUTURADA USING ..."
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
    
    # ============================================
    # TESTES - SQL INJECTION
    # ============================================
    
    def test_injection_multiple_statements(self):
        """Testa bloqueio de multiplos statements"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA; DROP TABLE test;"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'ultiplos' in reason or 'statements' in reason
    
    def test_injection_select_into(self):
        """Testa bloqueio de SELECT INTO"""
        sql = "SELECT * INTO temp_table FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'INTO' in reason
    
    def test_injection_dblink(self):
        """Testa bloqueio de database links"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA@remote_db"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'link' in reason.lower()
    
    def test_injection_plsql_block(self):
        """Testa bloqueio de blocos PL/SQL"""
        sql = "BEGIN EXECUTE IMMEDIATE 'DROP TABLE test'; END;"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        # Bloqueado por multiplos statements ou BEGIN
    
    def test_injection_execute_immediate(self):
        """Testa bloqueio de EXECUTE IMMEDIATE"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA WHERE EXECUTE IMMEDIATE"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'EXECUTE' in reason
    
    def test_injection_dbms_packages(self):
        """Testa bloqueio de pacotes DBMS_*"""
        # Nota: O validador atual bloqueia DBMS_ como palavra, mas nao em funcoes
        # Este teste documenta o comportamento atual
        sql = "SELECT DBMS_CRYPTO FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, reason = self.validator.is_safe_select(sql)
        
        # Deve bloquear DBMS_ como palavra-chave
        assert ok is False
    
    def test_injection_utl_packages(self):
        """Testa bloqueio de pacotes UTL_*"""
        # Nota: O validador atual bloqueia UTL_ como palavra, mas nao em funcoes
        sql = "SELECT UTL_FILE FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, reason = self.validator.is_safe_select(sql)
        
        # Deve bloquear UTL_ como palavra-chave
        assert ok is False
    
    # ============================================
    # TESTES - OBJETOS NAO PERMITIDOS
    # ============================================
    
    def test_invalid_unknown_table(self):
        """Testa bloqueio de tabela nao autorizada"""
        sql = "SELECT * FROM UNKNOWN_TABLE"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
        assert 'permitido' in reason.lower()
    
    def test_invalid_system_table(self):
        """Testa bloqueio de tabelas de sistema"""
        sql = "SELECT * FROM ALL_USERS"
        ok, reason = self.validator.is_safe_select(sql)
        
        assert ok is False
    
    def test_invalid_dual_with_function(self):
        """Testa bloqueio de tabelas nao autorizadas"""
        sql = "SELECT * FROM DUAL"
        ok, reason = self.validator.is_safe_select(sql)
        
        # DUAL nao esta na lista de objetos permitidos
        assert ok is False
    
    # ============================================
    # TESTES - ENFORCE LIMIT
    # ============================================
    
    def test_enforce_limit_adds_rownum(self):
        """Testa adicao de ROWNUM quando ausente"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA"
        limited = self.validator.enforce_limit(sql, limit=10)
        
        assert 'ROWNUM' in limited.upper()
        assert '10' in limited
    
    def test_enforce_limit_preserves_existing_rownum(self):
        """Testa que ROWNUM existente nao eh duplicado"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA WHERE ROWNUM <= 5"
        limited = self.validator.enforce_limit(sql, limit=10)
        
        # Nao deve embrulhar novamente
        assert limited.count('ROWNUM') == 1
    
    def test_enforce_limit_custom_value(self):
        """Testa limite customizado"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA"
        limited = self.validator.enforce_limit(sql, limit=50)
        
        assert '50' in limited
    
    # ============================================
    # TESTES - SANITIZE AND LIMIT
    # ============================================
    
    def test_sanitize_and_limit_valid_query(self):
        """Testa sanitizacao completa de query valida"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.sanitize_and_limit(sql, limit=10)
        
        assert ok is True
        assert 'ROWNUM' in result.upper()
    
    def test_sanitize_and_limit_invalid_query(self):
        """Testa que query invalida eh rejeitada"""
        sql = "DROP TABLE VW_RAG_VENDAS_ESTRUTURADA"
        ok, reason = self.validator.sanitize_and_limit(sql)
        
        assert ok is False
    
    def test_sanitize_and_limit_aggregation_no_limit(self):
        """Testa que agregacoes nao recebem ROWNUM automatico"""
        sql = "SELECT COUNT(*) FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.sanitize_and_limit(sql, limit=10)
        
        assert ok is True
        # Nao deve adicionar ROWNUM em agregacoes
        assert 'ROWNUM' not in result.upper()
    
    def test_sanitize_and_limit_force_on_aggregation(self):
        """Testa forca de limite em agregacao"""
        sql = "SELECT COUNT(*) FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.sanitize_and_limit(sql, limit=10, force_limit=True)
        
        assert ok is True
        assert 'ROWNUM' in result.upper()
    
    # ============================================
    # TESTES - COMENTARIOS
    # ============================================
    
    def test_strips_line_comments(self):
        """Testa remocao de comentarios de linha"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA -- comentario"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
        assert '--' not in result
    
    def test_strips_block_comments(self):
        """Testa remocao de comentarios de bloco"""
        sql = "SELECT * /* comentario */ FROM VW_RAG_VENDAS_ESTRUTURADA"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
        assert '/*' not in result
    
    def test_strips_malicious_comment(self):
        """Testa que comentarios nao escondem codigo malicioso"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA /* ; DROP TABLE test; */"
        ok, result = self.validator.is_safe_select(sql)
        
        # Comentario eh removido, query deve ser valida
        assert ok is True
    
    # ============================================
    # TESTES - CASOS EXTREMOS
    # ============================================
    
    def test_empty_sql(self):
        """Testa SQL vazio"""
        ok, reason = self.validator.is_safe_select("")
        
        assert ok is False
        assert 'vazio' in reason.lower()
    
    def test_none_sql(self):
        """Testa SQL None"""
        ok, reason = self.validator.is_safe_select(None)
        
        assert ok is False
    
    def test_whitespace_only(self):
        """Testa SQL com apenas espacos"""
        ok, reason = self.validator.is_safe_select("   \n\t  ")
        
        assert ok is False
    
    def test_case_insensitive_keywords(self):
        """Testa que validacao eh case-insensitive"""
        sql_lower = "select * from vw_rag_vendas_estruturada"
        sql_upper = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA"
        sql_mixed = "SeLeCt * FrOm Vw_RaG_VeNdAs_EsTrUtUrAdA"
        
        ok1, _ = self.validator.is_safe_select(sql_lower)
        ok2, _ = self.validator.is_safe_select(sql_upper)
        ok3, _ = self.validator.is_safe_select(sql_mixed)
        
        assert ok1 is True
        assert ok2 is True
        assert ok3 is True
    
    def test_trailing_semicolon_removed(self):
        """Testa que ponto-e-virgula final eh removido"""
        sql = "SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA;"
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True
        assert not result.endswith(';')
    
    def test_complex_subquery(self):
        """Testa query com subquery complexa"""
        sql = """
        SELECT pedido, valor
        FROM (
            SELECT pedido, valor, RANK() OVER (ORDER BY valor DESC) as rank
            FROM VW_RAG_VENDAS_ESTRUTURADA
        )
        WHERE rank <= 10
        """
        ok, result = self.validator.is_safe_select(sql)
        
        assert ok is True


@pytest.mark.unit
@pytest.mark.parametrize("sql,should_be_valid", [
    ("SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA", True),
    ("DROP TABLE VW_RAG_VENDAS_ESTRUTURADA", False),
    ("UPDATE VW_RAG_VENDAS_ESTRUTURADA SET VALOR = 0", False),
    ("DELETE FROM VW_RAG_VENDAS_ESTRUTURADA", False),
    ("INSERT INTO VW_RAG_VENDAS_ESTRUTURADA VALUES (1)", False),
    ("SELECT * FROM UNKNOWN_TABLE", False),
    ("SELECT * FROM VW_RAG_VENDAS_ESTRUTURADA; DROP TABLE test;", False),
    ("SELECT DBMS_CRYPTO.HASH('x') FROM DUAL", False),
])
class TestSQLValidatorParametrizado:
    """Testes parametrizados para validacao SQL"""
    
    def test_sql_validation_parametrizada(self, sql, should_be_valid):
        """Testa validacao parametrizada"""
        validator = SQLValidator()
        ok, _ = validator.is_safe_select(sql)
        
        assert ok == should_be_valid
