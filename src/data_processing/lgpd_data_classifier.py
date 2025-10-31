# src/data_processing/lgpd_data_classifier.py
"""
LGPD Data Classifier
Classifica dados estruturados (registros de CSV/banco de dados) por nível de sensibilidade LGPD
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from core.config import Config
except ImportError:
    # Fallback se config não existir ainda
    class Config:
        LGPD_LEVELS = ["BAIXO", "MÉDIO", "ALTO"]

class LGPDDataClassifier:
    """
    Classificador automático de níveis LGPD para dados estruturados
    Baseado nas especificações do TCC para conformidade com LGPD
    
    Use este classificador para registros de CSV ou banco de dados.
    Para classificar queries de usuário, use security.lgpd_query_classifier.LGPDQueryClassifier
    """
    
    def __init__(self):
        """Inicializa com as regras de classificação"""
        
        # Campos que caracterizam cada nível de sensibilidade
        self.sensitive_fields = {
            'ALTO': [
                # Dados identificadores diretos (Art. 5º, I da LGPD)
                'CNPJ_CLIENTE', 'NOME_CLIENTE', 'CPF', 'RG',
                'EMAIL', 'TELEFONE', 'ENDERECO', 'RAZAO_SOCIAL',
                'INSCRICAO_ESTADUAL', 'DOCUMENTO', 'IDENTIFICACAO'
            ],
            'MÉDIO': [
                # Dados financeiros e comerciais sensíveis
                'VALOR_ITEM_LIQUIDO', 'VALOR_ITEM_BRUTO', 'VALOR',
                'CNPJ_REPRESENTANTE', 'NOME_REPRESENTANTE', 
                'MARGEM', 'DESCONTO', 'FATURAMENTO', 'COMISSAO',
                'PRECO', 'FINANCEIRO', 'COMERCIAL'
            ],
            'BAIXO': [
                # Dados operacionais não sensíveis
                'CODIGO_REGIAO', 'DESCRICAO_REGIAO', 'NUMERO_PEDIDO',
                'CODIGO_PRODUTO', 'CODIGO_REGIONAL', 'EMPRESA',
                'CATEGORIA', 'TIPO', 'STATUS', 'DATA'
            ]
        }
        
        # Palavras-chave para identificação adicional no conteúdo
        self.keywords = {
            'ALTO': [
                'nome', 'cnpj', 'cpf', 'cliente', 'identificação',
                'razão social', 'documento', 'email', 'telefone'
            ],
            'MÉDIO': [
                'valor', 'preço', 'financeiro', 'real', 'dinheiro',
                'faturamento', 'receita', 'margem', 'lucro'
            ],
            'BAIXO': [
                'código', 'descrição', 'região', 'produto', 'operacional',
                'categoria', 'tipo', 'status'
            ]
        }
        
        # Padrões regex para identificação específica
        self.patterns = {
            'ALTO': [
                r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}',  # CNPJ
                r'\d{3}\.\d{3}\.\d{3}-\d{2}',        # CPF
                r'[a-zA-Z\s]+ LTDA',                 # Razão social
                r'[a-zA-Z\s]+ S\.A\.',               # Sociedade anônima
            ],
            'MÉDIO': [
                r'R\$\s*\d+[,.]?\d*',                # Valores monetários
                r'\d+[,.]\d+',                       # Números decimais (valores)
            ]
        }
        
        print("LGPDDataClassifier inicializado:")
        print(f"Nível ALTO: {len(self.sensitive_fields['ALTO'])} campos sensíveis")
        print(f"Nível MÉDIO: {len(self.sensitive_fields['MÉDIO'])} campos sensíveis") 
        print(f"Nível BAIXO: {len(self.sensitive_fields['BAIXO'])} campos operacionais")
    
    def classify_data(self, data: Dict[str, Any]) -> str:
        """
        Classifica o nível LGPD dos dados
        
        Args:
            data: Dicionário com os dados (ex: linha do CSV)
            
        Returns:
            String com o nível: "ALTO", "MÉDIO" ou "BAIXO"
        """
        if not data:
            return "BAIXO"
        
        # Análises diferentes
        field_analysis = self._analyze_fields(data)
        content_analysis = self._analyze_content(data)
        pattern_analysis = self._analyze_patterns(data)
        
        # Pontuação por nível
        scores = {
            'ALTO': field_analysis.get('ALTO', 0) + content_analysis.get('ALTO', 0) + pattern_analysis.get('ALTO', 0),
            'MÉDIO': field_analysis.get('MÉDIO', 0) + content_analysis.get('MÉDIO', 0) + pattern_analysis.get('MÉDIO', 0),
            'BAIXO': field_analysis.get('BAIXO', 0) + content_analysis.get('BAIXO', 0) + pattern_analysis.get('BAIXO', 0)
        }
        
        # Lógica de classificação: prioriza o nível mais alto com pontuação > 0
        if scores['ALTO'] > 0:
            return "ALTO"
        elif scores['MÉDIO'] > 0:
            return "MÉDIO"
        else:
            return "BAIXO"
    
    def _analyze_fields(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Analisa os nomes dos campos nos dados"""
        found = {'ALTO': 0, 'MÉDIO': 0, 'BAIXO': 0}
        
        for field_name in data.keys():
            field_upper = str(field_name).upper()
            
            # Verifica cada nível (prioriza ALTO > MÉDIO > BAIXO)
            classified = False
            for level in ['ALTO', 'MÉDIO', 'BAIXO']:
                if any(sensitive_field in field_upper for sensitive_field in self.sensitive_fields[level]):
                    found[level] += 1
                    classified = True
                    break  # Para no primeiro match para evitar dupla contagem
        
        return found
    
    def _analyze_content(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Analisa o conteúdo dos dados usando palavras-chave"""
        found = {'ALTO': 0, 'MÉDIO': 0, 'BAIXO': 0}
        
        # Converte todos os valores para string para análise
        content_str = ' '.join(str(value) for value in data.values() if value is not None).upper()
        
        for level, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword.upper() in content_str:
                    found[level] += 1
        
        return found
    
    def _analyze_patterns(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Analisa padrões específicos (regex) nos dados"""
        import re
        
        found = {'ALTO': 0, 'MÉDIO': 0, 'BAIXO': 0}
        
        # Converte dados para string
        data_str = str(data)
        
        for level, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, data_str)
                if matches:
                    found[level] += len(matches)
        
        return found
    
    def get_classification_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retorna detalhes completos da classificação para auditoria
        
        Args:
            data: Dados para classificar
            
        Returns:
            Dicionário com detalhes da classificação
        """
        classification = self.classify_data(data)
        
        field_analysis = self._analyze_fields(data)
        content_analysis = self._analyze_content(data)
        pattern_analysis = self._analyze_patterns(data)
        
        # Identifica campos específicos detectados
        detected_fields = []
        for field_name in data.keys():
            field_upper = str(field_name).upper()
            for level, fields in self.sensitive_fields.items():
                for sensitive_field in fields:
                    if sensitive_field in field_upper:
                        detected_fields.append({
                            'field': field_name,
                            'sensitive_pattern': sensitive_field,
                            'level': level,
                            'value': str(data[field_name])[:50] + "..." if len(str(data[field_name])) > 50 else str(data[field_name])
                        })
        
        return {
            'classification': classification,
            'confidence_score': self._calculate_confidence(field_analysis, content_analysis, pattern_analysis),
            'analysis': {
                'fields': field_analysis,
                'content': content_analysis,
                'patterns': pattern_analysis
            },
            'detected_fields': detected_fields,
            'total_fields': len(data),
            'requires_encryption': classification in ['ALTO', 'MÉDIO'],
            'retention_policy': self._get_retention_policy(classification),
            'access_restrictions': self._get_access_restrictions(classification)
        }
    
    def _calculate_confidence(self, field_analysis: Dict, content_analysis: Dict, pattern_analysis: Dict) -> float:
        """Calcula confiança da classificação"""
        total_indicators = sum(field_analysis.values()) + sum(content_analysis.values()) + sum(pattern_analysis.values())
        
        if total_indicators == 0:
            return 0.5  # Neutro quando não há indicadores
        elif total_indicators >= 5:
            return 0.95  # Alta confiança
        elif total_indicators >= 3:
            return 0.8   # Boa confiança
        else:
            return 0.6   # Confiança moderada
    
    def _get_retention_policy(self, classification: str) -> Dict[str, Any]:
        """Define política de retenção baseada na classificação"""
        policies = {
            'ALTO': {
                'retention_years': 5,
                'auto_delete': True,
                'audit_required': True,
                'backup_encrypted': True
            },
            'MÉDIO': {
                'retention_years': 7,
                'auto_delete': False,
                'audit_required': True,
                'backup_encrypted': True
            },
            'BAIXO': {
                'retention_years': 10,
                'auto_delete': False,
                'audit_required': False,
                'backup_encrypted': False
            }
        }
        return policies.get(classification, policies['BAIXO'])
    
    def _get_access_restrictions(self, classification: str) -> Dict[str, Any]:
        """Define restrições de acesso baseadas na classificação"""
        restrictions = {
            'ALTO': {
                'requires_authorization': True,
                'max_concurrent_users': 3,
                'audit_all_access': True,
                'anonymize_in_logs': True
            },
            'MÉDIO': {
                'requires_authorization': True,
                'max_concurrent_users': 10,
                'audit_all_access': True,
                'anonymize_in_logs': False
            },
            'BAIXO': {
                'requires_authorization': False,
                'max_concurrent_users': -1,  # Ilimitado
                'audit_all_access': False,
                'anonymize_in_logs': False
            }
        }
        return restrictions.get(classification, restrictions['BAIXO'])
    
    def classify_batch(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classifica uma lista de dados em lote"""
        results = []
        
        print(f"Classificando {len(data_list)} registros...")
        
        for i, data in enumerate(data_list):
            if i % 1000 == 0 and i > 0:
                print(f"   Processados: {i}/{len(data_list)}")
            
            classification = self.classify_data(data)
            results.append({
                'index': i,
                'classification': classification,
                'data': data
            })
        
        print(f"Classificação concluída!")
        return results
    
    def get_statistics(self, classifications: List[str]) -> Dict[str, Any]:
        """Calcula estatísticas das classificações"""
        from collections import Counter
        
        counter = Counter(classifications)
        total = len(classifications)
        
        return {
            'total_records': total,
            'distribution': dict(counter),
            'percentages': {level: (count/total)*100 for level, count in counter.items()},
            'requires_encryption': counter.get('ALTO', 0) + counter.get('MÉDIO', 0),
            'encryption_percentage': ((counter.get('ALTO', 0) + counter.get('MÉDIO', 0))/total)*100 if total > 0 else 0
        }

def test_lgpd_data_classifier():
    """Testa o classificador LGPD de dados com dados similares ao CSV"""
    
    print("TESTANDO CLASSIFICADOR LGPD DE DADOS")
    print("=" * 50)
    
    classifier = LGPDDataClassifier()
    
    # Casos de teste baseados nos dados reais do CSV
    test_cases = [
        {
            'name': 'Dados completos do cliente (ALTO)',
            'data': {
                'NUMERO_PEDIDO': 843562,
                'CNPJ_CLIENTE': '03.221.721/0001-10',
                'NOME_CLIENTE': 'CONFECCOES EDINELI LTDA',
                'VALOR_ITEM_LIQUIDO': 2842.50,
                'CODIGO_REGIAO': 351
            }
        },
        {
            'name': 'Apenas dados financeiros (MÉDIO)', 
            'data': {
                'NUMERO_PEDIDO': 843562,
                'VALOR_ITEM_LIQUIDO': 2842.50,
                'VALOR_ITEM_BRUTO': 3158.50,
                'CODIGO_REGIAO': 351,
                'DESCRICAO_REGIAO': 'SP - PIRACICABA'
            }
        },
        {
            'name': 'Apenas códigos operacionais (BAIXO)',
            'data': {
                'NUMERO_PEDIDO': 843562,
                'CODIGO_REGIAO': 351,
                'DESCRICAO_REGIAO': 'SP - PIRACICABA',
                'EMPRESA': 'Cativa Pomerode',
                'CODIGO_REGIONAL': 12
            }
        },
        {
            'name': 'Dados do representante (MÉDIO)',
            'data': {
                'CNPJ_REPRESENTANTE': '36.431.259/0001-34',
                'NOME_REPRESENTANTE': 'MATO GROSSO COMERCIO LTDA',
                'CODIGO_REGIONAL': 12,
                'DESCRICAO_REGIONAL': 'SP INTERIOR'
            }
        },
        {
            'name': 'Dados mistos com alta sensibilidade (ALTO)',
            'data': {
                'NOME_CLIENTE': 'EMPRESA TESTE S.A.',
                'EMAIL': 'contato@empresa.com.br',
                'TELEFONE': '(47) 99999-9999',
                'VALOR_ITEM_LIQUIDO': 5000.00
            }
        }
    ]
    
    print(f"\nTestando {len(test_cases)} casos:")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"{i}. {test_case['name']}:")
        
        # Classificação detalhada
        details = classifier.get_classification_details(test_case['data'])
        
        print(f"Classificação: {details['classification']}")
        print(f"Confiança: {details['confidence_score']:.1%}")
        print(f"Requer criptografia: {details['requires_encryption']}")
        
        # Mostra análises
        print(f"Análises:")
        for analysis_type, scores in details['analysis'].items():
            if sum(scores.values()) > 0:
                print(f"      {analysis_type.title()}: {scores}")
        
        # Mostra campos detectados
        if details['detected_fields']:
            print(f"Campos sensíveis detectados:")
            for field_info in details['detected_fields'][:3]:  # Primeiros 3
                print(f"- {field_info['field']} ({field_info['level']}): {field_info['value']}")
        
        # Mostra políticas
        retention = details['retention_policy']
        print(f"Retenção: {retention['retention_years']} anos")
        
        access = details['access_restrictions']
        print(f"Acesso: {'Restrito' if access['requires_authorization'] else 'Livre'}")

def test_batch_classification():
    """Testa classificação em lote"""
    
    print(f"\nTESTE DE CLASSIFICAÇÃO EM LOTE")
    print("=" * 40)
    
    # Simula dados do CSV
    sample_data = []
    for i in range(100):
        if i % 3 == 0:  # 1/3 dos dados são ALTO
            sample_data.append({
                'NUMERO_PEDIDO': 843562 + i,
                'CNPJ_CLIENTE': f'12.345.678/0001-{i:02d}',
                'NOME_CLIENTE': f'CLIENTE {i} LTDA',
                'VALOR_ITEM_LIQUIDO': 2000 + i * 10
            })
        elif i % 3 == 1:  # 1/3 são MÉDIO
            sample_data.append({
                'NUMERO_PEDIDO': 843562 + i,
                'VALOR_ITEM_LIQUIDO': 2000 + i * 10,
                'CNPJ_REPRESENTANTE': f'98.765.432/0001-{i:02d}',
                'CODIGO_REGIAO': 300 + i
            })
        else:  # 1/3 são BAIXO
            sample_data.append({
                'NUMERO_PEDIDO': 843562 + i,
                'CODIGO_REGIAO': 300 + i,
                'DESCRICAO_REGIAO': f'REGIAO {i}',
                'EMPRESA': 'Cativa Pomerode'
            })
    
    classifier = LGPDDataClassifier()
    
    # Classifica em lote
    classifications = [classifier.classify_data(data) for data in sample_data]
    
    # Estatísticas
    stats = classifier.get_statistics(classifications)
    
    print(f"ESTATÍSTICAS:")
    print(f"Total de registros: {stats['total_records']}")
    print(f"Distribuição:")
    for level, count in stats['distribution'].items():
        percentage = stats['percentages'][level]
        print(f"      {level}: {count} registros ({percentage:.1f}%)")
    
    print(f"Registros que requerem criptografia: {stats['requires_encryption']} ({stats['encryption_percentage']:.1f}%)")

if __name__ == "__main__":
    test_lgpd_data_classifier()
    test_batch_classification()
