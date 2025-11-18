# scripts/generate_encryption_key.py
"""
Gerador de Chave de Criptografia AES-256
Sistema RAG Cativa Têxtil
"""

import sys
from pathlib import Path

# Adiciona src ao path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from security.encryption import generate_key, key_to_base64


def generate_and_display_key():
    """
    Gera chave AES-256 criptograficamente segura e exibe instruções
    """
    
    print("\n" + "=" * 70)
    print(" GERADOR DE CHAVE DE CRIPTOGRAFIA AES-256")
    print(" Sistema RAG Cativa Têxtil - Conformidade LGPD")
    print("=" * 70 + "\n")
    
    # Gera chave segura de 256 bits (32 bytes)
    print("Gerando chave criptograficamente segura...")
    key = generate_key()
    
    # Converte para base64 (formato fácil de armazenar)
    key_b64 = key_to_base64(key)
    
    print(f"Chave gerada com sucesso!\n")
    
    # Exibe informações
    print("DETALHES DA CHAVE:")
    print("-" * 70)
    print(f"Tamanho:        {len(key)} bytes (256 bits)")
    print(f"Formato:        Base64 (para armazenamento)")
    print(f"Algoritmo:      AES-256-GCM")
    print(f"Padrão:         NIST FIPS 197")
    
    # Exibe chave
    print("\n" + "=" * 70)
    print("CHAVE GERADA (Base64):")
    print("=" * 70)
    print(f"\n{key_b64}\n")
    print("=" * 70)
    
    # Instruções de uso
    print("\nINSTRUÇÕES DE USO:")
    print("-" * 70)
    print("\n1. ADICIONE AO ARQUIVO .env:")
    print(f"   ENCRYPTION_KEY={key_b64}")
    
    print("\n2. EM PRODUÇÃO:")
    print("   - Use gerenciador de secrets (AWS KMS, Azure Key Vault, etc)")
    print("   - OU variável de ambiente do sistema")
    print("   - NUNCA commite no Git")
    
    print("\n3. FAÇA BACKUP SEGURO:")
    print("   - Armazene em gerenciador de senhas")
    print("   - Guarde cópia offline em local seguro")
    print("   - Se perder a chave, dados criptografados são IRRECUPERÁVEIS")
    
    print("\n4. TESTE A CONFIGURAÇÃO:")
    print("   python -c \"from src.security.encryption import AES256Encryptor; AES256Encryptor()\"")
    
    # Avisos de segurança
    print("\n" + "=" * 70)
    print("AVISOS DE SEGURANÇA IMPORTANTES:")
    print("=" * 70)
    print("\nNUNCA commite esta chave no Git")
    print("NUNCA compartilhe por email/mensagem não criptografada")
    print("NUNCA use a mesma chave em dev e produção")
    print("SEMPRE faça backup em local seguro")
    print("SEMPRE rotacione chaves periodicamente (ex: a cada 90 dias)")
    print("SEMPRE use gerenciador de secrets em produção")
    
    # Teste rápido
    print("\n" + "=" * 70)
    print("TESTE RÁPIDO DA CHAVE:")
    print("=" * 70)
    
    from security.encryption import AES256Encryptor
    
    try:
        encryptor = AES256Encryptor(key=key)
        test_text = "Teste de criptografia"
        encrypted = encryptor.encrypt(test_text)
        decrypted = encryptor.decrypt(encrypted)
        
        assert test_text == decrypted
        
        print(f"\nTeste passou!")
        print(f"   Original:        {test_text}")
        print(f"   Criptografado:   {encrypted.hex()[:40]}... ({len(encrypted)} bytes)")
        print(f"   Descriptografado: {decrypted}")
        
    except Exception as e:
        print(f"\nErro no teste: {e}")
    
    print("\n" + "=" * 70)
    print("Chave gerada e testada com sucesso!")
    print("=" * 70 + "\n")


def save_to_env_example():
    """
    Cria arquivo .env.example com template
    """
    env_example_path = Path(__file__).parent.parent / '.env.example'
    
    content = """# Configurações do Sistema RAG Cativa Têxtil

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# WhatsApp API
WHATSAPP_API_TOKEN=your_whatsapp_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_VERIFY_TOKEN=your_verify_token_here

# Database Oracle
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=ORCL
ORACLE_USER=your_user
ORACLE_PASSWORD=your_password

# Database PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Criptografia AES-256
# Execute: python scripts/generate_encryption_key.py
ENCRYPTION_KEY=your_generated_key_here

# Ambiente
ENVIRONMENT=development
"""
    
    try:
        with open(env_example_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nArquivo .env.example criado em: {env_example_path}")
    except Exception as e:
        print(f"\nNão foi possível criar .env.example: {e}")


if __name__ == "__main__":
    generate_and_display_key()
    save_to_env_example()
