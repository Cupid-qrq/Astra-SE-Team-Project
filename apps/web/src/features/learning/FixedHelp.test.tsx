import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { FixedHelp } from './FixedHelp'

const value = {
  feedback_version_id: 'version-one',
  title: '答案错误',
  explanation: '检查 **边界**。',
  checklist: ['核对格式', '手算小例子'],
}
it('嵌入固定版本并安全显示说明和清单，不依赖模型', () => {
  const { container } = render(<FixedHelp state="FINISHED" verdict="WA" value={value} />)
  expect(screen.getByRole('heading', { name: '答案错误' })).toBeInTheDocument()
  expect(screen.getByText('手算小例子')).toBeInTheDocument()
  expect(container.querySelector('strong')).toHaveTextContent('边界')
  expect(screen.getByText(/version-one/)).toBeInTheDocument()
})
it('非终态与成功判定不显示旧的错误帮助', () => {
  const { rerender } = render(<FixedHelp state="RUNNING" verdict={null} value={value} />)
  expect(screen.queryByText('答案错误')).not.toBeInTheDocument()
  expect(screen.getByText(/评测完成后/)).toBeInTheDocument()
  rerender(<FixedHelp state="FINISHED" verdict="AC" value={value} />)
  expect(screen.queryByText('答案错误')).not.toBeInTheDocument()
})
it('SE给出平台故障说明，缺失版本显示可恢复错误', () => {
  const { rerender } = render(<FixedHelp state="FINISHED" verdict="SE" error="网络断开" />)
  expect(screen.getByText(/平台故障/)).toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('网络断开')
  rerender(<FixedHelp state="FINISHED" verdict="WA" loading />)
  expect(screen.getByRole('status')).toHaveTextContent('正在读取')
})
