import { readFile, writeFile } from 'node:fs/promises'
import openapiTS, { astToString } from 'openapi-typescript'

const source = JSON.parse(
  await readFile(new URL('../../../specs/openapi/a.openapi.json', import.meta.url), 'utf8'),
)
const destination = new URL('../src/lib/api/schema.d.ts', import.meta.url)
const output = astToString(await openapiTS(source))
if (process.argv.includes('--check')) {
  if ((await readFile(destination, 'utf8')) !== output)
    throw new Error('API 类型已漂移，请运行 pnpm contracts:generate 并检查差异')
  console.log('API generated types match the contract.')
} else {
  await writeFile(destination, output)
}
