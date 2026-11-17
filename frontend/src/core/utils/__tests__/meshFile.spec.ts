import { describe, expect, it } from 'vitest'

import { MESH_ACCEPT, isMeshFile } from '../meshFile'

describe('isMeshFile', () => {
  it('recognises both formats the mesh slot accepts', () => {
    expect(isMeshFile('part.stl', 'model/stl')).toBe(true)
    expect(isMeshFile('part.3mf', 'model/3mf')).toBe(true)
  })

  it('matches the extension case-insensitively', () => {
    expect(isMeshFile('PART.STL', '')).toBe(true)
    expect(isMeshFile('PART.3MF', '')).toBe(true)
  })

  it('recognises a mesh whose mime the browser did not set', () => {
    // The common case for rows uploaded before the backend pinned a
    // canonical mime, the filename is all there is to go on.
    expect(isMeshFile('part.3mf', 'application/octet-stream')).toBe(true)
    expect(isMeshFile('part.stl', '')).toBe(true)
    expect(isMeshFile('part.stl', null)).toBe(true)
  })

  it('recognises the legacy mime spellings even without a useful name', () => {
    expect(isMeshFile('download', 'application/sla')).toBe(true)
    expect(isMeshFile('download', 'application/vnd.ms-package.3dmanufacturing-3dmodel+xml')).toBe(
      true,
    )
  })

  it('rejects everything else', () => {
    expect(isMeshFile('drawing.pdf', 'application/pdf')).toBe(false)
    expect(isMeshFile('photo.png', 'image/png')).toBe(false)
    expect(isMeshFile('model.step', 'application/octet-stream')).toBe(false)
    // .3mf must be the extension, not merely somewhere in the name.
    expect(isMeshFile('part.3mf.zip', 'application/zip')).toBe(false)
  })

  it('offers both extensions to the file picker', () => {
    expect(MESH_ACCEPT).toBe('.stl,.3mf')
  })
})
