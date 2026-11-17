import { describe, it, expect, vi, beforeEach } from 'vitest'

const postMock = vi.fn<(url: string, payload?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { post: (url: string, payload?: unknown) => postMock(url, payload) },
}))

import { sendMail } from '../sendMail'
import type { SendMailPayload } from '../sendMail'

describe('sendMail', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('POSTs the payload to /mail/send', async () => {
    const payload: SendMailPayload = {
      to: 'someone@example.com',
      subject: 'Hello',
      html_body: '<p>Hi</p>',
    }
    postMock.mockResolvedValue({ data: undefined })

    await sendMail(payload)

    expect(postMock).toHaveBeenCalledWith('/mail/send', payload)
  })

  it('forwards optional cc/reply_to fields untouched', async () => {
    const payload: SendMailPayload = {
      to: 'someone@example.com',
      subject: 'Hello',
      html_body: '<p>Hi</p>',
      cc: 'cc@example.com',
      reply_to: 'reply@example.com',
    }
    postMock.mockResolvedValue({ data: undefined })

    await sendMail(payload)

    expect(postMock).toHaveBeenCalledWith('/mail/send', payload)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('502 bad gateway')
    postMock.mockRejectedValue(error)

    await expect(
      sendMail({ to: 'a@example.com', subject: 'x', html_body: 'y' }),
    ).rejects.toBe(error)
  })
})
