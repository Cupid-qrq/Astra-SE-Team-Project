import { readdir, readFile } from 'node:fs/promises'
const root = new URL('../dist/', import.meta.url)
const files = await readdir(root, { recursive: true })
for (const name of files) {
  if (name.includes('mockServiceWorker')) throw new Error('Production contains a mock worker')
  if (!name.endsWith('.js') && !name.endsWith('.html')) continue
  const text = await readFile(new URL(name.replaceAll('\\', '/'), root), 'utf8')
  if (/demo_student|ExamplePass123|MOCK_NOT_IMPLEMENTED|mockServiceWorker/.test(text))
    throw new Error('Production contains development fixtures')
}
console.log('Production output excludes the mock worker and demo fixtures.')
