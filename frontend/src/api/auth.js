/**
 * 认证相关 API
 */
import { api } from './request'
import { rsaEncrypt } from '@/utils/crypto'

export const authApi = {
  login: async (username, password) => {
    const passwordEncrypted = await rsaEncrypt(password)
    return api.post('/login/', { username, password_encrypted: passwordEncrypted })
  },
  register: async ({ username, password, email }) => {
    const [passwordEncrypted, confirmEncrypted] = await Promise.all([
      rsaEncrypt(password),
      rsaEncrypt(password),
    ])
    return api.post('/register.html', {
      username,
      email,
      password_encrypted: passwordEncrypted,
      password_confirm_encrypted: confirmEncrypted,
    })
  },
  resetPassword: async ({ username, email, password, password_confirm }) => {
    const [passwordEncrypted, confirmEncrypted] = await Promise.all([
      rsaEncrypt(password),
      rsaEncrypt(password_confirm),
    ])
    return api.post('/reset-password/', {
      username,
      email,
      password_encrypted: passwordEncrypted,
      password_confirm_encrypted: confirmEncrypted,
    })
  },
  refreshToken: (refresh) => api.post('/api/auth/refresh/', { refresh }),
  getCurrentUser: () => api.get('/api/auth/user/'),
}
