import { spawnSync } from 'node:child_process'
import path from 'node:path'

export default async function cleanupFormalBrowser() {
  const python = process.env.ASTRA_SERVER_PYTHON
  if (!python) throw new Error('Formal browser Python is required for cleanup.')
  const result = spawnSync(
    python,
    [path.resolve('../../server/tests/shared/web_harness.py'), '--cleanup'],
    {
      stdio: 'inherit',
      windowsHide: true,
      env: process.env,
    },
  )
  if (result.error || result.status !== 0) throw new Error('Formal browser schema cleanup failed.')
}
