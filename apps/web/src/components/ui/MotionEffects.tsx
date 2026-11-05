import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Pause, Play } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Button } from './Button'

const preferenceKey = 'astra.visualMotion'
const MotionContext = createContext({ enabled: false, reduced: false, toggle: () => {} })

export function MotionProvider({ children }: { children: ReactNode }) {
  const [preferred, setPreferred] = useState(() => {
    try {
      return localStorage.getItem(preferenceKey) !== 'off'
    } catch {
      return true
    }
  })
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  )
  const enabled = preferred && !reduced
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const change = () => setReduced(query?.matches ?? false)
    query?.addEventListener('change', change)
    return () => query?.removeEventListener('change', change)
  }, [])
  useEffect(() => {
    document.documentElement.dataset.motion = enabled ? 'on' : 'off'
    return () => {
      delete document.documentElement.dataset.motion
    }
  }, [enabled])
  function toggle() {
    const next = !preferred
    setPreferred(next)
    try {
      localStorage.setItem(preferenceKey, next ? 'on' : 'off')
    } catch {
      /* The current session can still pause. */
    }
  }
  return (
    <MotionContext.Provider value={{ enabled, reduced, toggle }}>{children}</MotionContext.Provider>
  )
}

export function MotionToggle() {
  const { enabled, reduced, toggle } = useContext(MotionContext)
  return (
    <Button
      className="motion-toggle"
      variant="quiet"
      onClick={toggle}
      disabled={reduced}
      aria-label={enabled ? '暂停动态效果' : '开启动态效果'}
      aria-pressed={enabled}
      title={
        reduced
          ? '当前跟随系统的减少动态设置。'
          : enabled
            ? '暂停粒子、视差与背景动画。'
            : '开启粒子、视差与背景动画。'
      }
    >
      {enabled ? <Pause size={13} aria-hidden="true" /> : <Play size={13} aria-hidden="true" />}
      <span>动效 {enabled ? '开启' : '暂停'}</span>
    </Button>
  )
}

export function ParticleField() {
  const { enabled } = useContext(MotionContext)
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const target = ref.current
    if (!target || !enabled) return
    const rendering = target.getContext('2d')
    if (!rendering) return
    const canvas = target
    const context = rendering
    let width = 0,
      height = 0,
      frame = 0,
      previous = 0,
      visible = false
    let pointer = { x: -1000, y: -1000 }
    const color = getComputedStyle(canvas).color
    function resize() {
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
      canvas.width = Math.round(width * ratio)
      canvas.height = Math.round(height * ratio)
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
    }
    function draw(time: number) {
      frame = requestAnimationFrame(draw)
      if (time - previous < 32) return
      previous = time
      context.clearRect(0, 0, width, height)
      const count = width < 600 ? 28 : 52
      const points = Array.from({ length: count }, (_, i) => {
        let x = ((i * 0.61803398875 + 0.09) % 1) * width + Math.sin(time * 0.00012 + i) * 13
        let y = ((i * 0.41421356 + 0.17) % 1) * height + Math.cos(time * 0.0001 + i * 2) * 17
        const distance = Math.hypot(x - pointer.x, y - pointer.y)
        if (distance < 150 && distance > 0) {
          const force = (1 - distance / 150) * 12
          x += ((x - pointer.x) / distance) * force
          y += ((y - pointer.y) / distance) * force
        }
        return { x, y }
      })
      context.fillStyle = color
      context.strokeStyle = color
      context.lineWidth = 0.6
      points.forEach((point, i) => {
        context.globalAlpha = i % 7 === 0 ? 0.85 : 0.32
        const size = i % 7 === 0 ? 2.2 : 1
        context.fillRect(point.x, point.y, size, size)
        for (let j = i + 1; j < points.length; j++) {
          const other = points[j],
            distance = Math.hypot(point.x - other.x, point.y - other.y)
          if (distance < 130) {
            context.globalAlpha = (1 - distance / 130) * 0.16
            context.beginPath()
            context.moveTo(point.x, point.y)
            context.lineTo(other.x, other.y)
            context.stroke()
          }
        }
        const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y)
        if (distance < 170) {
          context.globalAlpha = (1 - distance / 170) * 0.45
          context.beginPath()
          context.moveTo(point.x, point.y)
          context.lineTo(pointer.x, pointer.y)
          context.stroke()
        }
      })
    }
    function activity() {
      cancelAnimationFrame(frame)
      if (visible && !document.hidden) {
        canvas.dataset.motionState = 'running'
        frame = requestAnimationFrame(draw)
      } else {
        canvas.dataset.motionState = 'paused'
      }
    }
    function move(event: PointerEvent) {
      const rect = canvas.getBoundingClientRect()
      pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top }
    }
    const size = new ResizeObserver(resize)
    size.observe(canvas)
    resize()
    const visibility = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      activity()
    })
    visibility.observe(canvas)
    window.addEventListener('pointermove', move, { passive: true })
    document.addEventListener('visibilitychange', activity)
    return () => {
      cancelAnimationFrame(frame)
      size.disconnect()
      visibility.disconnect()
      window.removeEventListener('pointermove', move)
      document.removeEventListener('visibilitychange', activity)
      context.clearRect(0, 0, width, height)
      canvas.dataset.motionState = 'paused'
    }
  }, [enabled])
  return <canvas ref={ref} className="particle-field" aria-hidden="true" />
}

export function PageMotion() {
  const { enabled } = useContext(MotionContext)
  const { pathname } = useLocation()
  useEffect(() => {
    const root = document.documentElement
    try {
      root.dataset.privateName = localStorage.getItem('astra.privateName') ?? 'false'
    } catch {
      /* Keep session preference. */
    }
    root.dataset.motionPage = pathname === '/login' ? 'login' : 'workspace'
    if (!enabled) return
    let frame = 0,
      cursorX = 0,
      cursorY = 0
    function paint() {
      frame = 0
      const range = Math.max(0, root.scrollHeight - innerHeight)
      root.style.setProperty('--scroll-ratio', range ? String(Math.min(1, scrollY / range)) : '0')
      root.style.setProperty('--scroll-offset', Math.min(scrollY, 700) + 'px')
      root.style.setProperty('--cursor-x', String(cursorX))
      root.style.setProperty('--cursor-y', String(cursorY))
      root.dataset.reading = range > 80 ? 'true' : 'false'
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(paint)
    }
    function move(event: PointerEvent) {
      const target =
        event.target instanceof Element
          ? event.target.closest('.login-intro, .course-heading')
          : null
      const rect = target?.getBoundingClientRect()
      const x = rect ? (event.clientX - rect.left) / rect.width - 0.5 : 0
      const y = rect ? (event.clientY - rect.top) / rect.height - 0.5 : 0
      if (x === cursorX && y === cursorY) return
      cursorX = x
      cursorY = y
      schedule()
    }
    const revealed = new WeakSet<Element>()
    const visibility = new IntersectionObserver(
      (entries) => {
        for (const entry of entries)
          if (entry.isIntersecting) {
            entry.target.classList.add('motion-arrived')
            visibility.unobserve(entry.target)
          }
      },
      { threshold: 0.06 },
    )
    const selector = '.main-content .panel, .main-content .management-panel, .course-section'
    function observe(element: Element) {
      const candidates = [...element.querySelectorAll(selector)]
      if (element.matches(selector)) candidates.push(element)
      for (const candidate of candidates)
        if (!revealed.has(candidate)) {
          revealed.add(candidate)
          visibility.observe(candidate)
        }
    }
    const content = new MutationObserver((records) => {
      for (const record of records) {
        if (record.target instanceof Element && record.target.closest('.cm-editor')) continue
        for (const node of record.addedNodes) if (node instanceof Element) observe(node)
      }
    })
    content.observe(document.getElementById('root')!, { childList: true, subtree: true })
    const size = new ResizeObserver(schedule)
    size.observe(document.body)
    observe(document.getElementById('root')!)
    paint()
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      visibility.disconnect()
      content.disconnect()
      size.disconnect()
      window.removeEventListener('pointermove', move)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      for (const key of ['--scroll-ratio', '--scroll-offset', '--cursor-x', '--cursor-y'])
        root.style.removeProperty(key)
      delete root.dataset.reading
      document
        .querySelectorAll('.motion-arrived')
        .forEach((element) => element.classList.remove('motion-arrived'))
    }
  }, [enabled, pathname])
  return (
    <div className="reading-progress" aria-hidden="true">
      <span />
    </div>
  )
}
