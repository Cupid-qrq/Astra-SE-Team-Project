import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect } from 'vitest'
import SwaggerParser from '@apidevtools/swagger-parser'
import Ajv from 'ajv/dist/2020'
import addFormats from 'ajv-formats'

const path = resolve('../../specs/openapi/a.openapi.json')
const load = () => JSON.parse(readFileSync(path, 'utf8'))
describe('A 模块 OpenAPI 3.1 交接契约', () => {
  it('是有效 OpenAPI 并可解析全部引用', async () => {
    const spec = await SwaggerParser.validate(load())
    expect('openapi' in spec && spec.openapi).toBe('3.1.0')
  })
  it('覆盖规范中 A 所有方法，B 路由不冒领', () => {
    const spec = load()
    const docs = readFileSync(resolve('../../docs/03-api-contract.md'), 'utf8')
    const rows = [...docs.matchAll(/^\| (GET|POST|PATCH|PUT|DELETE) (\/[^ |]+) \|/gm)]
    const isA = (method: string, url: string) => {
      if (/preflight/.test(url)) return false
      if (url.startsWith('/auth/') || url.startsWith('/admin/users')) return true
      if (
        /^\/(feedback-catalogs|hint-templates|ai-hints|review-items|recommendations|practice-problems)/.test(
          url,
        )
      )
        return true
      if (url === '/submissions/{id}/feedback') return true
      if (/^\/problem/.test(url)) return true
      if (url.startsWith('/courses')) return !url.endsWith('/archive')
      if (url.startsWith('/assignments')) return !/submissions|grades|rejudge|fairness/.test(url)
      return method === 'NONE'
    }
    const expected = rows
      .filter(([, method, url]) => isA(method, url))
      .map(([, method, url]) => `${method} ${url}`)
    for (const root of ['feedback-catalogs', 'hint-templates'])
      expected.push(`GET /${root}`, `GET /${root}/{id}/draft`)
    const actual = Object.entries(spec.paths).flatMap(([url, item]) =>
      Object.keys(item as object).map((method) => `${method.toUpperCase()} ${url}`),
    )
    expect(actual.sort()).toEqual(expected.sort())
  })
  it('每个操作有权限、统一错误、写操作 CSRF 和唯一 operationId', () => {
    const spec = load()
    const ids: string[] = []
    for (const item of Object.values(spec.paths))
      for (const [method, operation] of Object.entries(
        item as Record<string, Record<string, unknown>>,
      )) {
        expect(operation['x-roles']).toBeTruthy()
        ids.push(operation.operationId as string)
        expect((operation.responses as Record<string, unknown>)['422']).toBeTruthy()
        if (method !== 'get') expect(JSON.stringify(operation.parameters)).toContain('X-CSRF-Token')
      }
    expect(new Set(ids).size).toBe(ids.length)
  })
  it('作业允许最多 20 题，运行资源按每种语言固定', async () => {
    const spec = load()
    expect(spec.components.schemas.CreateAssignment.properties.items.maxItems).toBe(20)
    expect(spec.components.schemas.Profile.properties.memory_bytes.const).toBe(268435456)
    expect(spec.components.schemas.LanguageProfile.allOf).toHaveLength(2)
  })
  it('拒绝客户端自授角色、无效 revision 和隐藏内容注入公开题面', async () => {
    const spec = await SwaggerParser.dereference(load())
    if (!('components' in spec) || !spec.components?.schemas) throw new Error('缺少 schemas')
    const schemas = spec.components.schemas
    const ajv = new Ajv({ strict: false })
    addFormats(ajv)
    const createCourse = ajv.compile(schemas.CreateCourse as object)
    expect(createCourse({ title: '课程', role: 'ADMIN' })).toBe(false)
    expect(createCourse({ title: '课程' })).toBe(true)
    const patchCourse = ajv.compile(schemas.UpdateCourse as object)
    expect(patchCourse({ title: '课程', expected_revision: 0 })).toBe(false)
    const publicProblem = ajv.compile(schemas.PublicProblem as object)
    expect(publicProblem({ hidden_tests: ['SECRET'] })).toBe(false)
    expect(JSON.stringify(schemas.PublicProblem)).not.toMatch(
      /answer_text|reference_program|testcases|password_hash/,
    )
  })
})
