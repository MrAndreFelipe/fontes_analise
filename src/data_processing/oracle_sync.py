# src/data_processing/oracle_sync.py
"""
Oracle Data Synchronizer - Sistema RAG Cativa Têxtil
Sincroniza dados Oracle com PostgreSQL para estratégia híbrida
"""

import sys
from pathlib import Path
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import time

# Adiciona src ao path se necessário
sys.path.append(str(Path(__file__).parent.parent))

from core.database_adapter import DatabaseConfig, DatabaseAdapterFactory
from data_processing.embeddings import EmbeddingGenerator
from security.encryption import AES256Encryptor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OracleToPostgreSQLSync:
    """Sincronizador híbrido Oracle -> PostgreSQL"""
    
    def __init__(self, oracle_config: DatabaseConfig, postgres_config: Dict[str, Any]):
        """
        Inicializa sincronizador
        
        Args:
            oracle_config: Configuração do Oracle
            postgres_config: Configuração do PostgreSQL
        """
        self.oracle_config = oracle_config
        self.postgres_config = postgres_config
        
        # Adapters
        self.oracle_adapter = None
        self.postgres_adapter = None
        
        # Componentes de processamento
        self.embedding_generator = EmbeddingGenerator()
        
        # Encryptor AES-256-GCM para chunks sensíveis
        try:
            self.encryptor = AES256Encryptor()
            logger.info("Criptografia AES-256-GCM habilitada para sincronização")
        except ValueError as e:
            logger.warning(f"Criptografia desabilitada: {e}")
            self.encryptor = None
        
        # Estatísticas
        self.sync_stats = {
            'started_at': None,
            'completed_at': None,
            'records_processed': 0,
            'embeddings_generated': 0,
            'errors': []
        }
        
        logger.info("OracleToPostgreSQLSync inicializado")
    
    def connect_databases(self) -> bool:
        """Conecta aos bancos Oracle e PostgreSQL"""
        try:
            # Conecta Oracle
            logger.info("Conectando ao Oracle...")
            self.oracle_adapter = DatabaseAdapterFactory.create_adapter(self.oracle_config)
            if not self.oracle_adapter.connect():
                logger.error("Falha ao conectar ao Oracle")
                return False
            
            # Conecta PostgreSQL
            logger.info("Conectando ao PostgreSQL...")
            postgres_config = DatabaseConfig(
                host=self.postgres_config['host'],
                port=self.postgres_config['port'],
                database=self.postgres_config['database'],
                user=self.postgres_config['user'],
                password=self.postgres_config['password'],
                db_type='postgresql'
            )
            
            self.postgres_adapter = DatabaseAdapterFactory.create_adapter(postgres_config)
            if not self.postgres_adapter.connect():
                logger.error("Falha ao conectar ao PostgreSQL")
                return False
            
            logger.info("Conexões estabelecidas com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar aos bancos: {e}")
            return False
    
    def sync_textual_data_for_embeddings(self, days_back: int = 30, max_records: int = 1000) -> bool:
        """
        Sincroniza dados textuais do Oracle para PostgreSQL com embeddings
        
        Args:
            days_back: Quantos dias atrás buscar dados
            max_records: Máximo de registros por execução
        """
        logger.info(f"Iniciando sincronização de dados textuais ({days_back} dias, máx {max_records} registros)")
        
        try:
            self.sync_stats['started_at'] = datetime.now()
            
            # Busca dados textuais no Oracle
            data_inicio = datetime.now() - timedelta(days=days_back)
            
            textual_data = self.oracle_adapter.execute_query(
                self.oracle_adapter.queries['textual_data'],
                {
                    'data_inicio': data_inicio,
                    'max_rows': max_records
                }
            )
            
            logger.info(f"Encontrados {len(textual_data)} registros textuais no Oracle")
            
            if not textual_data:
                logger.warning("Nenhum dado textual encontrado no Oracle")
                return True
            
            # Processa cada registro
            chunks_created = []
            
            for i, row in enumerate(textual_data):
                try:
                    # Verifica se já existe no PostgreSQL
                    chunk_id = f"oracle_sync_{row['registro_id']}"
                    existing = self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE chunk_id = %s",
                        (chunk_id,)
                    )
                    
                    if existing:
                        logger.debug(f"Registro {chunk_id} já existe, pulando...")
                        continue
                    
                    # Cria chunk para processamento
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content_text': row['texto_completo'],
                        'entity': 'ORACLE_TEXTUAL',
                        'nivel_lgpd': row['nivel_lgpd'],
                        'source_file': 'oracle_sync',
                        'attributes': {
                            'valor_liquido': float(row.get('valor_item_liquido', 0)),
                            'nome_cliente': row.get('nome_cliente'),
                            'data_venda': str(row.get('data_venda')),
                            'sync_timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    # Gera embedding
                    if self.embedding_generator:
                        logger.debug(f"Gerando embedding para registro {i+1}/{len(textual_data)}")
                        embedding = self.embedding_generator.generate_embedding(row['texto_completo'])
                        chunk_data['embedding'] = embedding
                        chunk_data['embedding_model'] = self.embedding_generator.model_name
                        self.sync_stats['embeddings_generated'] += 1
                    
                    # Criptografia para dados sensíveis (LGPD ALTO/MEDIO)
                    encrypted_content = self._encrypt_if_needed(row['texto_completo'], row['nivel_lgpd'])
                    if encrypted_content:
                        chunk_data['encrypted_content'] = encrypted_content
                    
                    # Calcula hash
                    import hashlib
                    content_hash = hashlib.sha256(row['texto_completo'].encode()).hexdigest()
                    chunk_data['hash_sha256'] = content_hash
                    chunk_data['chunk_size'] = len(row['texto_completo'])
                    
                    # Adiciona à lista para inserção
                    chunks_created.append(chunk_data)
                    self.sync_stats['records_processed'] += 1
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"Processados {i+1}/{len(textual_data)} registros")
                
                except Exception as e:
                    error_msg = f"Erro ao processar registro {i}: {e}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            # Insere chunks no PostgreSQL
            if chunks_created:
                logger.info(f"Inserindo {len(chunks_created)} chunks no PostgreSQL...")
                
                inserted_count = 0
                for chunk_data in chunks_created:
                    if self.postgres_adapter.insert_chunk(chunk_data):
                        inserted_count += 1
                    else:
                        error_msg = f"Erro ao inserir chunk {chunk_data['chunk_id']}"
                        logger.error(error_msg)
                        self.sync_stats['errors'].append(error_msg)
                
                logger.info(f"Inseridos {inserted_count}/{len(chunks_created)} chunks com sucesso")
            
            self.sync_stats['completed_at'] = datetime.now()
            self._log_sync_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na sincronização: {e}")
            self.sync_stats['errors'].append(str(e))
            return False
    
    def sync_aggregated_summaries(self, period_months: int = 12) -> bool:
        """Sincroniza resumos agregados do Oracle"""
        logger.info(f"Sincronizando resumos agregados ({period_months} meses)")
        
        try:
            # Busca resumos agregados no Oracle
            periodo_inicio = (datetime.now() - timedelta(days=period_months*30)).strftime('%Y-%m')
            
            agregados_data = self.oracle_adapter.execute_query(
                self.oracle_adapter.queries['resumos_periodo'],
                {'periodo_inicio': periodo_inicio}
            )
            
            logger.info(f"Encontrados {len(agregados_data)} resumos agregados")
            
            # Processa cada resumo
            for row in agregados_data:
                try:
                    chunk_id = f"oracle_agregado_{row['registro_id']}"
                    
                    # Verifica se já existe
                    existing = self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE chunk_id = %s",
                        (chunk_id,)
                    )
                    
                    if existing:
                        continue
                    
                    # Cria chunk agregado
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content_text': row['texto_resumo'],
                        'entity': 'ORACLE_AGREGADO',
                        'nivel_lgpd': 'BAIXO',  # Dados agregados são menos sensíveis
                        'source_file': 'oracle_aggregated',
                        'attributes': {
                            'periodo': row['periodo'],
                            'faturamento_liquido': float(row.get('faturamento_liquido', 0)),
                            'total_pedidos': int(row.get('total_pedidos', 0)),
                            'sync_timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    # Gera embedding para resumo
                    if self.embedding_generator:
                        embedding = self.embedding_generator.generate_embedding(row['texto_resumo'])
                        chunk_data['embedding'] = embedding
                        chunk_data['embedding_model'] = self.embedding_generator.model_name
                    
                    # Criptografia (dados agregados geralmente são BAIXO, mas verifica)
                    encrypted_content = self._encrypt_if_needed(row['texto_resumo'], 'BAIXO')
                    if encrypted_content:
                        chunk_data['encrypted_content'] = encrypted_content
                    
                    # Calcula hash
                    import hashlib
                    content_hash = hashlib.sha256(row['texto_resumo'].encode()).hexdigest()
                    chunk_data['hash_sha256'] = content_hash
                    chunk_data['chunk_size'] = len(row['texto_resumo'])
                    
                    # Insere no PostgreSQL
                    if self.postgres_adapter.insert_chunk(chunk_data):
                        self.sync_stats['records_processed'] += 1
                        self.sync_stats['embeddings_generated'] += 1
                
                except Exception as e:
                    error_msg = f"Erro ao processar agregado {row.get('registro_id')}: {e}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            logger.info("Sincronização de agregados concluída")
            return True
            
        except Exception as e:
            logger.error(f"Erro na sincronização de agregados: {e}")
            return False
    
    def sync_contas_pagar(self, days_back: int = 30, max_records: int = 1000) -> bool:
        """
        Sincroniza dados de Contas a Pagar do Oracle para PostgreSQL com embeddings
        
        Args:
            days_back: Quantos dias atrás buscar dados
            max_records: Máximo de registros por execução
        """
        logger.info(f"Sincronizando Contas a Pagar ({days_back} dias, máx {max_records} registros)")
        
        try:
            data_inicio = datetime.now() - timedelta(days=days_back)
            
            # Busca dados de contas a pagar no Oracle
            cp_data = self.oracle_adapter.execute_query(
                self.oracle_adapter.queries['cp_textual_data'],
                {'data_inicio': data_inicio, 'max_rows': max_records}
            )
            
            logger.info(f"Encontrados {len(cp_data)} títulos de contas a pagar")
            
            if not cp_data:
                logger.warning("Nenhum título de contas a pagar encontrado")
                return True
            
            # Processa cada título
            chunks_created = []
            
            for i, row in enumerate(cp_data):
                try:
                    # Verifica se já existe no PostgreSQL
                    chunk_id = f"cp_{row['registro_id']}"
                    existing = self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE chunk_id = %s",
                        (chunk_id,)
                    )
                    
                    if existing:
                        logger.debug(f"Título {chunk_id} já existe, pulando...")
                        continue
                    
                    # Cria chunk
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content_text': row['texto_completo'],
                        'entity': 'CONTAS_PAGAR',
                        'nivel_lgpd': row['nivel_lgpd'],
                        'source_file': 'oracle_cp',
                        'attributes': {
                            'valor_titulo': float(row.get('valor_titulo', 0)),
                            'valor_saldo': float(row.get('valor_saldo', 0)),
                            'nome_fornecedor': row.get('nome_fornecedor'),
                            'cnpj_fornecedor': row.get('cnpj_fornecedor'),
                            'titulo': row.get('titulo'),
                            'data_vencimento': str(row.get('data_vencimento')),
                            'data_emissao': str(row.get('data_emissao')),
                            'grupo': row.get('descricao_grupo'),
                            'subgrupo': row.get('descricao_subgrupo'),
                            'banco': row.get('descricao_banco'),
                            'sync_timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    # Gera embedding
                    if self.embedding_generator:
                        logger.debug(f"Gerando embedding para título {i+1}/{len(cp_data)}")
                        embedding = self.embedding_generator.generate_embedding(row['texto_completo'])
                        chunk_data['embedding'] = embedding
                        chunk_data['embedding_model'] = self.embedding_generator.model_name
                        self.sync_stats['embeddings_generated'] += 1
                    
                    # Criptografia para dados sensíveis (LGPD ALTO/MEDIO)
                    encrypted_content = self._encrypt_if_needed(row['texto_completo'], row['nivel_lgpd'])
                    if encrypted_content:
                        chunk_data['encrypted_content'] = encrypted_content
                    
                    # Calcula hash
                    import hashlib
                    content_hash = hashlib.sha256(row['texto_completo'].encode()).hexdigest()
                    chunk_data['hash_sha256'] = content_hash
                    chunk_data['chunk_size'] = len(row['texto_completo'])
                    
                    chunks_created.append(chunk_data)
                    self.sync_stats['records_processed'] += 1
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"Processados {i+1}/{len(cp_data)} títulos")
                
                except Exception as e:
                    error_msg = f"Erro ao processar título CP {i}: {e}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            # Insere chunks no PostgreSQL
            if chunks_created:
                logger.info(f"Inserindo {len(chunks_created)} chunks CP no PostgreSQL...")
                
                inserted_count = 0
                for chunk_data in chunks_created:
                    if self.postgres_adapter.insert_chunk(chunk_data):
                        inserted_count += 1
                    else:
                        error_msg = f"Erro ao inserir chunk {chunk_data['chunk_id']}"
                        logger.error(error_msg)
                        self.sync_stats['errors'].append(error_msg)
                
                logger.info(f"Inseridos {inserted_count}/{len(chunks_created)} chunks CP com sucesso")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na sincronização de contas a pagar: {e}")
            self.sync_stats['errors'].append(str(e))
            return False
    
    def sync_contas_receber(self, days_back: int = 30, max_records: int = 1000) -> bool:
        """
        Sincroniza dados de Contas a Receber do Oracle para PostgreSQL com embeddings
        
        Args:
            days_back: Quantos dias atrás buscar dados
            max_records: Máximo de registros por execução
        """
        logger.info(f"Sincronizando Contas a Receber ({days_back} dias, máx {max_records} registros)")
        
        try:
            data_inicio = datetime.now() - timedelta(days=days_back)
            
            # Busca dados de contas a receber no Oracle
            cr_data = self.oracle_adapter.execute_query(
                self.oracle_adapter.queries['cr_textual_data'],
                {'data_inicio': data_inicio, 'max_rows': max_records}
            )
            
            logger.info(f"Encontrados {len(cr_data)} títulos de contas a receber")
            
            if not cr_data:
                logger.warning("Nenhum título de contas a receber encontrado")
                return True
            
            # Processa cada título
            chunks_created = []
            
            for i, row in enumerate(cr_data):
                try:
                    # Verifica se já existe no PostgreSQL
                    chunk_id = f"cr_{row['registro_id']}"
                    existing = self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE chunk_id = %s",
                        (chunk_id,)
                    )
                    
                    if existing:
                        logger.debug(f"Título {chunk_id} já existe, pulando...")
                        continue
                    
                    # Cria chunk
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content_text': row['texto_completo'],
                        'entity': 'CONTAS_RECEBER',
                        'nivel_lgpd': row['nivel_lgpd'],
                        'source_file': 'oracle_cr',
                        'attributes': {
                            'valor_titulo': float(row.get('valor_titulo', 0)),
                            'saldo': float(row.get('saldo', 0)),
                            'nome_cliente': row.get('nome_cliente'),
                            'cnpj_cliente': row.get('cnpj_cliente'),
                            'nome_representante': row.get('nome_representante'),
                            'fatura': row.get('fatura'),
                            'ordem': row.get('ordem'),
                            'data_vencimento': str(row.get('data_vencimento')),
                            'data_emissao': str(row.get('data_emissao')),
                            'situacao': row.get('situacao_duplicata'),
                            'operacao': row.get('operacao'),
                            'banco': row.get('descricao_banco'),
                            'sync_timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    # Gera embedding
                    if self.embedding_generator:
                        logger.debug(f"Gerando embedding para título {i+1}/{len(cr_data)}")
                        embedding = self.embedding_generator.generate_embedding(row['texto_completo'])
                        chunk_data['embedding'] = embedding
                        chunk_data['embedding_model'] = self.embedding_generator.model_name
                        self.sync_stats['embeddings_generated'] += 1
                    
                    # Criptografia para dados sensíveis (LGPD ALTO/MEDIO)
                    encrypted_content = self._encrypt_if_needed(row['texto_completo'], row['nivel_lgpd'])
                    if encrypted_content:
                        chunk_data['encrypted_content'] = encrypted_content
                    
                    # Calcula hash
                    import hashlib
                    content_hash = hashlib.sha256(row['texto_completo'].encode()).hexdigest()
                    chunk_data['hash_sha256'] = content_hash
                    chunk_data['chunk_size'] = len(row['texto_completo'])
                    
                    chunks_created.append(chunk_data)
                    self.sync_stats['records_processed'] += 1
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"Processados {i+1}/{len(cr_data)} títulos")
                
                except Exception as e:
                    error_msg = f"Erro ao processar título CR {i}: {e}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            # Insere chunks no PostgreSQL
            if chunks_created:
                logger.info(f"Inserindo {len(chunks_created)} chunks CR no PostgreSQL...")
                
                inserted_count = 0
                for chunk_data in chunks_created:
                    if self.postgres_adapter.insert_chunk(chunk_data):
                        inserted_count += 1
                    else:
                        error_msg = f"Erro ao inserir chunk {chunk_data['chunk_id']}"
                        logger.error(error_msg)
                        self.sync_stats['errors'].append(error_msg)
                
                logger.info(f"Inseridos {inserted_count}/{len(chunks_created)} chunks CR com sucesso")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na sincronização de contas a receber: {e}")
            self.sync_stats['errors'].append(str(e))
            return False
    
    def sync_cp_resumos_agregados(self, period_months: int = 12) -> bool:
        """
        Sincroniza resumos agregados de Contas a Pagar
        
        Args:
            period_months: Quantos meses atrás buscar resumos
        """
        logger.info(f"Sincronizando resumos agregados CP ({period_months} meses)")
        
        try:
            periodo_inicio = (datetime.now() - timedelta(days=period_months*30)).strftime('%Y-%m')
            
            cp_resumos = self.oracle_adapter.execute_query(
                self.oracle_adapter.queries['cp_resumos_agregados'],
                {'periodo_inicio': periodo_inicio}
            )
            
            logger.info(f"Encontrados {len(cp_resumos)} resumos agregados CP")
            
            if not cp_resumos:
                logger.warning("Nenhum resumo agregado CP encontrado")
                return True
            
            for row in cp_resumos:
                try:
                    chunk_id = f"cp_resumo_{row['registro_id']}"
                    
                    # Verifica se já existe
                    existing = self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE chunk_id = %s",
                        (chunk_id,)
                    )
                    
                    if existing:
                        continue
                    
                    # Cria chunk agregado
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content_text': row['texto_resumo'],
                        'entity': 'CP_RESUMO_AGREGADO',
                        'nivel_lgpd': 'BAIXO',
                        'source_file': 'oracle_cp_resumo',
                        'attributes': {
                            'periodo': row['periodo'],
                            'empresa': row.get('empresa'),
                            'valor_total': float(row.get('valor_total', 0)),
                            'saldo_total': float(row.get('saldo_total', 0)),
                            'valor_medio': float(row.get('valor_medio', 0)),
                            'total_titulos': int(row.get('total_titulos', 0)),
                            'titulos_pagos': int(row.get('titulos_pagos', 0)),
                            'titulos_vencidos': int(row.get('titulos_vencidos', 0)),
                            'sync_timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    # Gera embedding
                    if self.embedding_generator:
                        embedding = self.embedding_generator.generate_embedding(row['texto_resumo'])
                        chunk_data['embedding'] = embedding
                        chunk_data['embedding_model'] = self.embedding_generator.model_name
                    
                    # Criptografia (dados agregados geralmente são BAIXO)
                    encrypted_content = self._encrypt_if_needed(row['texto_resumo'], 'BAIXO')
                    if encrypted_content:
                        chunk_data['encrypted_content'] = encrypted_content
                    
                    # Calcula hash
                    import hashlib
                    content_hash = hashlib.sha256(row['texto_resumo'].encode()).hexdigest()
                    chunk_data['hash_sha256'] = content_hash
                    chunk_data['chunk_size'] = len(row['texto_resumo'])
                    
                    # Insere no PostgreSQL
                    if self.postgres_adapter.insert_chunk(chunk_data):
                        self.sync_stats['records_processed'] += 1
                        self.sync_stats['embeddings_generated'] += 1
                
                except Exception as e:
                    error_msg = f"Erro ao processar resumo CP {row.get('registro_id')}: {e}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            logger.info("Sincronização de resumos CP concluída")
            return True
            
        except Exception as e:
            logger.error(f"Erro na sincronização de resumos CP: {e}")
            return False
    
    def sync_cr_resumos_agregados(self, period_months: int = 12) -> bool:
        """
        Sincroniza resumos agregados de Contas a Receber
        
        Args:
            period_months: Quantos meses atrás buscar resumos
        """
        logger.info(f"Sincronizando resumos agregados CR ({period_months} meses)")
        
        try:
            periodo_inicio = (datetime.now() - timedelta(days=period_months*30)).strftime('%Y-%m')
            
            cr_resumos = self.oracle_adapter.execute_query(
                self.oracle_adapter.queries['cr_resumos_agregados'],
                {'periodo_inicio': periodo_inicio}
            )
            
            logger.info(f"Encontrados {len(cr_resumos)} resumos agregados CR")
            
            if not cr_resumos:
                logger.warning("Nenhum resumo agregado CR encontrado")
                return True
            
            for row in cr_resumos:
                try:
                    chunk_id = f"cr_resumo_{row['registro_id']}"
                    
                    # Verifica se já existe
                    existing = self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE chunk_id = %s",
                        (chunk_id,)
                    )
                    
                    if existing:
                        continue
                    
                    # Cria chunk agregado
                    chunk_data = {
                        'chunk_id': chunk_id,
                        'content_text': row['texto_resumo'],
                        'entity': 'CR_RESUMO_AGREGADO',
                        'nivel_lgpd': 'BAIXO',
                        'source_file': 'oracle_cr_resumo',
                        'attributes': {
                            'periodo': row['periodo'],
                            'empresa': row.get('empresa'),
                            'valor_total': float(row.get('valor_total', 0)),
                            'saldo_total': float(row.get('saldo_total', 0)),
                            'valor_medio': float(row.get('valor_medio', 0)),
                            'total_duplicatas': int(row.get('total_duplicatas', 0)),
                            'duplicatas_recebidas': int(row.get('duplicatas_recebidas', 0)),
                            'duplicatas_vencidas': int(row.get('duplicatas_vencidas', 0)),
                            'sync_timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    # Gera embedding
                    if self.embedding_generator:
                        embedding = self.embedding_generator.generate_embedding(row['texto_resumo'])
                        chunk_data['embedding'] = embedding
                        chunk_data['embedding_model'] = self.embedding_generator.model_name
                    
                    # Criptografia (dados agregados geralmente são BAIXO)
                    encrypted_content = self._encrypt_if_needed(row['texto_resumo'], 'BAIXO')
                    if encrypted_content:
                        chunk_data['encrypted_content'] = encrypted_content
                    
                    # Calcula hash
                    import hashlib
                    content_hash = hashlib.sha256(row['texto_resumo'].encode()).hexdigest()
                    chunk_data['hash_sha256'] = content_hash
                    chunk_data['chunk_size'] = len(row['texto_resumo'])
                    
                    # Insere no PostgreSQL
                    if self.postgres_adapter.insert_chunk(chunk_data):
                        self.sync_stats['records_processed'] += 1
                        self.sync_stats['embeddings_generated'] += 1
                
                except Exception as e:
                    error_msg = f"Erro ao processar resumo CR {row.get('registro_id')}: {e}"
                    logger.error(error_msg)
                    self.sync_stats['errors'].append(error_msg)
            
            logger.info("Sincronização de resumos CR concluída")
            return True
            
        except Exception as e:
            logger.error(f"Erro na sincronização de resumos CR: {e}")
            return False
    
    def cleanup_old_embeddings(self, days_old: int = 90) -> int:
        """Remove embeddings antigos do PostgreSQL com log LGPD"""
        logger.info(f"Removendo embeddings antigos (>{days_old} dias)")
        
        try:
            from security.lgpd_audit import LGPDAuditLogger
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            result = self.postgres_adapter.execute_query(
                """
                DELETE FROM chunks 
                WHERE source_file IN ('oracle_sync', 'oracle_aggregated')
                AND created_at < %s
                RETURNING chunk_id
                """,
                (cutoff_date,)
            )
            
            removed_count = len(result) if result else 0
            logger.info(f"Removidos {removed_count} chunks antigos")
            
            # Log LGPD Art. 18 (exclusão)
            if removed_count > 0 and self.postgres_adapter.connection:
                audit_logger = LGPDAuditLogger(self.postgres_adapter.connection)
                audit_logger.log_deletion(
                    deletion_type='retention_cleanup',
                    affected_table='chunks',
                    records_deleted=removed_count,
                    deletion_reason=f'Limpeza automática - dados > {days_old} dias',
                    criteria_used={
                        'source_files': ['oracle_sync', 'oracle_aggregated'],
                        'cutoff_date': cutoff_date.isoformat(),
                        'days_old': days_old
                    },
                    requested_by='system'
                )
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Erro ao remover embeddings antigos: {e}")
            return 0
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Retorna status da sincronização"""
        try:
            # Status PostgreSQL
            pg_stats = self.postgres_adapter.get_chunks_summary() if self.postgres_adapter else {}
            
            # Status Oracle  
            oracle_stats = self.oracle_adapter.get_chunks_summary() if self.oracle_adapter else {}
            
            return {
                'oracle_status': {
                    'connected': self.oracle_adapter is not None,
                    'total_records': oracle_stats.get('total_chunks', 0),
                    'faturamento_total': oracle_stats.get('faturamento_total', 0)
                },
                'postgresql_status': {
                    'connected': self.postgres_adapter is not None,
                    'total_chunks': pg_stats.get('total_chunks', 0),
                    'oracle_chunks': len(self.postgres_adapter.execute_query(
                        "SELECT chunk_id FROM chunks WHERE source_file LIKE 'oracle_%'"
                    )) if self.postgres_adapter else 0
                },
                'last_sync': self.sync_stats,
                'recommendations': self._get_sync_recommendations()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter status: {e}")
            return {'error': str(e)}
    
    def _get_sync_recommendations(self) -> List[str]:
        """Gera recomendações baseadas no status"""
        recommendations = []
        
        if self.sync_stats['errors']:
            recommendations.append(f"Resolver {len(self.sync_stats['errors'])} erros encontrados")
        
        if self.sync_stats['records_processed'] < 100:
            recommendations.append("Aumentar período de sincronização para capturar mais dados")
        
        if self.sync_stats['embeddings_generated'] == 0:
            recommendations.append("Verificar configuração do gerador de embeddings")
        
        return recommendations
    
    def _log_sync_summary(self):
        """Log do resumo da sincronização"""
        duration = (self.sync_stats['completed_at'] - self.sync_stats['started_at']).total_seconds()
        
        logger.info("=" * 60)
        logger.info("RESUMO DA SINCRONIZAÇÃO ORACLE -> POSTGRESQL")
        logger.info("=" * 60)
        logger.info(f"Início: {self.sync_stats['started_at']}")
        logger.info(f"Fim: {self.sync_stats['completed_at']}")
        logger.info(f"Duração: {duration:.1f} segundos")
        logger.info(f"Registros processados: {self.sync_stats['records_processed']}")
        logger.info(f"Embeddings gerados: {self.sync_stats['embeddings_generated']}")
        logger.info(f"Erros: {len(self.sync_stats['errors'])}")
        
        if self.sync_stats['records_processed'] > 0:
            rate = self.sync_stats['records_processed'] / duration
            logger.info(f"Taxa: {rate:.1f} registros/segundo")
        
        if self.sync_stats['errors']:
            logger.info("Erros encontrados:")
            for error in self.sync_stats['errors'][:5]:  # Mostra apenas os primeiros 5
                logger.info(f"  - {error}")
        
        logger.info("=" * 60)
    
    def _encrypt_if_needed(self, content: str, nivel_lgpd: str) -> Optional[bytes]:
        """
        Criptografia AES-256-GCM para chunks sensíveis durante sincronização
        
        Args:
            content: Conteúdo do chunk
            nivel_lgpd: Nível LGPD (ALTO, MEDIO, BAIXO)
        
        Returns:
            bytes: Conteúdo criptografado ou None se não for necessário
        
        Política:
        - ALTO: Criptografa (dados pessoais - CNPJ, nome cliente)
        - MEDIO: Criptografa (dados financeiros sensíveis)
        - BAIXO: Não criptografa (dados agregados/públicos)
        """
        if not self.encryptor:
            return None
        
        # Só criptografa dados ALTO ou MEDIO
        if nivel_lgpd not in ['ALTO', 'MÉDIO', 'MEDIO']:
            return None
        
        try:
            encrypted_bytes = self.encryptor.encrypt(content)
            logger.debug(f"Chunk criptografado: {len(content)} chars → {len(encrypted_bytes)} bytes (LGPD: {nivel_lgpd})")
            return encrypted_bytes
        except Exception as e:
            logger.error(f"Erro ao criptografar chunk: {e}")
            return None
    
    def disconnect(self):
        """Desconecta dos bancos de dados"""
        if self.oracle_adapter:
            self.oracle_adapter.disconnect()
        
        if self.postgres_adapter:
            self.postgres_adapter.disconnect()
        
        logger.info("Desconectado dos bancos de dados")

def run_sync_example():
    """
    Exemplo de execução da sincronização COMPLETA (Vendas + CP + CR)
    
    Agora carrega configurações de variáveis de ambiente via .env
    Seguro para uso em qualquer ambiente (dev, staging, produção)
    """
    
    print("="* 80)
    print("SINCRONIZAÇÃO COMPLETA: VENDAS + CONTAS A PAGAR + CONTAS A RECEBER")
    print("=" * 80)
    
    # Carrega configurações de variáveis de ambiente via config centralizado
    oracle_config, postgres_config = load_config_from_env()
    
    try:
        # Inicializa sincronizador
        sync = OracleToPostgreSQLSync(oracle_config, postgres_config)
        
        # Conecta aos bancos
        if sync.connect_databases():
            print("\nSUCCESS: Conexões estabelecidas\n")
            
            # 1. Sincroniza VENDAS
            print("[1] SINCRONIZANDO VENDAS")
            print("-" * 80)
            success_vendas = sync.sync_textual_data_for_embeddings(days_back=30, max_records=1000)
            if success_vendas:
                print("SUCCESS: Vendas sincronizadas\n")
            else:
                print("ERROR: Erro na sincronização de vendas\n")
            
            # 2. Sincroniza CONTAS A PAGAR
            print("[2] SINCRONIZANDO CONTAS A PAGAR")
            print("-" * 80)
            success_cp = sync.sync_contas_pagar(days_back=30, max_records=1000)
            if success_cp:
                print("SUCCESS: Contas a pagar sincronizadas\n")
            else:
                print("ERROR: Erro na sincronização de contas a pagar\n")
            
            # 3. Sincroniza CONTAS A RECEBER
            print("[3] SINCRONIZANDO CONTAS A RECEBER")
            print("-" * 80)
            success_cr = sync.sync_contas_receber(days_back=30, max_records=1000)
            if success_cr:
                print("SUCCESS: Contas a receber sincronizadas\n")
            else:
                print("ERROR: Erro na sincronização de contas a receber\n")
            
            # 4. Sincroniza resumos agregados de VENDAS
            print("[4] SINCRONIZANDO RESUMOS AGREGADOS - VENDAS")
            print("-" * 80)
            sync.sync_aggregated_summaries(period_months=12)
            print("SUCCESS: Resumos agregados de vendas sincronizados\n")
            
            # 5. Sincroniza resumos agregados de CONTAS A PAGAR
            print("[5] SINCRONIZANDO RESUMOS AGREGADOS - CONTAS A PAGAR")
            print("-" * 80)
            sync.sync_cp_resumos_agregados(period_months=12)
            print("SUCCESS: Resumos agregados CP sincronizados\n")
            
            # 6. Sincroniza resumos agregados de CONTAS A RECEBER
            print("[6] SINCRONIZANDO RESUMOS AGREGADOS - CONTAS A RECEBER")
            print("-" * 80)
            sync.sync_cr_resumos_agregados(period_months=12)
            print("SUCCESS: Resumos agregados CR sincronizados\n")
            
            # Mostra status final
            print("=" * 80)
            print("STATUS FINAL DA SINCRONIZAÇÃO")
            print("=" * 80)
            status = sync.get_sync_status()
            print(f"\n[DATA] Oracle:")
            print(f"   Conectado: {status['oracle_status']['connected']}")
            print(f"   Total registros: {status['oracle_status']['total_records']:,}")
            
            print(f"\n[DATA] PostgreSQL:")
            print(f"   Conectado: {status['postgresql_status']['connected']}")
            print(f"   Total chunks: {status['postgresql_status']['total_chunks']:,}")
            print(f"   Chunks Oracle: {status['postgresql_status']['oracle_chunks']:,}")
            
            print(f"\n[STATS] Última Sincronização:")
            last_sync = status['last_sync']
            print(f"   Registros processados: {last_sync['records_processed']}")
            print(f"   Embeddings gerados: {last_sync['embeddings_generated']}")
            print(f"   Erros: {len(last_sync['errors'])}")
            
            if last_sync['errors']:
                print(f"\nWARNING: Erros encontrados:")
                for error in last_sync['errors'][:5]:
                    print(f"   - {error}")
            
        else:
            print("\nERROR: Não foi possível conectar aos bancos")
        
        # Desconecta
        sync.disconnect()
        print("\nSUCCESS: Sincronização concluída!")
        
    except Exception as e:
        print(f"\nERROR: Erro na sincronização: {e}")
        import traceback
        traceback.print_exc()

def load_config_from_env():
    """Carrega configuração de variáveis de ambiente via config centralizado"""
    from core.config import Config
    
    oracle = Config.oracle()
    postgres = Config.postgres()
    
    oracle_config = DatabaseConfig(
        host=oracle.host,
        port=oracle.port,
        database=oracle.sid or oracle.service_name or 'dbprod',
        user=oracle.user,
        password=oracle.password,
        db_type='oracle',
        additional_params={'service_name': oracle.service_name} if oracle.service_name else None
    )
    
    postgres_config = {
        'host': postgres.host,
        'port': postgres.port,
        'database': postgres.database,
        'user': postgres.user,
        'password': postgres.password
    }
    
    return oracle_config, postgres_config

def run_sync_auto(days_back: int = 30, max_records: int = 5000, period_months: int = 12):
    """Execução automática da sincronização com parâmetros configuráveis"""
    
    print("="* 80)
    print("SINCRONIZAÇÃO COMPLETA: VENDAS + CONTAS A PAGAR + CONTAS A RECEBER")
    print("=" * 80)
    print(f"Parâmetros: days_back={days_back}, max_records={max_records}, period_months={period_months}")
    print()
    
    # Carrega configuração de variáveis de ambiente
    oracle_config, postgres_config = load_config_from_env()
    
    try:
        # Inicializa sincronizador
        sync = OracleToPostgreSQLSync(oracle_config, postgres_config)
        
        # Conecta aos bancos
        if sync.connect_databases():
            print("\nSUCCESS: Conexões estabelecidas\n")
            
            # 1. Sincroniza VENDAS
            print("[1] SINCRONIZANDO VENDAS")
            print("-" * 80)
            success_vendas = sync.sync_textual_data_for_embeddings(days_back=days_back, max_records=max_records)
            if success_vendas:
                print("SUCCESS: Vendas sincronizadas\n")
            else:
                print("ERROR: Erro na sincronização de vendas\n")
            
            # 2. Sincroniza CONTAS A PAGAR
            print("[2] SINCRONIZANDO CONTAS A PAGAR")
            print("-" * 80)
            success_cp = sync.sync_contas_pagar(days_back=days_back, max_records=max_records)
            if success_cp:
                print("SUCCESS: Contas a pagar sincronizadas\n")
            else:
                print("ERROR: Erro na sincronização de contas a pagar\n")
            
            # 3. Sincroniza CONTAS A RECEBER
            print("[3] SINCRONIZANDO CONTAS A RECEBER")
            print("-" * 80)
            success_cr = sync.sync_contas_receber(days_back=days_back, max_records=max_records)
            if success_cr:
                print("SUCCESS: Contas a receber sincronizadas\n")
            else:
                print("ERROR: Erro na sincronização de contas a receber\n")
            
            # 4. Sincroniza resumos agregados de VENDAS
            print("[4] SINCRONIZANDO RESUMOS AGREGADOS - VENDAS")
            print("-" * 80)
            sync.sync_aggregated_summaries(period_months=period_months)
            print("SUCCESS: Resumos agregados de vendas sincronizados\n")
            
            # 5. Sincroniza resumos agregados de CONTAS A PAGAR
            print("[5] SINCRONIZANDO RESUMOS AGREGADOS - CONTAS A PAGAR")
            print("-" * 80)
            sync.sync_cp_resumos_agregados(period_months=period_months)
            print("SUCCESS: Resumos agregados CP sincronizados\n")
            
            # 6. Sincroniza resumos agregados de CONTAS A RECEBER
            print("[6] SINCRONIZANDO RESUMOS AGREGADOS - CONTAS A RECEBER")
            print("-" * 80)
            sync.sync_cr_resumos_agregados(period_months=period_months)
            print("SUCCESS: Resumos agregados CR sincronizados\n")
            
            # Mostra status final
            print("=" * 80)
            print("STATUS FINAL DA SINCRONIZAÇÃO")
            print("=" * 80)
            status = sync.get_sync_status()
            print(f"\n[DATA] Oracle:")
            print(f"   Conectado: {status['oracle_status']['connected']}")
            print(f"   Total registros: {status['oracle_status']['total_records']:,}")
            
            print(f"\n[DATA] PostgreSQL:")
            print(f"   Conectado: {status['postgresql_status']['connected']}")
            print(f"   Total chunks: {status['postgresql_status']['total_chunks']:,}")
            print(f"   Chunks Oracle: {status['postgresql_status']['oracle_chunks']:,}")
            
            print(f"\n[STATS] Última Sincronização:")
            last_sync = status['last_sync']
            print(f"   Registros processados: {last_sync['records_processed']}")
            print(f"   Embeddings gerados: {last_sync['embeddings_generated']}")
            print(f"   Erros: {len(last_sync['errors'])}")
            
            if last_sync['errors']:
                print(f"\nWARNING: Erros encontrados:")
                for error in last_sync['errors'][:5]:
                    print(f"   - {error}")
            
        else:
            print("\nERROR: Não foi possível conectar aos bancos")
            return False
        
        # Desconecta
        sync.disconnect()
        print("\nSUCCESS: Sincronização concluída!")
        return True
        
    except Exception as e:
        print(f"\nERROR: Erro na sincronização: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    print("ORACLE DATA SYNCHRONIZER - CATIVA TÊXTIL")
    print("=" * 50)
    
    # Verifica argumentos de linha de comando
    if '--help' in sys.argv or '-h' in sys.argv:
        print("\nUso: python -m src.data_processing.oracle_sync [opções]\n")
        print("Opções:")
        print("  --days DAYS         Número de dias a sincronizar (padrão: 30)")
        print("  --max MAX           Máximo de registros por entidade (padrão: 5000)")
        print("  --months MONTHS     Meses de resumos agregados (padrão: 12)")
        print("  -h, --help          Mostra esta ajuda")
        print("\nVariáveis de ambiente:")
        print("  ORACLE_HOST, ORACLE_PORT, ORACLE_USER, ORACLE_PASSWORD")
        print("  ORACLE_SERVICE_NAME (ou ORACLE_SID)")
        print("  PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD")
        print("  OPENAI_API_KEY (para embeddings)")
        print("\nExemplos:")
        print("  python -m src.data_processing.oracle_sync")
        print("  python -m src.data_processing.oracle_sync --days 60 --max 10000")
        sys.exit(0)
    
    # Executa automaticamente (padrão)
    days_back = 30
    max_records = 5000
    period_months = 12
    
    # Processa argumentos
    for i, arg in enumerate(sys.argv):
        if arg == '--days' and i + 1 < len(sys.argv):
            days_back = int(sys.argv[i + 1])
        elif arg == '--max' and i + 1 < len(sys.argv):
            max_records = int(sys.argv[i + 1])
        elif arg == '--months' and i + 1 < len(sys.argv):
            period_months = int(sys.argv[i + 1])
    
    print("\n[START] Executando sincronização automática...\n")
    success = run_sync_auto(days_back=days_back, max_records=max_records, period_months=period_months)
    sys.exit(0 if success else 1)
