/**
 * RSA 加密工具（node-forge + OAEP 填充）
 *
 * - 从后端获取公钥并缓存
 * - 使用 RSA-OAEP (SHA-256) 加密密码
 */
import forge from 'node-forge'

let cachedPublicKey = null
let fetchPromise = null

/**
 * 从后端获取 RSA 公钥（带缓存）
 */
async function fetchPublicKey() {
  if (cachedPublicKey) return cachedPublicKey

  if (!fetchPromise) {
    fetchPromise = fetch('/api/auth/public-key/')
      .then(res => res.json())
      .then(data => {
        if (data.success && data.public_key) {
          cachedPublicKey = data.public_key
          return cachedPublicKey
        }
        throw new Error('获取公钥失败')
      })
      .finally(() => {
        fetchPromise = null
      })
  }

  return fetchPromise
}

/**
 * 使用 RSA-OAEP 公钥加密文本
 *
 * @param {string} text - 待加密的明文
 * @returns {Promise<string>} Base64 编码的密文
 */
export async function rsaEncrypt(text) {
  const publicKeyPem = await fetchPublicKey()

  const publicKey = forge.pki.publicKeyFromPem(publicKeyPem)
  const encrypted = publicKey.encrypt(text, 'RSA-OAEP', {
    md: forge.md.sha256.create(),
    mgf1: { md: forge.md.sha256.create() },
  })

  return forge.util.encode64(encrypted)
}

/**
 * 清除缓存的公钥（密钥轮换时调用）
 */
export function clearPublicKeyCache() {
  cachedPublicKey = null
}
