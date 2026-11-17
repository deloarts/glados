import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProfile } from '../../__tests__/profileFactory'

import type { DataImportProfile, ImportFieldSpec } from '../../types/spreadsheetImport'

const getDataImportProfile = vi.hoisted(() =>
  vi.fn<(importType: string) => Promise<DataImportProfile>>(),
)
vi.mock('../../api/getDataImportProfile', () => ({ getDataImportProfile }))

import SpreadsheetColumnNamesButton from '../SpreadsheetColumnNamesButton.vue'

const FIELDS: ImportFieldSpec<'project' | 'note'>[] = [
  { key: 'project', payloadKey: 'project_number', kind: 'text', alwaysRequired: true },
  { key: 'note', payloadKey: 'note', kind: 'text' },
]

describe('SpreadsheetColumnNamesButton', () => {
  it('lists the profile column names of each field once opened', async () => {
    setActivePinia(createPinia())
    getDataImportProfile.mockResolvedValue(
      makeProfile({ project_number: ['Project', 'Project No.'], note: [] }),
    )
    const wrapper = mountWithApp(SpreadsheetColumnNamesButton, {
      props: {
        importType: 'bought_item_demand',
        fields: FIELDS,
        labelFor: (field: ImportFieldSpec<string>) => `label-${field.key}`,
      },
      attachTo: document.body,
    })

    await wrapper.find('[data-testid="spreadsheet-column-names"]').trigger('click')
    await flushPromises()

    expect(getDataImportProfile).toHaveBeenCalledWith('bought_item_demand')
    const text = document.body.textContent ?? ''
    expect(text).toContain('label-project *')
    expect(text).toContain('Project, Project No.')
    expect(text).toContain('label-note')
    wrapper.unmount()
  })
})
