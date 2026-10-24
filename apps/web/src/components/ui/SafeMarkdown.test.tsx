import { render } from '@testing-library/react'
import { expect, it } from 'vitest'
import { SafeMarkdown } from './SafeMarkdown'

const attacks = [
  '<script>alert(1)</script>',
  '<img src="https://attacker.invalid/a" onerror="alert(1)">',
  '<svg onload="alert(1)"></svg>',
  '<iframe src="https://attacker.invalid"></iframe>',
  '<object data="https://attacker.invalid"></object>',
  '<video poster="https://attacker.invalid/a"></video>',
  '<audio src="https://attacker.invalid/a"></audio>',
  '<style>@import "https://attacker.invalid/a";</style>',
  '<link rel="stylesheet" href="https://attacker.invalid/a">',
  '<meta http-equiv="refresh" content="0;url=https://attacker.invalid">',
  '[执行](javascript:alert%281%29)',
  '[执行](JaVaScRiPt:alert%281%29)',
  '[执行](data:text/html,boom)',
  '![外链](https://attacker.invalid/image)',
  '![数据](data:image/svg+xml,boom)',
  '<a onclick="alert(1)">点我</a>',
  '<input autofocus onfocus="alert(1)">',
  '<form action="https://attacker.invalid"><button>提交</button></form>',
  '<math><mtext><img src=x onerror=alert(1)></mtext></math>',
  '<details open ontoggle="alert(1)">x</details>',
]
it.each(attacks)('不渲染可执行内容或自动外发资源：%s', (value) => {
  const { container } = render(<SafeMarkdown>{value}</SafeMarkdown>)
  expect(
    container.querySelector(
      'script,img,svg,iframe,object,video,audio,style,link,meta,input,form,math,details',
    ),
  ).toBeNull()
  for (const el of container.querySelectorAll('*')) {
    expect([...el.attributes].some((a) => a.name.startsWith('on'))).toBe(false)
    expect(el.getAttribute('href') || '').not.toMatch(/^(javascript|data):/i)
  }
})
