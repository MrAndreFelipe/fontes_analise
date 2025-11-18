# src/integrations/whatsapp/response_formatter.py
"""
Response Formatter
Formats RAG responses for WhatsApp messaging
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any
import re

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class ResponseFormatter:
    """Formats RAG responses for WhatsApp display"""
    
    def __init__(self, max_length: int = 4096, use_llm: bool = True):
        """
        Initialize formatter
        
        Args:
            max_length: Maximum message length (WhatsApp limit)
            use_llm: Use LLM for natural response formatting
        """
        self.max_length = max_length
        self.use_llm = use_llm
        self.llm_client = None
        
        if use_llm:
            try:
                from ai.openai_client import OpenAIClient
                self.llm_client = OpenAIClient()
                if self.llm_client.api_key_configured:
                    logger.info("LLM formatting enabled (OpenAI)")
                else:
                    logger.warning("OpenAI not configured, using rule-based formatting")
                    self.use_llm = False
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client: {e}")
                self.use_llm = False
        
        logger.debug("ResponseFormatter initialized")
    
    def format_response(self, rag_response) -> str:
        """
        Format RAG response for WhatsApp
        
        Args:
            rag_response: RAGResponse object from RAG Engine
            
        Returns:
            Formatted string for WhatsApp
        """
        try:
            # Get answer text
            answer = rag_response.answer
            
            # Check if it's a Text-to-SQL response (detect by metadata)
            is_text_to_sql = rag_response.metadata.get('route') == 'text_to_sql'
            
            if is_text_to_sql and self.use_llm and self.llm_client:
                # Use LLM to format SQL responses naturally
                formatted = self._format_with_llm(answer, rag_response)
            elif is_text_to_sql:
                # Format Text-to-SQL responses with rules
                formatted = self._format_sql_response(answer, rag_response)
            else:
                # Apply standard WhatsApp formatting
                formatted = self._apply_whatsapp_formatting(answer)
            
            # Add metadata footer if low confidence
            if rag_response.confidence < 0.6:
                formatted += "\n\n(Nota: Recomenda-se validação adicional desta informação)"
            
            # Truncate if too long
            if len(formatted) > self.max_length:
                formatted = formatted[:self.max_length-50] + "\n\n...(mensagem truncada)"
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            return "Desculpe, ocorreu um erro ao formatar a resposta."
    
    def _format_with_llm(self, answer: str, rag_response) -> str:
        """
        Use LLM to format SQL response naturally for WhatsApp
        
        Args:
            answer: Raw SQL result text
            rag_response: Full RAG response
            
        Returns:
            Natural, conversational response
        """
        try:
            # Extract the SQL and results
            sql_query = None
            for source in rag_response.sources:
                if isinstance(source, dict) and 'sql' in source:
                    sql_query = source['sql']
                    break
            
            # Build prompt for LLM
            system_prompt = (
                "Voce eh o assistente virtual da Cativa Textil. Sua funcao eh interpretar dados estruturados e formata-los para WhatsApp de forma clara e profissional.\n\n"
                "REGRA FUNDAMENTAL: ANALISE DE CONTEXTO\n\n"
                "Antes de responder, SEMPRE analise:\n"
                "1. O que o usuario REALMENTE perguntou?\n"
                "2. Que tipo de resposta ele espera: um numero total OU uma lista detalhada?\n"
                "3. Os dados recebidos correspondem aa expectativa da pergunta?\n\n"
                "TIPOS DE RESPOSTA\n\n"
                "TIPO 1: VALOR AGREGADO UNICO\n"
                "Quando o usuario pede um TOTAL, SOMA ou VALOR CONSOLIDADO.\n"
                "Indicadores na pergunta: 'quanto', 'qual o total', 'soma de', 'valor total', 'quantos clientes compraram' (numero unico)\n"
                "Estrutura: 'Claro! [Confirmacao]: R$ X.XXX,XX'\n"
                "Exemplo: Pergunta='Quanto vendemos hoje?' -> Resposta='Claro! O total de vendas de hoje eh: R$ 550.000,00'\n\n"
                "TIPO 1.5: CAMPO UNICO NAO-MONETARIO\n"
                "Quando o usuario pede um CAMPO ESPECIFICO (numero do pedido, nome do cliente, etc).\n"
                "Indicadores: 'qual o numero', 'qual o nome', 'qual a data', 'qual pedido'\n"
                "Estrutura: 'Claro! [Campo solicitado]: [Valor]'\n"
                "Exemplo 1: Pergunta='Qual o numero do melhor pedido?' + Dados='NUMERO_PEDIDO | 843562' -> Resposta='Claro! O numero do melhor pedido eh: 843562'\n"
                "Exemplo 2: Pergunta='Qual o nome do cliente?' + Dados='NOME_CLIENTE | CONFECCOES EDINELI' -> Resposta='Claro! O cliente eh: CONFECCOES EDINELI'\n\n"
                "TIPO 2: TOTALIZACAO POR GRUPO\n"
                "Quando o usuario pede totais SEPARADOS por categoria/grupo.\n"
                "Indicadores: 'por cliente', 'por fornecedor', 'por produto', 'quais clientes mais compraram', 'breakdown'\n"
                "Estrutura: Lista cada grupo com seu total + linha 'Total geral: R$ XXX.XXX,XX (X grupos)'\n\n"
                "TIPO 3: LISTAGEM DETALHADA\n"
                "Quando o usuario pede para VER registros individuais.\n"
                "Indicadores: 'liste', 'mostre', 'quais sao', 'pedidos do cliente', 'vendas de hoje'\n"
                "Estrutura: Cada item com campos principais e secundarios em formato numerado\n\n"
                "REGRAS DE FORMATACAO\n\n"
                "Valores: Use sempre separador de milhar R$ 1.234,56 com duas casas decimais\n"
                "Datas: Formato DD/MM/YYYY ou DD/MM/YYYY as HH:MM se tiver hora\n"
                "Listagens: MAXIMO 10 itens, ordene MAIOR para MENOR, uma linha em branco entre itens\n"
                "Se houver mais de 10: indique 'Mostrando X de Y resultados'\n\n"
                "TRADUCAO DE CAMPOS TECNICOS\n"
                "NOMECLIENTE->Nome do Cliente | NOME_CLIENTE->Nome do Cliente | TOTAL->Total\n"
                "VALOR_ITEM_LIQUIDO->Valor Liquido | DATA_VENDA->Data da Venda | NUMERO_PEDIDO->Numero do Pedido\n"
                "VALOR_SALDO->Saldo | DATA_VENCIMENTO->Data de Vencimento | NOME_FORNECEDOR->Fornecedor\n"
                "QTD_ITENS->Quantidade de Itens | DESCRICAO_PRODUTO->Descricao do Produto\n\n"
                "TOM E ESTILO\n"
                "FAÇA: Profissional mas acessivel. Confirme o que foi solicitado. Termine oferecendo ajuda.\n"
                "NAO FAÇA: Emojis, markdown (**, __), simbolos especiais, jargoes tecnicos\n\n"
                "TRATAMENTO DE ERROS E CASOS ESPECIAIS\n"
                "Se dados REALMENTE vazios (0 linhas): 'Nao encontrei nenhum resultado para [periodo]. Quer tentar com outros parametros?'\n"
                "Se pergunta ambigua: 'Posso te mostrar de duas formas: [opcao 1] ou [opcao 2]. Qual prefere?'\n"
                "IMPORTANTE: Se receber 1 linha com 1 campo (ex: 'NUMERO_PEDIDO | 12345'), isso NAO eh dado vazio! Formate normalmente conforme TIPO 1.5\n\n"
                "CHECKLIST FINAL\n"
                "- Identifiquei corretamente o tipo de resposta?\n"
                "- Os dados sao suficientes?\n"
                "- Formatei valores monetarios corretamente?\n"
                "- Traduzi todos os campos tecnicos?\n"
                "- Removi formatacao markdown e emojis?\n"
                "- Limitei a 10 itens se for lista?\n"
                "- Ofereci ajuda adicional?\n\n"
                "Lembre-se: Sua prioridade eh entender a INTENCAO do usuario, nao apenas processar dados cegamente."
            )
            
            user_prompt = (
                f"Dados do Oracle:\n"
                f"{answer}\n\n"
                f"Formate de acordo com o tipo de dado (total unico, grupo de totais, ou listagem). Respeite o tipo exato."
            )
            
            # Call LLM
            response = self.llm_client.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500  # Aumentado para evitar cortes em listagens
            )
            
            formatted = response.choices[0].message.content.strip()
            
            # Remove markdown formatting para WhatsApp
            formatted = self._apply_whatsapp_formatting(formatted)
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error in LLM formatting: {e}")
            # Fallback to rule-based formatting
            return self._format_sql_response(answer, rag_response)
    
    def _format_sql_response(self, answer: str, rag_response) -> str:
        """
        Format SQL query responses to be more natural and friendly
        
        Args:
            answer: Raw answer from Text-to-SQL
            rag_response: Full RAG response object
            
        Returns:
            Formatted friendly response
        """
        try:
            # Extract table data if present
            lines = answer.split('\n')
            
            # Check if it's a "no rows" response
            if 'Nenhuma linha retornada' in answer:
                return "Não encontrei registros para este período.\n\nPossíveis motivos:\n• Sistema ainda não atualizou os dados\n• Não houve movimentações neste período\n\nQue tal tentar outro período? Estou aqui para ajudar!"
            
            # Parse tabular results
            if '|' in answer or 'total' in answer.lower():
                # Try to extract and format the data
                formatted = self._format_table_data(answer)
                if formatted:
                    return formatted
            
            # Fallback to standard formatting
            return self._apply_whatsapp_formatting(answer)
            
        except Exception as e:
            logger.error(f"Error formatting SQL response: {e}")
            return self._apply_whatsapp_formatting(answer)
    
    def _format_table_data(self, text: str) -> str:
        """
        Format table data into friendly message
        
        Args:
            text: Raw table text
            
        Returns:
            Formatted friendly message
        """
        try:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Look for header and data
            header_idx = -1
            data_lines = []
            
            for i, line in enumerate(lines):
                if '-----' in line or '|' in line:
                    header_idx = i
                    break
            
            if header_idx >= 0 and header_idx + 1 < len(lines):
                # Extract data after the separator
                for line in lines[header_idx+1:]:
                    if line and not line.startswith('...'):
                        data_lines.append(line)
            
            # Try to parse single value results (like SUM, COUNT)
            if len(data_lines) == 1 and not '|' in data_lines[0]:
                value = data_lines[0].strip()
                
                # Check if it's a monetary value
                try:
                    num_value = float(value)
                    
                    # Format based on magnitude
                    if num_value >= 1000000:
                        formatted_value = f"R$ {num_value:,.2f}".replace(',', '.')
                        formatted_value = formatted_value.replace('.', ',', 1)  # First dot to comma
                    elif num_value >= 1000:
                        formatted_value = f"R$ {num_value:,.2f}".replace(',', '.')
                        formatted_value = formatted_value.replace('.', ',', 1)
                    else:
                        formatted_value = f"R$ {num_value:.2f}".replace('.', ',')
                    
                    return f"Encontrei o seguinte valor total:\n\n{formatted_value}\n\nPrecisa de mais alguma informação?"
                except:
                    return f"Resultado da consulta:\n\n{value}\n\nPosso ajudar com algo mais?"
            
            # Multiple rows - format as list
            if len(data_lines) > 1:
                result = "Encontrei os seguintes registros:\n\n"
                for i, line in enumerate(data_lines[:10], 1):
                    # Clean and format each line
                    clean_line = line.replace('|', ' - ').strip()
                    result += f"{i}. {clean_line}\n"
                
                if len(data_lines) > 10:
                    result += f"\n(Mais {len(data_lines)-10} registro(s) disponível(is))"
                
                result += "\n\nPosso ajudar com mais alguma coisa?"
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing table data: {e}")
            return None
    
    def _apply_whatsapp_formatting(self, text: str) -> str:
        """
        Clean text by removing markdown formatting characters
        
        Args:
            text: Raw text
            
        Returns:
            Clean text without markdown
        """
        # Remove markdown bold (**text** or *text*)
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        
        # Remove italic (_text_)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        
        # Remove strikethrough (~text~)
        text = re.sub(r'~([^~]+)~', r'\1', text)
        
        return text
    
    def _format_sources(self, sources: list) -> str:
        """
        Format sources section (removed to keep messages cleaner)
        
        Args:
            sources: List of source dicts
            
        Returns:
            Empty string (sources now integrated in main message)
        """
        # Sources are now integrated in the formatted message
        # No need for separate sources section
        return ""
    
    def format_error_message(self, error_type: str = "generic") -> str:
        """
        Format error message for user
        
        Args:
            error_type: Type of error
            
        Returns:
            User-friendly error message
        """
        error_messages = {
            "generic": "Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.",
            "timeout": "A consulta demorou mais que o esperado. Tente ser mais específico na consulta.",
            "no_results": "Não encontrei informações com esses critérios. Tente reformular a consulta.",
            "database": "No momento estou com dificuldade para acessar os dados. Tente novamente em instantes."
        }
        
        return error_messages.get(error_type, error_messages["generic"])
    
    def format_welcome_message(self) -> str:
        """
        Format welcome message
        
        Returns:
            Welcome message text
        """
        return (
            "Olá! Bem-vindo ao Sistema da Cativa Têxtil.\n\n"
            "Posso ajudá-lo com consultas sobre:\n"
            "• Pedidos de venda\n"
            "• Informações de clientes\n"
            "• Dados de representantes\n"
            "• Vendas por região\n"
            "• Relatórios e análises\n\n"
            "Exemplos do que você pode perguntar:\n"
            "• Qual o valor do pedido 123456?\n"
            "• Total de vendas hoje\n"
            "• Ranking de representantes do mês\n\n"
            "Como posso ajudar você hoje?"
        )
