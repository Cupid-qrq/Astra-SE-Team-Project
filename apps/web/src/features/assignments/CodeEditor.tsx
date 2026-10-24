import { useEffect, useRef } from 'react'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { python } from '@codemirror/lang-python'
import { cpp } from '@codemirror/lang-cpp'
import { basicSetup } from 'codemirror'

export default function CodeEditor({
  value,
  language,
  onChange,
}: {
  value: string
  language: 'cpp17' | 'python3'
  onChange: (value: string) => void
}) {
  const parent = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const initial = useRef(value)
  const changed = useRef(onChange)
  useEffect(() => {
    changed.current = onChange
  }, [onChange])
  useEffect(() => {
    if (!parent.current) return
    const editor = new EditorView({
      parent: parent.current,
      state: EditorState.create({
        doc: initial.current,
        extensions: [
          basicSetup,
          language === 'python3' ? python() : cpp(),
          EditorView.lineWrapping,
          EditorView.contentAttributes.of({
            'aria-label': '代码编辑器',
            role: 'textbox',
            'aria-multiline': 'true',
          }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) changed.current(update.state.doc.toString())
          }),
          EditorView.theme({
            '&': { height: '100%', minHeight: '360px' },
            '.cm-scroller': {
              overflow: 'auto',
              fontFamily: 'Consolas, monospace',
              fontSize: '14px',
            },
            '.cm-content': { padding: '16px 0' },
          }),
        ],
      }),
    })
    view.current = editor
    return () => {
      view.current = null
      editor.destroy()
    }
  }, [language])
  useEffect(() => {
    const editor = view.current
    if (editor && editor.state.doc.toString() !== value)
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } })
  }, [value])
  return <div ref={parent} className="code-editor" />
}
