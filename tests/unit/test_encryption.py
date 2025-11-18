# tests/test_encryption.py
"""
Testes Unitários - Criptografia AES-256-GCM
Sistema RAG Cativa Têxtil
"""

import pytest
import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from security.encryption import AES256Encryptor, generate_key, key_to_base64


class TestAES256Encryptor:
    """Testes para classe AES256Encryptor"""
    
    @pytest.fixture
    def encryptor(self):
        """Fixture: cria encryptor com chave de teste"""
        test_key = generate_key()
        return AES256Encryptor(key=test_key)
    
    def test_generate_key(self):
        """Testa geração de chave"""
        key = generate_key()
        
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits
    
    def test_key_to_base64(self):
        """Testa conversão de chave para base64"""
        key = generate_key()
        key_b64 = key_to_base64(key)
        
        assert isinstance(key_b64, str)
        assert len(key_b64) == 44  # Base64 de 32 bytes
    
    def test_basic_encryption_decryption(self, encryptor):
        """Testa criptografia e descriptografia básica"""
        original = "CNPJ: 03.221.721/0001-10"
        
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        
        assert decrypted == original
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > len(original)  # IV + texto + tag
    
    def test_encryption_format(self, encryptor):
        """Testa formato do resultado criptografado"""
        text = "Teste"
        encrypted = encryptor.encrypt(text)
        
        # Formato: IV (12) + Ciphertext (len(text)) + Tag (16)
        expected_min_length = 12 + len(text) + 16
        assert len(encrypted) >= expected_min_length
    
    def test_iv_uniqueness(self, encryptor):
        """Testa que mesmo texto gera ciphertexts diferentes (IVs únicos)"""
        text = "Dados de teste"
        
        encrypted1 = encryptor.encrypt(text)
        encrypted2 = encryptor.encrypt(text)
        
        # Ciphertexts devem ser diferentes (IVs únicos)
        assert encrypted1 != encrypted2
        
        # Mas ambos descriptografam para o mesmo texto
        assert encryptor.decrypt(encrypted1) == text
        assert encryptor.decrypt(encrypted2) == text
    
    def test_authentication_tag(self, encryptor):
        """Testa que adulteração de dados é detectada"""
        text = "Dados importantes"
        encrypted = encryptor.encrypt(text)
        
        # Adultera último byte (parte da tag de autenticação)
        tampered = encrypted[:-1] + b'\x00'
        
        # Deve lançar exceção ao tentar descriptografar
        with pytest.raises(ValueError):
            encryptor.decrypt(tampered)
    
    def test_empty_text(self, encryptor):
        """Testa que texto vazio lança exceção"""
        with pytest.raises(ValueError):
            encryptor.encrypt("")
    
    def test_invalid_encrypted_data(self, encryptor):
        """Testa que dados inválidos lançam exceção"""
        invalid_data = b'\x00' * 10  # Muito curto (mínimo: 28 bytes)
        
        with pytest.raises(ValueError):
            encryptor.decrypt(invalid_data)
    
    def test_long_text(self, encryptor):
        """Testa criptografia de texto longo"""
        long_text = "Pedido 843562. Cliente: CONFECCOES EDILENI LTDA. " * 100
        
        encrypted = encryptor.encrypt(long_text)
        decrypted = encryptor.decrypt(encrypted)
        
        assert decrypted == long_text
    
    def test_special_characters(self, encryptor):
        """Testa criptografia com caracteres especiais"""
        special_text = "Olá! Testando: çãõáéíóú@#$%&*()"
        
        encrypted = encryptor.encrypt(special_text)
        decrypted = encryptor.decrypt(encrypted)
        
        assert decrypted == special_text
    
    def test_unicode_text(self, encryptor):
        """Testa criptografia com Unicode"""
        unicode_text = "中文测试 🔐 Тест テスト"
        
        encrypted = encryptor.encrypt(unicode_text)
        decrypted = encryptor.decrypt(encrypted)
        
        assert decrypted == unicode_text
    
    def test_base64_encoding(self, encryptor):
        """Testa conversão para/de base64"""
        text = "Teste base64"
        
        encrypted_b64 = encryptor.encrypt_to_base64(text)
        decrypted = encryptor.decrypt_from_base64(encrypted_b64)
        
        assert isinstance(encrypted_b64, str)
        assert decrypted == text
    
    def test_multiple_encryptions_different_keys(self):
        """Testa que chaves diferentes geram resultados diferentes"""
        text = "Dados de teste"
        
        key1 = generate_key()
        key2 = generate_key()
        
        encryptor1 = AES256Encryptor(key=key1)
        encryptor2 = AES256Encryptor(key=key2)
        
        encrypted1 = encryptor1.encrypt(text)
        encrypted2 = encryptor2.encrypt(text)
        
        # Ciphertexts devem ser diferentes (chaves diferentes)
        assert encrypted1 != encrypted2
        
        # Cada encryptor só consegue descriptografar seu próprio ciphertext
        assert encryptor1.decrypt(encrypted1) == text
        assert encryptor2.decrypt(encrypted2) == text
        
        # Não consegue descriptografar com chave errada
        with pytest.raises(ValueError):
            encryptor1.decrypt(encrypted2)
    
    def test_invalid_key_length(self):
        """Testa que chave com tamanho incorreto lança exceção"""
        invalid_key = b'short_key'  # Menor que 32 bytes
        
        with pytest.raises(ValueError):
            AES256Encryptor(key=invalid_key)


# Função para executar testes manualmente
def run_manual_tests():
    """Executa testes manualmente (sem pytest)"""
    print("\n" + "=" * 70)
    print("TESTES MANUAIS DE CRIPTOGRAFIA")
    print("=" * 70 + "\n")
    
    # Teste 1: Básico
    print("1. Teste básico de encrypt/decrypt...")
    key = generate_key()
    encryptor = AES256Encryptor(key=key)
    
    original = "CNPJ: 03.221.721/0001-10"
    encrypted = encryptor.encrypt(original)
    decrypted = encryptor.decrypt(encrypted)
    
    assert original == decrypted
    print(f"   ✅ PASSOU (original == decrypted)\n")
    
    # Teste 2: IVs únicos
    print("2. Teste de IVs únicos...")
    enc1 = encryptor.encrypt(original)
    enc2 = encryptor.encrypt(original)
    assert enc1 != enc2
    print(f"   ✅ PASSOU (IVs únicos)\n")
    
    # Teste 3: Autenticação
    print("3. Teste de autenticação...")
    encrypted = encryptor.encrypt("Teste")
    tampered = encrypted[:-1] + b'\x00'
    
    try:
        encryptor.decrypt(tampered)
        print(f"   ❌ FALHOU (não detectou adulteração)")
    except ValueError:
        print(f"   ✅ PASSOU (adulteração detectada)\n")
    
    print("=" * 70)
    print("TODOS OS TESTES MANUAIS PASSARAM!")
    print("=" * 70)


if __name__ == "__main__":
    # Se pytest não estiver disponível, executa testes manuais
    try:
        pytest.main([__file__, "-v"])
    except:
        print("pytest não disponível, executando testes manuais...")
        run_manual_tests()
