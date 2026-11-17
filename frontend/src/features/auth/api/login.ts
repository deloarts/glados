import authApi from '@/core/api/auth'

import type { LoginRequest } from '../types/authRequest'
import type { LoginResponse, TokenResponse } from '../types/authResponse'

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const form = new URLSearchParams()
  form.set('username', credentials.username)
  form.set('password', credentials.password)

  const response = await authApi.post<LoginResponse>('/login/access-token', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

  return response.data
}

export async function verifyTotp(
  partial_token: string,
  totp_code: string,
  trust_device = false,
): Promise<TokenResponse> {
  const response = await authApi.post<TokenResponse>('/login/totp', {
    partial_token,
    totp_code,
    trust_device,
  })
  return response.data
}
