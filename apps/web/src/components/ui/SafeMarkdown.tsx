import Markdown from 'react-markdown'

const allowed = [
  'p',
  'br',
  'strong',
  'em',
  'del',
  'code',
  'pre',
  'blockquote',
  'ul',
  'ol',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'hr',
]
export function SafeMarkdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <Markdown skipHtml allowedElements={allowed} unwrapDisallowed={false}>
        {children}
      </Markdown>
    </div>
  )
}
