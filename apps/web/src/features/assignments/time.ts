export const beijingInput = (utc: string) =>
  new Date(new Date(utc).getTime() + 8 * 3600_000).toISOString().slice(0, 16)
export const fromBeijing = (value: string) =>
  new Date(`${value}${value.length === 16 ? ':00' : ''}+08:00`).toISOString()
export const beijingTime = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'medium',
    timeStyle: 'short',
    hour12: false,
  }).format(new Date(value))
