"""
RSA 密钥管理工具

- 应用启动时自动加载或生成 RSA 密钥对
- 提供公钥 PEM 导出和私钥解密方法
- 密钥文件存储在项目根目录的 .keys/ 目录下
"""

import os
import base64
import logging
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

logger = logging.getLogger(__name__)

# 密钥存储目录
_KEYS_DIR = Path(__file__).resolve().parent.parent.parent / '.keys'
_PRIVATE_KEY_PATH = _KEYS_DIR / 'private_key.pem'
_PUBLIC_KEY_PATH = _KEYS_DIR / 'public_key.pem'

# 内存缓存
_private_key = None
_public_key_pem = None


def _generate_key_pair():
    """生成 RSA 2048 密钥对并保存到文件"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    _KEYS_DIR.mkdir(parents=True, exist_ok=True)

    # 保存私钥
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _PRIVATE_KEY_PATH.write_bytes(private_pem)

    # 保存公钥
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _PUBLIC_KEY_PATH.write_bytes(public_pem)

    logger.info('[RSA] 已生成新的 RSA 密钥对')
    return private_key, public_pem


def _load_keys():
    """从文件加载密钥对，不存在则自动生成"""
    global _private_key, _public_key_pem

    if _PRIVATE_KEY_PATH.exists() and _PUBLIC_KEY_PATH.exists():
        try:
            private_pem = _PRIVATE_KEY_PATH.read_bytes()
            _private_key = serialization.load_pem_private_key(private_pem, password=None)
            _public_key_pem = _PUBLIC_KEY_PATH.read_bytes()
            logger.info('[RSA] 已从文件加载 RSA 密钥对')
            return
        except Exception as e:
            logger.warning(f'[RSA] 加载密钥文件失败，将重新生成: {e}')

    _private_key, _public_key_pem = _generate_key_pair()


def get_public_key_pem() -> str:
    """获取公钥 PEM 字符串（供前端使用）"""
    if _public_key_pem is None:
        _load_keys()
    return _public_key_pem.decode('utf-8')


def decrypt_password(encrypted_b64: str) -> str:
    """
    解密前端 RSA 加密的密码

    Args:
        encrypted_b64: Base64 编码的 RSA 密文

    Returns:
        解密后的明文密码
    """
    if _private_key is None:
        _load_keys()

    encrypted_bytes = base64.b64decode(encrypted_b64)
    decrypted_bytes = _private_key.decrypt(
        encrypted_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return decrypted_bytes.decode('utf-8')


# 应用启动时预加载密钥
_load_keys()
