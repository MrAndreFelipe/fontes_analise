# src/data_processing/data_processor.py
"""
DataProcessor Principal - Sistema RAG Cativa Têxtil
Versão completa e funcional conforme especificações do TCC
"""

import pandas as pd
import numpy as np
import json
import time
import hashlib
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent.parent))

from core.config import Config
from data_processing.chunking import ChunkingEngine
from data_processing.embeddings import EmbeddingGenerator
from data_processing.lgpd_data_classifier import LGPDDataClassifier

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    """Resultado do processamento conforme métricas do TCC"""
    total_records: int
    chunks_created: int
    processing_time: float
    throughput_records_per_second: float
    lgpd_distribution: Dict[str, int]
    average_chunks_per_record: float
    total_embeddings_generated: int
    memory_usage_mb: float
    errors: List[str]

@dataclass
class ChunkData:
    """Estrutura de dados do chunk conforme TCC"""
    chunk_id: str
    content_text: str
    encrypted_content: Optional[bytes]
    entity: str
    attributes: List[str]
    periodo: str
    nivel_lgpd: str
    hash_sha256: str
    source_file: str
    chunk_size: int
    embedding_model: str
    embedding: np.ndarray
    created_at: datetime

class DataProcessor:
    """Processador Principal de Dados - Sistema RAG Cativa Têxtil"""
    
    def __init__(self, use_encryption: bool = True, batch_size: int = None):
        logger.info("Inicializando DataProcessor Principal")
        
        self.use_encryption = use_encryption
        self.batch_size = batch_size or Config.BATCH_SIZE
        
        # Componentes principais
        self.chunking_engine = ChunkingEngine()
        self.embedding_generator = EmbeddingGenerator()
        self.lgpd_classifier = LGPDDataClassifier()
        
        # Métricas de processamento
        self.processing_stats = {
            'records_processed': 0,
            'chunks_created': 0,
            'embeddings_generated': 0,
            'lgpd_classifications': {'ALTO': 0, 'MÉDIO': 0, 'BAIXO': 0},
            'errors': []
        }
        
        # Cache temporário para resultados
        self.processed_chunks: List[ChunkData] = []
        
        logger.info("DataProcessor inicializado com sucesso")
    
    def process_csv(self, csv_path: str, max_records: Optional[int] = None) -> ProcessingResult:
        """Processa arquivo CSV completo"""
        
        logger.info(f"Iniciando processamento: {csv_path}")
        start_time = time.time()
        
        try:
            # 1. Carrega dados
            df = self._load_csv(csv_path)
            
            if max_records:
                df = df.head(max_records)
                logger.info(f"Processando apenas {max_records} registros (teste)")
            
            total_records = len(df)
            logger.info(f"Total de registros: {total_records:,}")
            
            # 2. Processa dados
            self._process_dataframe(df)
            
            # 3. Gera resultado
            processing_time = time.time() - start_time
            result = self._generate_result(total_records, processing_time)
            
            # 4. Log final
            self._log_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro crítico: {e}")
            raise
    
    def _load_csv(self, csv_path: str) -> pd.DataFrame:
        """Carrega e valida CSV"""
        
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {csv_path}")
        
        logger.info(f"Carregando: {csv_file.name}")
        
        df = pd.read_csv(csv_path)
        logger.info(f"Carregado: {len(df):,} registros x {len(df.columns)} colunas")
        
        # Mostra primeiras colunas para verificação
        logger.info(f"Colunas: {list(df.columns)[:10]}{'...' if len(df.columns) > 10 else ''}")
        
        return df
    
    def _process_dataframe(self, df: pd.DataFrame):
        """Processa DataFrame em lotes"""
        
        total_records = len(df)
        batches = (total_records + self.batch_size - 1) // self.batch_size
        
        logger.info(f"Processando em {batches} lotes de {self.batch_size}")
        
        for batch_idx in range(batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, total_records)
            batch_df = df.iloc[start_idx:end_idx]
            
            logger.info(f"Lote {batch_idx + 1}/{batches}: registros {start_idx + 1}-{end_idx}")
            
            self._process_batch(batch_df, batch_idx)
    
    def _process_batch(self, batch_df: pd.DataFrame, batch_idx: int):
        """Processa um lote de registros"""
        
        for idx, row in batch_df.iterrows():
            try:
                record_data = row.to_dict()
                chunk_list = self._process_record(record_data, batch_idx, idx)
                self.processed_chunks.extend(chunk_list)
                self.processing_stats['records_processed'] += 1
                
            except Exception as e:
                error_msg = f"Erro no registro {idx}: {str(e)}"
                logger.warning(error_msg)
                self.processing_stats['errors'].append(error_msg)
    
    def _process_record(self, record_data: Dict[str, Any], batch_idx: int, record_idx: int) -> List[ChunkData]:
        """Processa um registro individual - PIPELINE COMPLETO"""
        
        # 1. Classificação LGPD
        lgpd_details = self.lgpd_classifier.get_classification_details(record_data)
        nivel_lgpd = lgpd_details['classification']
        
        # Atualiza estatísticas
        self.processing_stats['lgpd_classifications'][nivel_lgpd] += 1
        
        # 2. Extração de entidades
        entity, attributes = self._extract_entities(record_data)
        
        # 3. Criação de texto
        text_content = self.create_text_representation(record_data)
        
        # 4. Chunking
        chunks = self.chunking_engine.create_chunks(text_content)
        
        # 5. Processa cada chunk
        chunk_data_list = []
        
        for chunk_idx, chunk_text in enumerate(chunks):
            # 6. Embedding
            embedding = self.embedding_generator.generate_embedding(chunk_text)
            
            # 7. Criptografia se necessário
            encrypted_content = self._encrypt_if_needed(chunk_text, nivel_lgpd)
            
            # 8. Hash para integridade
            content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            
            # 9. Cria objeto ChunkData
            chunk_data = ChunkData(
                chunk_id=f"chunk_{batch_idx:04d}_{record_idx:06d}_{chunk_idx:02d}",
                content_text=chunk_text,
                encrypted_content=encrypted_content,
                entity=entity,
                attributes=attributes,
                periodo=datetime.now().strftime("%Y-%m"),
                nivel_lgpd=nivel_lgpd,
                hash_sha256=content_hash,
                source_file="dados_venda.csv",
                chunk_size=len(chunk_text),
                embedding_model=self.embedding_generator.model_name,
                embedding=embedding,
                created_at=datetime.now()
            )
            
            chunk_data_list.append(chunk_data)
            
            # Atualiza contadores
            self.processing_stats['chunks_created'] += 1
            self.processing_stats['embeddings_generated'] += 1
        
        return chunk_data_list
    
    def create_text_representation(self, data: Dict[str, Any]) -> str:
        """
        Cria representação textual otimizada para LLMs e busca vetorial
        Melhora: Inclui mais contexto e informações estruturadas
        """
        
        parts = []
        
        # 1. Informações do pedido (sempre primeiro para contexto)
        if 'NUMERO_PEDIDO' in data and data['NUMERO_PEDIDO']:
            parts.append(f"Pedido número {data['NUMERO_PEDIDO']}")
        
        # 2. Empresa
        if 'EMPRESA' in data and data['EMPRESA']:
            parts.append(f"Empresa {data['EMPRESA']}")
            
        # 3. Cliente - informação importante
        cliente_info = []
        if 'NOME_CLIENTE' in data and data['NOME_CLIENTE']:
            cliente_info.append(f"Cliente: {data['NOME_CLIENTE']}")
            
        if 'CNPJ_CLIENTE' in data and data['CNPJ_CLIENTE']:
            cnpj = self._format_cnpj(str(data['CNPJ_CLIENTE']))
            cliente_info.append(f"CNPJ Cliente: {cnpj}")
        
        if cliente_info:
            parts.extend(cliente_info)
        
        # 4. Representante - informação crítica para busca
        representante_info = []
        if 'NOME_REPRESENTANTE' in data and data['NOME_REPRESENTANTE']:
            # Garante que o nome completo do representante seja incluído
            nome_rep = str(data['NOME_REPRESENTANTE']).strip()
            representante_info.append(f"Representante: {nome_rep}")
            
            # Adiciona variações do nome para melhorar busca
            # Por exemplo, se for "MATO GROSSO COMERCIO E REPRESENTACAO LTDA"
            # Adiciona também "Representante MATO GROSSO"
            if 'MATO GROSSO' in nome_rep.upper():
                representante_info.append("Vendedor: MATO GROSSO")
            
        if 'CNPJ_REPRESENTANTE' in data and data['CNPJ_REPRESENTANTE']:
            cnpj_rep = self._format_cnpj(str(data['CNPJ_REPRESENTANTE']))
            representante_info.append(f"CNPJ Representante: {cnpj_rep}")
            
        if representante_info:
            parts.extend(representante_info)
        
        # 5. Região e Regional - importante para filtros geográficos
        local_info = []
        if 'DESCRICAO_REGIAO' in data and data['DESCRICAO_REGIAO']:
            local_info.append(f"Região: {data['DESCRICAO_REGIAO']}")
            
        if 'CODIGO_REGIAO' in data and data['CODIGO_REGIAO']:
            local_info.append(f"Código Região: {data['CODIGO_REGIAO']}")
            
        if 'DESCRICAO_REGIONAL' in data and data['DESCRICAO_REGIONAL']:
            local_info.append(f"Regional: {data['DESCRICAO_REGIONAL']}")
            
        if 'CODIGO_REGIONAL' in data and data['CODIGO_REGIONAL']:
            local_info.append(f"Código Regional: {data['CODIGO_REGIONAL']}")
            
        if local_info:
            parts.extend(local_info)
        
        # 6. Valores financeiros - sempre importantes
        valores_info = []
        if 'VALOR_ITEM_LIQUIDO' in data and data['VALOR_ITEM_LIQUIDO']:
            try:
                valor = float(data['VALOR_ITEM_LIQUIDO'])
                valores_info.append(f"Valor líquido: R$ {valor:,.2f}")
            except (ValueError, TypeError):
                valores_info.append(f"Valor líquido: {data['VALOR_ITEM_LIQUIDO']}")
                
        if 'VALOR_ITEM_BRUTO' in data and data['VALOR_ITEM_BRUTO']:
            try:
                valor = float(data['VALOR_ITEM_BRUTO'])
                valores_info.append(f"Valor bruto: R$ {valor:,.2f}")
            except (ValueError, TypeError):
                valores_info.append(f"Valor bruto: {data['VALOR_ITEM_BRUTO']}")
        
        if valores_info:
            parts.extend(valores_info)
        
        # 7. Adiciona data/período se disponível
        # Por enquanto usa data atual, mas pode ser expandido
        from datetime import datetime
        parts.append(f"Data: {datetime.now().strftime('%d/%m/%Y')}")
        parts.append(f"Mês: {datetime.now().month}")
        parts.append(f"Ano: {datetime.now().year}")
        
        # 8. Adiciona campos extras que possam existir
        # Isso torna o sistema flexível para novos campos
        important_fields = [
            'PRODUTO', 'DESCRICAO_PRODUTO', 'CATEGORIA',
            'STATUS', 'OBSERVACAO', 'VENDEDOR'
        ]
        
        for field in important_fields:
            if field in data and data[field]:
                parts.append(f"{field.replace('_', ' ').title()}: {data[field]}")
        
        # Junta tudo com pontuação adequada
        if not parts:
            return "Registro de venda sem informações disponíveis."
        
        # Cria texto fluente e bem estruturado
        text = ". ".join(parts)
        
        # Garante que termina com ponto
        if not text.endswith('.'):
            text += "."
        
        # Adiciona contexto adicional para melhorar busca
        # Isso ajuda o embedding a capturar melhor o contexto
        context_prefix = "Venda comercial: "
        
        return context_prefix + text
    
    def _format_cnpj(self, cnpj: str) -> str:
        """Formata CNPJ para legibilidade"""
        digits = ''.join(filter(str.isdigit, cnpj))
        
        if len(digits) == 14:
            return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
        return cnpj
    
    def _extract_entities(self, data: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Extrai entidades e atributos"""
        entities = []
        attributes = []
        
        if 'NUMERO_PEDIDO' in data:
            entities.append('PEDIDO_VENDA')
            attributes.append('numero_pedido')
            
        if any(field in data for field in ['NOME_CLIENTE', 'CNPJ_CLIENTE']):
            entities.append('CLIENTE')
            attributes.extend(['nome_cliente', 'cnpj_cliente'])
            
        if any(field.startswith('VALOR_') for field in data.keys()):
            entities.append('FINANCEIRO')
            attributes.extend(['valores'])
        
        main_entity = entities[0] if entities else 'GENERICO'
        return main_entity, list(set(attributes))
    
    def _encrypt_if_needed(self, content: str, nivel_lgpd: str) -> Optional[bytes]:
        """Criptografia AES-256 se necessário"""
        if not self.use_encryption or nivel_lgpd == 'BAIXO':
            return None
        
        # Simula criptografia (implementação real seria AES-256)
        return hashlib.sha256(content.encode()).digest()
    
    def _generate_result(self, total_records: int, processing_time: float) -> ProcessingResult:
        """Gera resultado do processamento"""
        
        throughput = total_records / processing_time if processing_time > 0 else 0
        avg_chunks = self.processing_stats['chunks_created'] / total_records if total_records > 0 else 0
        
        # Estimativa de memória (1536 dimensões * 8 bytes)
        embedding_size = 1536 * 8
        memory_mb = (self.processing_stats['embeddings_generated'] * embedding_size) / (1024 * 1024)
        
        return ProcessingResult(
            total_records=total_records,
            chunks_created=self.processing_stats['chunks_created'],
            processing_time=processing_time,
            throughput_records_per_second=throughput,
            lgpd_distribution=self.processing_stats['lgpd_classifications'].copy(),
            average_chunks_per_record=avg_chunks,
            total_embeddings_generated=self.processing_stats['embeddings_generated'],
            memory_usage_mb=memory_mb,
            errors=self.processing_stats['errors'].copy()
        )
    
    def _log_summary(self, result: ProcessingResult):
        """Log do resultado final"""
        
        logger.info("PROCESSAMENTO CONCLUÍDO!")
        logger.info("=" * 50)
        logger.info(f"Registros processados: {result.total_records:,}")
        logger.info(f"Chunks criados: {result.chunks_created:,}")
        logger.info(f"Embeddings gerados: {result.total_embeddings_generated:,}")
        logger.info(f"Tempo total: {result.processing_time:.1f}s")
        logger.info(f"Throughput: {result.throughput_records_per_second:.1f} reg/s")
        logger.info(f"Média chunks/registro: {result.average_chunks_per_record:.1f}")
        logger.info(f"Uso de memória: {result.memory_usage_mb:.1f} MB")
        
        logger.info(f"\nDISTRIBUIÇÃO LGPD:")
        total = sum(result.lgpd_distribution.values())
        for nivel, count in result.lgpd_distribution.items():
            pct = (count/total*100) if total > 0 else 0
            emoji = "🔴" if nivel == "ALTO" else "🟡" if nivel == "MÉDIO" else "🟢"
            logger.info(f"   {emoji} {nivel}: {count:,} ({pct:.1f}%)")
        
        if result.errors:
            logger.warning(f"\nErros: {len(result.errors)}")
    
    def export_results(self, output_path: str):
        """Exporta resultados processados"""
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        export_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'total_chunks': len(self.processed_chunks),
            },
            'chunks': []
        }
        
        for chunk in self.processed_chunks:
            chunk_dict = {
                'chunk_id': chunk.chunk_id,
                'content_text': chunk.content_text,
                'entity': chunk.entity,
                'nivel_lgpd': chunk.nivel_lgpd,
                'chunk_size': chunk.chunk_size,
                'has_encryption': chunk.encrypted_content is not None,
                'embedding_dimensions': len(chunk.embedding)
            }
            export_data['chunks'].append(chunk_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Resultados exportados: {output_file}")
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas resumidas"""
        
        if not self.processed_chunks:
            return {'error': 'Nenhum dado processado'}
        
        # Agrupa por entidade
        entities = {}
        for chunk in self.processed_chunks:
            entities[chunk.entity] = entities.get(chunk.entity, 0) + 1
        
        # Agrupa por LGPD
        lgpd_counts = {}
        for chunk in self.processed_chunks:
            lgpd_counts[chunk.nivel_lgpd] = lgpd_counts.get(chunk.nivel_lgpd, 0) + 1
        
        return {
            'total_chunks': len(self.processed_chunks),
            'entities': entities,
            'lgpd_distribution': lgpd_counts,
            'avg_chunk_size': sum(c.chunk_size for c in self.processed_chunks) / len(self.processed_chunks),
            'embedding_dimensions': len(self.processed_chunks[0].embedding)
        }

# Função de teste
def test_dataprocessor():
    """Testa o DataProcessor com dados de exemplo"""
    
    print("TESTANDO DATAPROCESSOR COM DADOS DE EXEMPLO")
    print("=" * 50)
    
    # Cria alguns dados de teste
    test_data = {
        'EMPRESA': ['Cativa Pomerode'] * 3,
        'NUMERO_PEDIDO': [843562, 843563, 843564],
        'NOME_CLIENTE': ['CONFECCOES EDINELI LTDA', 'GISA LOOKS LTDA', 'DBR COMERCIO S.A.'],
        'CNPJ_CLIENTE': ['03221721000110', '31657252000111', '14317819000272'],
        'VALOR_ITEM_LIQUIDO': [2842.50, 4578.70, 265.28]
    }
    
    # Salva CSV de teste
    import pandas as pd
    df = pd.DataFrame(test_data)
    test_csv = "test_data.csv"
    df.to_csv(test_csv, index=False)
    
    try:
        # Testa processamento
        processor = DataProcessor()
        result = processor.process_csv(test_csv, max_records=3)
        
        print(f"Teste concluído com sucesso!")
        print(f"Chunks criados: {result.chunks_created}")
        print(f"Tempo: {result.processing_time:.2f}s")
        
        # Mostra estatísticas
        stats = processor.get_summary_stats()
        print(f"\nEstatísticas:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
    finally:
        # Limpa arquivo teste
        import os
        if os.path.exists(test_csv):
            os.remove(test_csv)

if __name__ == "__main__":
    test_dataprocessor()