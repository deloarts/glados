import { describe, it, expect } from 'vitest'

import {
  demandRowNumberColumnDef,
  demandIdColumnDef,
  demandPriorityColumnDef,
  demandDesiredDeliveryColumnDef,
  demandCreatedColumnDef,
} from '../demandColumnDefs'

describe('demandColumnDefs', () => {
  it('demandRowNumberColumnDef returns the shared "#" column shape', () => {
    expect(demandRowNumberColumnDef()).toEqual({
      frozen: true,
      header: '#',
      headerStyle: 'width: 3rem',
      bodyClass: 'row-number',
    })
  })

  it('demandIdColumnDef uses the given header and width', () => {
    expect(demandIdColumnDef('ID', '5rem')).toEqual({
      header: 'ID',
      field: 'id',
      style: 'width: 5rem',
      showFilterMenu: false,
    })
  })

  it('demandPriorityColumnDef fixes the field and width, no filter menu', () => {
    expect(demandPriorityColumnDef('Priority')).toEqual({
      field: 'high_priority',
      header: 'Priority',
      style: 'width: 6rem',
      showFilterMenu: false,
    })
  })

  it('demandDesiredDeliveryColumnDef fixes the field and width, no filter menu', () => {
    expect(demandDesiredDeliveryColumnDef('Desired delivery')).toEqual({
      field: 'desired_delivery_date',
      header: 'Desired delivery',
      style: 'width: 10rem',
      showFilterMenu: false,
    })
  })

  it('demandCreatedColumnDef fixes the field and width, no filter menu', () => {
    expect(demandCreatedColumnDef('Created')).toEqual({
      field: 'created',
      header: 'Created',
      style: 'width: 10rem',
      showFilterMenu: false,
    })
  })
})
