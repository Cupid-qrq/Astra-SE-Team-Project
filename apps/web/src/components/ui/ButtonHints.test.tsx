import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
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

it('链接、折叠说明和选择控件都有提示且保留原无障碍说明', () => {
  render(
    <>
      <ButtonHints />
      <a href="/courses">返回课程</a>
      <details>
        <summary>管理讨论</summary>
      </details>
      <label>
        显示我的姓名
        <input type="checkbox" aria-describedby="existing" />
      </label>
      <span id="existing">仅本课程</span>
    </>,
  )
  fireEvent.focusIn(screen.getByRole('link'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('课程')
  fireEvent.pointerOver(screen.getByText('管理讨论'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('讨论')
  const checkbox = screen.getByRole('checkbox')
  fireEvent.focusIn(checkbox)
  expect(screen.getByRole('tooltip')).toHaveTextContent('显示我的姓名')
  expect(checkbox.getAttribute('aria-describedby')).toContain('existing')
  const hintId = screen.getByRole('tooltip').id
  expect(hintId).not.toBe('')
  expect(checkbox.getAttribute('aria-describedby')).toContain(hintId)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(checkbox).toHaveAttribute('aria-describedby', 'existing')
})

it('fieldset禁用的选择控件解释不可用，页面移除后提示关闭', async () => {
  const view = render(
    <>
      <ButtonHints />
      <fieldset disabled>
        <label>
          作业状态
          <select>
            <option>全部</option>
          </select>
        </label>
        <label>
          显示姓名
          <input type="checkbox" />
        </label>
      </fieldset>
    </>,
  )
  fireEvent.pointerOver(screen.getByRole('combobox'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('暂不可用')
  fireEvent.pointerOver(screen.getByRole('checkbox'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('暂不可用')
  view.rerender(<ButtonHints />)
  await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
})

it('课程文字入口在悬停前已有具体说明，并随动态状态更新', async () => {
  const view = render(
    <>
      <ButtonHints />
      <a href="/courses/c/problems">管理题目</a>
      <a href="/courses/c/assignments/new">新建作业</a>
    </>,
  )
  const link = screen.getByRole('link', { name: '管理题目' })
  expect(link).toHaveAttribute('title', '查看本课程题库，创建题目、维护版本并进行预检发布。')
  expect(screen.getByRole('link', { name: '新建作业' })).toHaveAttribute(
    'title',
    '从本课程已发布题目中选题，设置分值、开放时间和截止时间。',
  )
  view.rerender(
    <>
      <ButtonHints />
      <a href="/courses/c/problems" aria-busy="true">
        管理题目
      </a>
      <a href="/courses/c/assignments/new">新建作业</a>
    </>,
  )
  await waitFor(() => expect(link).toHaveAttribute('title', '正在处理，请稍候。'))
  view.rerender(
    <>
      <ButtonHints />
      <a href="/courses/c/problems">管理题目</a>
      <a href="/courses/c/assignments/new">新建作业</a>
    </>,
  )
  await waitFor(() =>
    expect(link).toHaveAttribute('title', '查看本课程题库，创建题目、维护版本并进行预检发布。'),
  )
})
it('键盘聚焦引发滚动时提示保持可见并跟随入口，Escape关闭', () => {
  render(
    <>
      <ButtonHints />
      <a href="/courses/c/problems">管理题目</a>
    </>,
  )
  const link = screen.getByRole('link')
  const rect = vi.spyOn(link, 'getBoundingClientRect').mockReturnValue({
    left: 30,
    right: 110,
    top: 100,
    bottom: 130,
    width: 80,
    height: 30,
  } as DOMRect)
  act(() => link.focus())
  expect(screen.getByRole('tooltip')).toBeVisible()
  rect.mockReturnValue({
    left: 30,
    right: 110,
    top: 40,
    bottom: 70,
    width: 80,
    height: 30,
  } as DOMRect)
  fireEvent.scroll(window)
  expect(screen.getByRole('tooltip')).toBeVisible()
  expect(screen.getByRole('tooltip')).toHaveStyle({ top: '78px' })
  fireEvent.keyDown(link, { key: 'Escape' })
  expect(screen.queryByRole('tooltip')).toBeNull()
  rect.mockRestore()
})
it('卸载时恢复自动生成的原生属性，保留作者说明', () => {
  const view = render(
    <>
      <ButtonHints />
      <a href="/courses">我的课程</a>
      <button title="作者说明">保存</button>
    </>,
  )
  const link = screen.getByRole('link')
  expect(link).toHaveAttribute('title')
  view.rerender(
    <>
      <a href="/courses">我的课程</a>
      <button title="作者说明">保存</button>
    </>,
  )
  expect(link).not.toHaveAttribute('title')
  expect(screen.getByRole('button')).toHaveAttribute('title', '作者说明')
})

it('屏幕外链接聚焦后自动滚入时仍出现提示', () => {
  render(
    <>
      <ButtonHints />
      <a href="/courses/c/problems">管理题目</a>
    </>,
  )
  const link = screen.getByRole('link')
  const rect = vi.spyOn(link, 'getBoundingClientRect').mockReturnValue({
    left: 30,
    right: 110,
    top: 1200,
    bottom: 1230,
    width: 80,
    height: 30,
  } as DOMRect)
  act(() => link.focus())
  expect(screen.queryByRole('tooltip')).toBeNull()
  rect.mockReturnValue({
    left: 30,
    right: 110,
    top: 100,
    bottom: 130,
    width: 80,
    height: 30,
  } as DOMRect)
  fireEvent.scroll(window)
  expect(screen.getByRole('tooltip')).toHaveTextContent('查看本课程题库')
  rect.mockRestore()
})
it('已经展开的提示随处理中及作者说明变化同步更新', async () => {
  const view = render(
    <>
      <ButtonHints />
      <a href="/courses/c/problems">管理题目</a>
    </>,
  )
  const link = screen.getByRole('link')
  act(() => link.focus())
  expect(screen.getByRole('tooltip')).toHaveTextContent('查看本课程题库')
  view.rerender(
    <>
      <ButtonHints />
      <a href="/courses/c/problems" aria-busy="true">
        管理题目
      </a>
    </>,
  )
  await waitFor(() => expect(screen.getByRole('tooltip')).toHaveTextContent('正在处理'))
  view.rerender(
    <>
      <ButtonHints />
      <a href="/courses/c/problems" data-tooltip="当前课程已归档，只能查看题目。">
        管理题目
      </a>
    </>,
  )
  await waitFor(() =>
    expect(screen.getByRole('tooltip')).toHaveTextContent('当前课程已归档，只能查看题目。'),
  )
})

it('链接失去交互属性后恢复原生属性并收起提示', async () => {
  const view = render(
    <>
      <ButtonHints />
      <a href="/courses">我的课程</a>
    </>,
  )
  const link = screen.getByRole('link')
  act(() => link.focus())
  expect(screen.getByRole('tooltip')).toBeVisible()
  view.rerender(
    <>
      <ButtonHints />
      <a>我的课程</a>
    </>,
  )
  await waitFor(() => expect(link).not.toHaveAttribute('title'))
  expect(screen.queryByRole('tooltip')).toBeNull()
})
