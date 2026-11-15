import { render, screen, fireEvent } from '@testing-library/react'
import { it, expect, vi, afterEach } from 'vitest'
import { CopyIdentifier } from './CopyIdentifier'
afterEach(() => vi.unstubAllGlobals())
it('复制完整编号，失败时保留可手动复制的值', async () => {
  const value = '589bc0e1-4b1e-4593-92a3-6de94901cdc8'
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  render(<CopyIdentifier label="课程编号" value={value} />)
  fireEvent.click(screen.getByRole('button', { name: '复制课程编号' }))
  expect(await screen.findByText('已复制')).toBeVisible()
  expect(writeText).toHaveBeenCalledWith(value)
  writeText.mockRejectedValue(new Error('denied'))
  fireEvent.click(screen.getByRole('button', { name: '复制课程编号' }))
  expect(await screen.findByText('复制未获允许，请选中编号手动复制。')).toBeVisible()
  expect(screen.getByText(value)).toBeVisible()
})
