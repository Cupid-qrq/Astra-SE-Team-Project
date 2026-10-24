import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { Button } from './Button'
import { Field } from './Field'
import { DataTable } from './DataTable'
import { StatePanel } from './StatePanel'
import { ConfirmDialog } from './ConfirmDialog'

describe('公共组件的可访问行为', () => {
  it('确认操作进行中时焦点留在弹窗，Tab不能进入背景', async () => {
    function Example() {
      const [busy, setBusy] = useState(false)
      return (
        <>
          <Button>背景操作</Button>
          <ConfirmDialog
            open
            title="确认发布"
            description="发布后冻结版本"
            confirmLabel="发布"
            busy={busy}
            onCancel={() => {}}
            onConfirm={() => setBusy(true)}
          />
        </>
      )
    }
    render(<Example />)
    await userEvent.click(screen.getByRole('button', { name: /^发布$/ }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveFocus()
    await userEvent.tab()
    expect(dialog).toHaveFocus()
    await userEvent.tab({ shift: true })
    expect(dialog).toHaveFocus()
  })
  it('字段提供 label、错误关联并保留输入', async () => {
    render(<Field label="课程名称" name="title" error="最多 100 个字符" defaultValue="程序设计" />)
    const field = screen.getByLabelText('课程名称')
    expect(field).toHaveValue('程序设计')
    expect(field).toHaveAccessibleDescription('最多 100 个字符')
    expect(field).toHaveAttribute('aria-invalid', 'true')
  })
  it('空表说明下一步而不是显示空网格', () => {
    render(
      <DataTable
        caption="课程"
        rows={[]}
        columns={[
          { key: 'title', heading: '课程名称', render: (row: { title: string }) => row.title },
        ]}
        rowKey={(row) => row.title}
        empty="暂未加入课程，请联系任课教师。"
      />,
    )
    expect(screen.getByText('暂未加入课程，请联系任课教师。')).toBeVisible()
  })
  it('显示服务故障且允许用户主动重试', async () => {
    const retry = vi.fn()
    render(
      <StatePanel kind="error" title="暂时无法加载" description="请稍后重试" onRetry={retry} />,
    )
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(retry).toHaveBeenCalledOnce()
  })
  it('忙碌按钮拒绝重复点击', async () => {
    const click = vi.fn()
    render(
      <Button busy onClick={click}>
        保存
      </Button>,
    )
    await userEvent.click(screen.getByRole('button'))
    expect(click).not.toHaveBeenCalled()
  })
  it('对话框可 Escape 关闭并恢复触发按钮焦点', async () => {
    function Example() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <Button onClick={() => setOpen(true)}>归档课程</Button>
          <ConfirmDialog
            open={open}
            title="确认归档"
            description="归档后只读"
            confirmLabel="确认归档"
            onCancel={() => setOpen(false)}
            onConfirm={() => setOpen(false)}
          />
        </>
      )
    }
    render(<Example />)
    const trigger = screen.getByRole('button', { name: '归档课程' })
    await userEvent.click(trigger)
    expect(screen.getByRole('dialog', { name: '确认归档' })).toBeVisible()
    expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })
})
