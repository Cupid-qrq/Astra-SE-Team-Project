import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'

/** Animate the mounted surface without keeping old account content or remounting forms. */
export function RouteSurface({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  useLayoutEffect(() => {
    const root = document.documentElement
    let animation: Animation | undefined
    const stop = () => {
      if (root.dataset.motion !== 'on') animation?.cancel()
    }
    if (root.dataset.motion === 'on' && ref.current?.animate) {
      animation = ref.current.animate(
        [
          { opacity: 0.65, transform: 'translateY(10px)' },
          { opacity: 1, transform: 'translateY(0)' },
        ],
        { duration: 300, easing: 'cubic-bezier(.16,1,.3,1)' },
      )
    }
    const observer = new MutationObserver(stop)
    observer.observe(root, { attributes: true, attributeFilter: ['data-motion'] })
    return () => {
      animation?.cancel()
      observer.disconnect()
    }
  }, [pathname])
  return (
    <div className="route-surface" ref={ref}>
      {children}
    </div>
  )
}
