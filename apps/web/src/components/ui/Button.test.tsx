import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Button } from './Button'
import { Field } from './Field'

it('按钮显示操作提示，禁用与忙碌分别说明', () => {
  const view = render(
    <Button disabled title="请填写来源提交编号">
      请求提示
    </Button>,
  )
  expect(screen.getByRole('button')).toHaveAttribute('title', '请填写来源提交编号')
  view.rerender(
    <Button busy title="请求提示">
      请求提示
    </Button>,
  )
  expect(screen.getByRole('button')).toHaveAttribute('title', '正在处理，请稍候。')
  view.rerender(<Button>保存</Button>)
  expect(screen.getByRole('button')).toHaveAttribute('title', '保存')
})

it('编号有格式示例但保持空值，普通字段不添加编号说明', () => {
  render(
    <>
      <Field label="课程编号" />
      <Field label="课程名称" />
    </>,
  )
  expect(screen.getByLabelText('课程编号')).toHaveAttribute(
    'placeholder',
    expect.stringContaining('00000000-0000-4000-8000-000000000001'),
  )
  expect(screen.getByLabelText('课程编号')).toHaveValue('')
  expect(screen.getByText(/仅展示编号格式/)).toBeVisible()
  expect(screen.getByLabelText('课程名称')).not.toHaveAttribute('placeholder')
})

it('数字测试编号保持数字语义，组合按钮文字也提供提示', () => {
  render(
    <>
      <Field label="测试编号" type="number" min={1} max={10} />
      <Button>载入测试 {2}</Button>
    </>,
  )
  expect(screen.getByLabelText('测试编号')).not.toHaveAttribute('placeholder')
  expect(screen.queryByText(/仅展示编号格式/)).toBeNull()
  expect(screen.getByRole('button', { name: '载入测试 2' })).toHaveAttribute('title', '载入测试 2')
})
