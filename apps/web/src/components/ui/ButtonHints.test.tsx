import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ButtonHints } from './ButtonHints'
import { Button } from './Button'

it('禁用按钮悬停显示说明，移开后关闭，且不触发操作', async () => {
  render(
    <>
      <ButtonHints />
      <Button disabled title="先填写操作理由">
        暂停
      </Button>
    </>,
  )
  const button = screen.getByRole('button')
  fireEvent.pointerOver(button)
  expect(screen.getByRole('tooltip')).toHaveTextContent('先填写操作理由')
  expect(button).toBeDisabled()
  fireEvent.pointerOut(button)
  await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
})
it('原生按钮键盘聚焦可显示提示，Esc和滚动关闭', () => {
  render(
    <>
      <ButtonHints />
      <button data-tooltip="按状态筛选课程">全部课程</button>
    </>,
  )
  const button = screen.getByRole('button')
  fireEvent.focusIn(button)
  expect(screen.getByRole('tooltip')).toHaveTextContent('按状态筛选课程')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('tooltip')).toBeNull()
  fireEvent.focusIn(button)
  fireEvent.scroll(window)
  expect(screen.queryByRole('tooltip')).toBeNull()
})
it('提示可处理后续插入的按钮，点击时收起', () => {
  const view = render(<ButtonHints />)
  view.rerender(
    <>
      <ButtonHints />
      <button data-tooltip="导出本页数据">导出</button>
    </>,
  )
  fireEvent.pointerOver(screen.getByRole('button'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('导出本页数据')
  fireEvent.pointerDown(screen.getByRole('button'))
  expect(screen.queryByRole('tooltip')).toBeNull()
})

it('指针可移入提示框阅读，Escape仍可关闭', () => {
  render(
    <>
      <ButtonHints />
      <Button title="完整操作说明">操作</Button>
    </>,
  )
  const button = screen.getByRole('button')
  fireEvent.pointerOver(button)
  const tooltip = screen.getByRole('tooltip')
  fireEvent.pointerOut(button, { relatedTarget: tooltip })
  fireEvent.pointerOver(tooltip)
  expect(screen.getByRole('tooltip')).toHaveTextContent('完整操作说明')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('tooltip')).toBeNull()
})
