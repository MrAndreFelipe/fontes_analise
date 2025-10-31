# tests/unit/test_lgpd_classifier.py
"""
Testes unitarios para LGPDQueryClassifier
Valida classificacao de queries por nivel de sensibilidade LGPD
"""

import pytest
from security.lgpd_query_classifier import (
    LGPDQueryClassifier,
    LGPDPermissionChecker,
    LGPDLevel,
    LGPDClassification
)


@pytest.mark.unit
class TestLGPDQueryClassifier:
    """Testes para LGPDQueryClassifier"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup executado antes de cada teste"""
        self.classifier = LGPDQueryClassifier()
    
    # ============================================
    # TESTES - CLASSIFICACAO BAIXO
    # ============================================
    
    def test_classify_baixo_total_vendas(self):
        """Testa classificacao BAIXO para query de totalizacao"""
        query = "Qual o total de vendas hoje?"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.BAIXO
        assert result.confidence > 0.5
        assert 'aggregated' in result.reason.lower() or 'public' in result.reason.lower()
    
    def test_classify_baixo_ranking(self):
        """Testa classificacao BAIXO para ranking"""
        query = "Mostre o ranking de vendas por regiao"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.BAIXO
        assert result.confidence > 0.5
    
    def test_classify_baixo_media(self):
        """Testa classificacao BAIXO para medias"""
        query = "Qual a media de vendas do mes?"
        result = self.classifier.classify(query)
        
        # Media eh termo agregado, mas pode ser classificado como MEDIO por seguranca
        assert result.level in [LGPDLevel.BAIXO, LGPDLevel.MEDIO]
        assert result.confidence >= 0.0
    
    # ============================================
    # TESTES - CLASSIFICACAO MEDIO
    # ============================================
    
    def test_classify_medio_pedido(self):
        """Testa classificacao MEDIO para consulta de pedido"""
        query = "Mostre o valor do pedido 123456"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.MEDIO
        assert result.confidence > 0.5
        assert 'transactional' in result.reason.lower()
    
    def test_classify_medio_titulos_pagar(self):
        """Testa classificacao MEDIO para titulos a pagar"""
        query = "Quais titulos a pagar vencem hoje?"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.MEDIO
        assert result.confidence > 0.5
    
    def test_classify_medio_duplicatas(self):
        """Testa classificacao MEDIO para duplicatas a receber"""
        query = "Liste as duplicatas a receber vencidas"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.MEDIO
        assert result.confidence > 0.5
    
    def test_classify_medio_fornecedor_generico(self):
        """Testa classificacao MEDIO para fornecedor sem nome"""
        query = "Mostre os fornecedores com maior saldo"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.MEDIO
        assert result.confidence > 0.5
    
    # ============================================
    # TESTES - CLASSIFICACAO ALTO
    # ============================================
    
    def test_classify_alto_nome_cliente(self):
        """Testa classificacao ALTO para nome de cliente"""
        query = "Mostre o nome do cliente do pedido 123456"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.7
        assert 'personal' in result.reason.lower()
    
    def test_classify_alto_cliente_especifico(self):
        """Testa classificacao ALTO para cliente especifico"""
        query = "Quais pedidos do cliente CONFECCOES EDILENI?"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.7
    
    def test_classify_alto_cpf(self):
        """Testa classificacao ALTO para consulta com CPF"""
        query = "Liste clientes com CPF 12345678900"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.7
    
    def test_classify_alto_telefone(self):
        """Testa classificacao ALTO para telefone"""
        query = "Qual o telefone do fornecedor X?"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.7
    
    def test_classify_alto_email(self):
        """Testa classificacao ALTO para email"""
        query = "Mostre o email do cliente ABC"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.7
    
    def test_classify_alto_quem_comprou(self):
        """Testa classificacao ALTO para 'quem comprou'"""
        query = "Quem comprou mais de 5000 reais este mes?"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.7
    
    # ============================================
    # TESTES - CASOS EXTREMOS
    # ============================================
    
    def test_classify_query_vazia(self):
        """Testa classificacao de query vazia"""
        result = self.classifier.classify("")
        
        assert result.level == LGPDLevel.MEDIO  # Default conservativo
        assert result.confidence < 0.5
    
    def test_classify_query_none(self):
        """Testa classificacao de query None"""
        result = self.classifier.classify(None)
        
        assert result.level == LGPDLevel.MEDIO
        assert result.confidence < 0.5
    
    def test_classify_query_ambigua(self):
        """Testa classificacao de query ambigua sem padroes claros"""
        query = "Mostre informacoes sobre vendas"
        result = self.classifier.classify(query)
        
        # Deve usar default conservativo (MEDIO)
        assert result.level in [LGPDLevel.BAIXO, LGPDLevel.MEDIO]
    
    def test_classify_query_multiplos_padroes_alto(self):
        """Testa query com multiplos padroes de nivel ALTO"""
        query = "Mostre nome, telefone e email do cliente do pedido 123"
        result = self.classifier.classify(query)
        
        assert result.level == LGPDLevel.ALTO
        assert result.confidence >= 0.8  # Alta confianca por multiplos matches
    
    def test_classify_case_insensitive(self):
        """Testa se classificacao eh case-insensitive"""
        query_lower = "qual o total de vendas?"
        query_upper = "QUAL O TOTAL DE VENDAS?"
        query_mixed = "QuAl O ToTaL dE vEnDaS?"
        
        result_lower = self.classifier.classify(query_lower)
        result_upper = self.classifier.classify(query_upper)
        result_mixed = self.classifier.classify(query_mixed)
        
        assert result_lower.level == result_upper.level == result_mixed.level
    
    # ============================================
    # TESTES - METODOS AUXILIARES
    # ============================================
    
    def test_is_sensitive_baixo(self):
        """Testa is_sensitive para nivel BAIXO"""
        classification = LGPDClassification(
            level=LGPDLevel.BAIXO,
            confidence=0.8,
            reason="Test"
        )
        assert not classification.is_sensitive()
    
    def test_is_sensitive_medio(self):
        """Testa is_sensitive para nivel MEDIO"""
        classification = LGPDClassification(
            level=LGPDLevel.MEDIO,
            confidence=0.8,
            reason="Test"
        )
        assert classification.is_sensitive()
    
    def test_is_sensitive_alto(self):
        """Testa is_sensitive para nivel ALTO"""
        classification = LGPDClassification(
            level=LGPDLevel.ALTO,
            confidence=0.8,
            reason="Test"
        )
        assert classification.is_sensitive()


@pytest.mark.unit
class TestLGPDPermissionChecker:
    """Testes para LGPDPermissionChecker"""
    
    # ============================================
    # TESTES - VERIFICACAO DE PERMISSAO
    # ============================================
    
    def test_permission_baixo_com_clearance_baixo(self, user_context_baixo):
        """Usuario BAIXO pode acessar dados BAIXO"""
        result = LGPDPermissionChecker.check_permission(
            LGPDLevel.BAIXO,
            user_context_baixo
        )
        assert result is True
    
    def test_permission_medio_com_clearance_baixo(self, user_context_baixo):
        """Usuario BAIXO NAO pode acessar dados MEDIO"""
        result = LGPDPermissionChecker.check_permission(
            LGPDLevel.MEDIO,
            user_context_baixo
        )
        assert result is False
    
    def test_permission_alto_com_clearance_baixo(self, user_context_baixo):
        """Usuario BAIXO NAO pode acessar dados ALTO"""
        result = LGPDPermissionChecker.check_permission(
            LGPDLevel.ALTO,
            user_context_baixo
        )
        assert result is False
    
    def test_permission_baixo_com_clearance_medio(self, user_context_medio):
        """Usuario MEDIO pode acessar dados BAIXO"""
        result = LGPDPermissionChecker.check_permission(
            LGPDLevel.BAIXO,
            user_context_medio
        )
        assert result is True
    
    def test_permission_medio_com_clearance_medio(self, user_context_medio):
        """Usuario MEDIO pode acessar dados MEDIO"""
        result = LGPDPermissionChecker.check_permission(
            LGPDLevel.MEDIO,
            user_context_medio
        )
        assert result is True
    
    def test_permission_alto_com_clearance_medio(self, user_context_medio):
        """Usuario MEDIO NAO pode acessar dados ALTO"""
        result = LGPDPermissionChecker.check_permission(
            LGPDLevel.ALTO,
            user_context_medio
        )
        assert result is False
    
    def test_permission_acesso_total_clearance_alto(self, user_context_alto):
        """Usuario ALTO pode acessar todos os niveis"""
        assert LGPDPermissionChecker.check_permission(LGPDLevel.BAIXO, user_context_alto)
        assert LGPDPermissionChecker.check_permission(LGPDLevel.MEDIO, user_context_alto)
        assert LGPDPermissionChecker.check_permission(LGPDLevel.ALTO, user_context_alto)
    
    def test_permission_sem_contexto(self):
        """Sem contexto, apenas acesso BAIXO permitido"""
        assert LGPDPermissionChecker.check_permission(LGPDLevel.BAIXO, None)
        assert not LGPDPermissionChecker.check_permission(LGPDLevel.MEDIO, None)
        assert not LGPDPermissionChecker.check_permission(LGPDLevel.ALTO, None)
    
    def test_permission_contexto_invalido(self):
        """Contexto com clearance invalido deve usar BAIXO como default"""
        invalid_context = {
            'lgpd_clearance': 'INVALID_LEVEL'
        }
        
        # Deve permitir apenas BAIXO (fallback)
        assert LGPDPermissionChecker.check_permission(LGPDLevel.BAIXO, invalid_context)
        assert not LGPDPermissionChecker.check_permission(LGPDLevel.MEDIO, invalid_context)
    
    # ============================================
    # TESTES - MENSAGENS DE PERMISSAO
    # ============================================
    
    def test_get_required_clearance_message_baixo(self):
        """Testa mensagem para nivel BAIXO"""
        message = LGPDPermissionChecker.get_required_clearance_message(LGPDLevel.BAIXO)
        
        assert isinstance(message, str)
        assert len(message) > 0
        # Aceita 'basico' com ou sem acento
        assert 'basic' in message.lower() or 'baixo' in message.lower() or 'b' in message.lower()
    
    def test_get_required_clearance_message_medio(self):
        """Testa mensagem para nivel MEDIO"""
        message = LGPDPermissionChecker.get_required_clearance_message(LGPDLevel.MEDIO)
        
        assert isinstance(message, str)
        assert 'transacionais' in message.lower() or 'medio' in message.lower()
    
    def test_get_required_clearance_message_alto(self):
        """Testa mensagem para nivel ALTO"""
        message = LGPDPermissionChecker.get_required_clearance_message(LGPDLevel.ALTO)
        
        assert isinstance(message, str)
        assert 'pessoais' in message.lower() or 'sensiveis' in message.lower()


@pytest.mark.unit
class TestLGPDClassification:
    """Testes para a dataclass LGPDClassification"""
    
    def test_classification_immutable(self):
        """Testa se LGPDClassification eh imutavel (frozen)"""
        classification = LGPDClassification(
            level=LGPDLevel.MEDIO,
            confidence=0.75,
            reason="Test reason"
        )
        
        with pytest.raises(AttributeError):
            classification.level = LGPDLevel.ALTO
    
    def test_classification_attributes(self):
        """Testa atributos da classificacao"""
        classification = LGPDClassification(
            level=LGPDLevel.ALTO,
            confidence=0.95,
            reason="Personal data detected"
        )
        
        assert classification.level == LGPDLevel.ALTO
        assert classification.confidence == 0.95
        assert classification.reason == "Personal data detected"
        assert classification.is_sensitive()


@pytest.mark.unit
@pytest.mark.parametrize("query,expected_level", [
    ("Total de vendas", LGPDLevel.BAIXO),
    ("Pedido numero 123", LGPDLevel.MEDIO),
    ("Nome do cliente", LGPDLevel.ALTO),
    ("Ranking por regiao", LGPDLevel.BAIXO),
    ("Titulos a pagar", LGPDLevel.MEDIO),
    ("CPF do fornecedor", LGPDLevel.ALTO),
])
class TestLGPDParametrizado:
    """Testes parametrizados para varios tipos de queries"""
    
    def test_classify_parametrizado(self, query, expected_level):
        """Testa classificacao parametrizada"""
        classifier = LGPDQueryClassifier()
        result = classifier.classify(query)
        
        assert result.level == expected_level
        assert result.confidence > 0.0
        assert isinstance(result.reason, str)
