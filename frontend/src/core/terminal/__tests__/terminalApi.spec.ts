import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AxiosError } from 'axios'
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

const sessionExpired = vi.fn<() => void>()

vi.mock('@/core/stores/currentUserStore', () => ({
  useCurrentUserStore: () => ({ sessionExpired }),
}))

import {
  getTerminalDeviceFeed,
  getTerminalDeviceState,
  requestTerminalSession,
  terminalHttp,
} from '../terminalApi'
import type { TerminalSessionBody } from '../terminalApi'

const requests: InternalAxiosRequestConfig[] = []
let answer: (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>
const originalAdapter = terminalHttp.defaults.adapter

describe('terminalApi', () => {
  beforeEach(() => {
    requests.length = 0
    answer = async (config) => ({ data: {}, status: 200, statusText: 'OK', headers: {}, config })
    const adapter: AxiosAdapter = (config) => {
      requests.push(config)
      return answer(config)
    }
    terminalHttp.defaults.adapter = adapter
  })

  afterEach(() => {
    terminalHttp.defaults.adapter = originalAdapter
  })

  it('sends the terminal token as a Bearer header and no cookies', async () => {
    await getTerminalDeviceState('token-1')
    await getTerminalDeviceFeed('token-1')

    expect(requests.map((config) => config.url)).toEqual(['/state', '/feed'])
    for (const config of requests) {
      expect(config.headers.Authorization).toBe('Bearer token-1')
      expect(config.withCredentials).toBe(false)
    }
  })

  it('sends the terminal key only when the bridge has one', async () => {
    const body = { public_key: 'pk', nonce: 'n', signature: 's' } as TerminalSessionBody

    await requestTerminalSession(body, 'terminal-key')
    await requestTerminalSession(body, null)

    expect(requests[0]!.headers['X-Api-Key']).toBe('terminal-key')
    expect(requests[1]!.headers['X-Api-Key']).toBeUndefined()
  })

  it('never expires the web session on a 401 from a device call', async () => {
    answer = async (config) => {
      throw new AxiosError('unauthorized', 'ERR_BAD_REQUEST', config, undefined, {
        data: {},
        status: 401,
        statusText: 'Unauthorized',
        headers: {},
        config,
      })
    }

    await expect(getTerminalDeviceState('expired')).rejects.toBeInstanceOf(AxiosError)
    expect(sessionExpired).not.toHaveBeenCalled()
  })
})
