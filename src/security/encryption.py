# src/security/encryption.py
"""
Criptografia AES-256-GCM para proteção de dados sensíveis
Sistema RAG Cativa Têxtil - Conformidade LGPD Art. 46
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AES256Encryptor:
    """
    Criptografia AES-256-GCM para dados sensíveis LGPD
    
    Features:
    - AES-256 (chave de 256 bits)
    - Modo GCM (Galois/Counter Mode)
    - Autenticação integrada (detecta adulteração)
    - IV único por operação
    
    Conformidade:
    - LGPD Art. 46 (segurança técnica)
    - NIST FIPS 197 (padrão AES)
    - NIST SP 800-38D (modo GCM)
    """
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Inicializa encryptor AES-256-GCM
        
        Args:
            key: Chave de 32 bytes (256 bits). Se None, carrega do .env
            
        Raises:
            ValueError: Se chave inválida ou não configurada
        """
        if key is None:
            key = self._load_key_from_env()
        
        if len(key) != 32:
            raise ValueError(f"Chave deve ter 32 bytes (256 bits), recebido: {len(key)} bytes")
        
        self.cipher = AESGCM(key)
        logger.info("AES-256-GCM Encryptor inicializado com sucesso")
    
    def _load_key_from_env(self) -> bytes:
        """
        Carrega chave de criptografia do ambiente
        
        Returns:
            bytes: Chave de 32 bytes
            
        Raises:
            ValueError: Se ENCRYPTION_KEY não configurada
        """
        key_b64 = os.getenv('ENCRYPTION_KEY')
        
        if not key_b64:
            raise ValueError(
                "ENCRYPTION_KEY não configurada no .env\n"
                "Execute: python scripts/generate_encryption_key.py\n"
                "Depois adicione ao .env: ENCRYPTION_KEY=<chave_gerada>"
            )
        
        try:
            key = base64.b64decode(key_b64)
            if len(key) != 32:
                raise ValueError(f"Chave decodificada tem tamanho incorreto: {len(key)} bytes")
            return key
        except Exception as e:
            raise ValueError(f"Erro ao decodificar ENCRYPTION_KEY: {e}")
    
    def encrypt(self, plaintext: str) -> bytes:
        """
        Criptografa texto usando AES-256-GCM
        
        Args:
            plaintext: Texto a criptografar (string UTF-8)
            
        Returns:
            bytes: IV (12) + Ciphertext (variável) + Tag (16)
            
        Raises:
            ValueError: Se texto vazio
            
        Example:
            >>> encryptor = AES256Encryptor()
            >>> encrypted = encryptor.encrypt("CNPJ: 03.221.721/0001-10")
            >>> len(encrypted)  # 12 (IV) + 28 (texto) + 16 (tag) = 56
            56
        """
        if not plaintext:
            raise ValueError("Texto para criptografar não pode ser vazio")
        
        # 1. Gera IV aleatório (12 bytes = 96 bits)
        # CRÍTICO: IV deve ser único para cada operação
        iv = os.urandom(12)
        
        # 2. Converte texto para bytes UTF-8
        plaintext_bytes = plaintext.encode('utf-8')
        
        # 3. Criptografa com AES-256-GCM
        # GCM retorna: ciphertext + tag de autenticação (16 bytes)
        ciphertext_and_tag = self.cipher.encrypt(iv, plaintext_bytes, None)
        
        # 4. Retorna: IV + Ciphertext + Tag
        # Formato: [12 bytes IV][n bytes ciphertext][16 bytes tag]
        result = iv + ciphertext_and_tag
        
        logger.debug(f"Criptografado: {len(plaintext)} chars → {len(result)} bytes")
        return result
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Descriptografa dados usando AES-256-GCM
        
        Args:
            encrypted_data: IV + Ciphertext + Tag
            
        Returns:
            str: Texto original descriptografado
            
        Raises:
            ValueError: Se dados inválidos ou corrompidos
            InvalidTag: Se dados foram adulterados (falha autenticação)
            
        Example:
            >>> encryptor = AES256Encryptor()
            >>> encrypted = encryptor.encrypt("Dados sensíveis")
            >>> decrypted = encryptor.decrypt(encrypted)
            >>> decrypted
            'Dados sensíveis'
        """
        # Valida tamanho mínimo: 12 (IV) + 0 (texto) + 16 (tag) = 28 bytes
        if len(encrypted_data) < 28:
            raise ValueError(
                f"Dados criptografados inválidos: "
                f"{len(encrypted_data)} bytes (mínimo: 28 bytes)"
            )
        
        try:
            # 1. Separa IV (primeiros 12 bytes)
            iv = encrypted_data[:12]
            
            # 2. Pega ciphertext + tag (restante)
            ciphertext_and_tag = encrypted_data[12:]
            
            # 3. Descriptografa e valida tag de autenticação
            # Se tag inválida, lança InvalidTag exception
            plaintext_bytes = self.cipher.decrypt(iv, ciphertext_and_tag, None)
            
            # 4. Converte bytes para string UTF-8
            plaintext = plaintext_bytes.decode('utf-8')
            
            logger.debug(f"Descriptografado: {len(encrypted_data)} bytes → {len(plaintext)} chars")
            return plaintext
            
        except Exception as e:
            logger.error(f"Erro ao descriptografar: {e}")
            raise ValueError(f"Falha na descriptografia: {e}")
    
    def encrypt_to_base64(self, plaintext: str) -> str:
        """
        Criptografa e retorna em base64 (útil para JSON/texto)
        
        Args:
            plaintext: Texto a criptografar
            
        Returns:
            str: Dados criptografados em base64
            
        Example:
            >>> encryptor = AES256Encryptor()
            >>> encrypted_b64 = encryptor.encrypt_to_base64("Dados sensíveis")
            >>> encrypted_b64[:20]
            'j3OaLhtM3BkYzFm4R...'
        """
        encrypted = self.encrypt(plaintext)
        return base64.b64encode(encrypted).decode('ascii')
    
    def decrypt_from_base64(self, encrypted_b64: str) -> str:
        """
        Descriptografa dados em formato base64
        
        Args:
            encrypted_b64: Dados criptografados em base64
            
        Returns:
            str: Texto original
            
        Example:
            >>> encryptor = AES256Encryptor()
            >>> encrypted_b64 = encryptor.encrypt_to_base64("Teste")
            >>> decrypted = encryptor.decrypt_from_base64(encrypted_b64)
            >>> decrypted
            'Teste'
        """
        encrypted = base64.b64decode(encrypted_b64)
        return self.decrypt(encrypted)


# Funções auxiliares
def generate_key() -> bytes:
    """
    Gera chave AES-256 criptograficamente segura
    
    Returns:
        bytes: Chave de 32 bytes (256 bits)
        
    Example:
        >>> key = generate_key()
        >>> len(key)
        32
    """
    return AESGCM.generate_key(bit_length=256)


def key_to_base64(key: bytes) -> str:
    """
    Converte chave para base64 (para armazenar no .env)
    
    Args:
        key: Chave de 32 bytes
        
    Returns:
        str: Chave em base64
        
    Example:
        >>> key = generate_key()
        >>> key_b64 = key_to_base64(key)
        >>> len(key_b64)
        44
    """
    return base64.b64encode(key).decode('ascii')


# Testes unitários
def test_basic_encryption():
    """Teste básico de criptografia e descriptografia"""
    print("Teste 1: Criptografia básica")
    print("-" * 50)
    
    # Gera chave de teste
    test_key = generate_key()
    encryptor = AES256Encryptor(key=test_key)
    
    # Teste
    original = "CNPJ: 03.221.721/0001-10"
    print(f"Original: {original}")
    
    encrypted = encryptor.encrypt(original)
    print(f"Criptografado: {encrypted.hex()[:60]}... ({len(encrypted)} bytes)")
    
    decrypted = encryptor.decrypt(encrypted)
    print(f"Descriptografado: {decrypted}")
    
    assert original == decrypted, "Erro: texto não corresponde"
    print("PASSOU\n")


def test_iv_uniqueness():
    """Teste: mesmo texto gera ciphertexts diferentes (IVs únicos)"""
    print("Teste 2: Unicidade de IVs")
    print("-" * 50)
    
    test_key = generate_key()
    encryptor = AES256Encryptor(key=test_key)
    
    original = "Dados de teste"
    encrypted1 = encryptor.encrypt(original)
    encrypted2 = encryptor.encrypt(original)
    
    print(f"Ciphertext 1: {encrypted1.hex()[:40]}...")
    print(f"Ciphertext 2: {encrypted2.hex()[:40]}...")
    
    assert encrypted1 != encrypted2, "Erro: IVs devem ser únicos"
    
    # Mas ambos descriptografam para o texto original
    assert encryptor.decrypt(encrypted1) == original
    assert encryptor.decrypt(encrypted2) == original
    
    print("PASSOU\n")


def test_authentication():
    """Teste: detecta adulteração de dados"""
    print("Teste 3: Autenticação (detecta adulteração)")
    print("-" * 50)
    
    test_key = generate_key()
    encryptor = AES256Encryptor(key=test_key)
    
    original = "Dados importantes"
    encrypted = encryptor.encrypt(original)
    
    # Adultera último byte (tag de autenticação)
    tampered = encrypted[:-1] + b'\x00'
    
    print(f"Tentando descriptografar dados adulterados...")
    
    try:
        encryptor.decrypt(tampered)
        assert False, "Deveria ter detectado adulteração"
    except ValueError as e:
        print(f"Adulteração detectada: {str(e)[:60]}...")
        print("PASSOU\n")


def test_long_text():
    """Teste com texto longo"""
    print("Teste 4: Texto longo")
    print("-" * 50)
    
    test_key = generate_key()
    encryptor = AES256Encryptor(key=test_key)
    
    long_text = "Pedido 843562. Cliente: CONFECCOES EDILENI LTDA. " * 50
    print(f"Tamanho do texto: {len(long_text)} caracteres")
    
    encrypted = encryptor.encrypt(long_text)
    print(f"Tamanho criptografado: {len(encrypted)} bytes")
    
    decrypted = encryptor.decrypt(encrypted)
    
    assert long_text == decrypted
    print("PASSOU\n")


def test_base64_encoding():
    """Teste conversão base64"""
    print("Teste 5: Encoding base64")
    print("-" * 50)
    
    test_key = generate_key()
    encryptor = AES256Encryptor(key=test_key)
    
    original = "Teste base64"
    encrypted_b64 = encryptor.encrypt_to_base64(original)
    print(f"Base64: {encrypted_b64[:50]}...")
    
    decrypted = encryptor.decrypt_from_base64(encrypted_b64)
    
    assert original == decrypted
    print("PASSOU\n")


def run_all_tests():
    """Executa todos os testes"""
    print("\n" + "=" * 60)
    print("TESTES DE CRIPTOGRAFIA AES-256-GCM")
    print("=" * 60 + "\n")
    
    tests = [
        test_basic_encryption,
        test_iv_uniqueness,
        test_authentication,
        test_long_text,
        test_base64_encoding
    ]
    
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"FALHOU: {e}\n")
            return False
        except Exception as e:
            print(f"ERRO: {e}\n")
            return False
    
    print("=" * 60)
    print("TODOS OS TESTES PASSARAM!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    run_all_tests()
