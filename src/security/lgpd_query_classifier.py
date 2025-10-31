# src/security/lgpd_query_classifier.py
"""
LGPD Query Classifier
Classifies user queries (natural language) by data sensitivity level according to LGPD compliance.

Single Responsibility: Only classify LGPD sensitivity levels from user queries.

For classifying structured data (CSV/database records), use data_processing.lgpd_data_classifier.LGPDDataClassifier
"""

import logging
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class LGPDLevel(Enum):
    """LGPD data sensitivity levels"""
    BAIXO = "BAIXO"      # Public/aggregated data
    MEDIO = "MEDIO"      # Order numbers, values (no customer names)
    ALTO = "ALTO"        # Customer names, personal data


@dataclass(frozen=True)
class LGPDClassification:
    """Immutable classification result"""
    level: LGPDLevel
    confidence: float
    reason: str
    
    def is_sensitive(self) -> bool:
        """Check if data is considered sensitive (MEDIO or ALTO)"""
        return self.level in (LGPDLevel.MEDIO, LGPDLevel.ALTO)


class LGPDQueryClassifier:
    """
    Classifies queries according to LGPD sensitivity.
    
    Uses pattern matching to determine data sensitivity level.
    Clean, focused, single responsibility.
    """
    
    # Patterns that indicate HIGH sensitivity (personal data)
    HIGH_PATTERNS = [
        r'\bnome\s+do\s+cliente\b',
        r'\bcliente\s+\w+',
        r'\bquem\s+(comprou|vendeu)',
        r'\bpessoa\b',
        r'\bcontato\b',
        r'\btelefone\b',
        r'\bemail\b',
        r'\bcpf\b',
        r'\bcnpj\s+do\s+cliente\b',
        r'\bnome\s+do\s+fornecedor\b',
        r'\bfornecedor\s+\w+',
        r'\bcnpj\s+do\s+fornecedor\b',
    ]
    
    # Patterns that indicate MEDIUM sensitivity (transactional data)
    MEDIUM_PATTERNS = [
        r'\bpedido\s+\d+',
        r'\bn[uú]mero\s+do\s+pedido\b',
        r'\bvalor\s+(do|total|líquido|bruto)',
        r'\bfatura\b',
        r'\bvenda\s+de\b',
        r'\btransação\b',
        r'\bpagamento\b',
        r'\bcontas?\s+a\s+pagar\b',
        r'\bt[íi]tulos?\s+(a\s+pagar|vencidos?|em\s+aberto|vencem)',
        r'\bt[íi]tulos?\s+\d+',
        r'\bquais\s+t[íi]tulos?\b',
        r'\bfornecedores?\b',
        r'\bvencimento\b',
        r'\bvenc(e|em|idos?)\b',
        r'\bsaldo\s+(devedor|pendente|a\s+pagar)\b',
        r'\bdespesas?\b',
        r'\bgrupo\s+de\s+despesa\b',
        r'\bsubgrupo\s+de\s+despesa\b',
        r'\bcontas?\s+a\s+receber\b',
        r'\bduplicatas?\s+(a\s+receber|vencidas?|em\s+aberto|vencem)',
        r'\bduplicatas?\s+\d+',
        r'\bquais\s+duplicatas?\b',
        r'\brecebimentos?\b',
        r'\bsaldo\s+(a\s+receber|pendente)\b',
        r'\bfaturas?\b',
        r'\breceber\s+(de|do)\b',
    ]
    
    # Patterns that indicate LOW sensitivity (aggregated/public)
    LOW_PATTERNS = [
        r'\btotal\s+de\s+vendas\b',
        r'\branking\b',
        r'\bagregad[oa]\b',
        r'\bmédia\b',
        r'\bsoma\b',
        r'\bcount\b',
        r'\brelatório\b',
        r'\bestatística\b',
        r'\bregião\b',
    ]
    
    def __init__(self):
        """Initialize classifier with compiled patterns for performance"""
        self._high_patterns = [re.compile(p, re.IGNORECASE) for p in self.HIGH_PATTERNS]
        self._medium_patterns = [re.compile(p, re.IGNORECASE) for p in self.MEDIUM_PATTERNS]
        self._low_patterns = [re.compile(p, re.IGNORECASE) for p in self.LOW_PATTERNS]
        
        logger.debug("LGPDQueryClassifier initialized")
    
    def classify(self, query: str) -> LGPDClassification:
        """
        Classify query by LGPD sensitivity level.
        
        Args:
            query: User query string
            
        Returns:
            LGPDClassification with level, confidence, and reason
        """
        if not query or not query.strip():
            return self._create_default_classification()
        
        query_lower = query.lower()
        
        # Check HIGH sensitivity first (most restrictive)
        high_matches = sum(1 for p in self._high_patterns if p.search(query_lower))
        if high_matches > 0:
            confidence = min(0.7 + (high_matches * 0.1), 1.0)
            return LGPDClassification(
                level=LGPDLevel.ALTO,
                confidence=confidence,
                reason=f"Contains personal data identifiers ({high_matches} match(es))"
            )
        
        # Check MEDIUM sensitivity
        medium_matches = sum(1 for p in self._medium_patterns if p.search(query_lower))
        if medium_matches > 0:
            confidence = min(0.6 + (medium_matches * 0.1), 0.95)
            return LGPDClassification(
                level=LGPDLevel.MEDIO,
                confidence=confidence,
                reason=f"Contains transactional data ({medium_matches} match(es))"
            )
        
        # Check LOW sensitivity
        low_matches = sum(1 for p in self._low_patterns if p.search(query_lower))
        if low_matches > 0:
            confidence = min(0.5 + (low_matches * 0.1), 0.9)
            return LGPDClassification(
                level=LGPDLevel.BAIXO,
                confidence=confidence,
                reason=f"Aggregated/public data query ({low_matches} match(es))"
            )
        
        # Default: assume MEDIUM for safety (conservative approach)
        return LGPDClassification(
            level=LGPDLevel.MEDIO,
            confidence=0.4,
            reason="No clear pattern match - defaulting to MEDIO for safety"
        )
    
    def _create_default_classification(self) -> LGPDClassification:
        """Create safe default classification for empty/invalid queries"""
        return LGPDClassification(
            level=LGPDLevel.MEDIO,
            confidence=0.3,
            reason="Empty query - default to MEDIO"
        )


class LGPDPermissionChecker:
    """
    Checks if user has permission to access data at given LGPD level.
    
    Single Responsibility: Only permission checking.
    """
    
    LEVEL_HIERARCHY = {
        LGPDLevel.BAIXO: 0,
        LGPDLevel.MEDIO: 1,
        LGPDLevel.ALTO: 2
    }
    
    @classmethod
    def check_permission(cls, 
                        required_level: LGPDLevel, 
                        user_context: Optional[dict] = None) -> bool:
        """
        Check if user has permission for required LGPD level.
        
        Args:
            required_level: Minimum required LGPD level
            user_context: User context with 'lgpd_clearance' key
            
        Returns:
            True if user has sufficient clearance
        """
        if not user_context:
            # No context = only BAIXO access (conservative)
            return required_level == LGPDLevel.BAIXO
        
        user_clearance_str = user_context.get('lgpd_clearance', 'BAIXO')
        
        # Convert string to enum
        try:
            user_clearance = LGPDLevel(user_clearance_str)
        except ValueError:
            logger.warning(f"Invalid clearance level: {user_clearance_str}, defaulting to BAIXO")
            user_clearance = LGPDLevel.BAIXO
        
        user_level = cls.LEVEL_HIERARCHY[user_clearance]
        required_level_value = cls.LEVEL_HIERARCHY[required_level]
        
        return user_level >= required_level_value
    
    @classmethod
    def get_required_clearance_message(cls, required_level: LGPDLevel) -> str:
        """Get user-friendly message for permission denial"""
        messages = {
            LGPDLevel.BAIXO: "Esta consulta requer acesso básico.",
            LGPDLevel.MEDIO: "Esta consulta requer acesso a dados transacionais.",
            LGPDLevel.ALTO: "Esta consulta requer acesso a dados pessoais sensíveis."
        }
        return messages.get(required_level, "Acesso negado.")
