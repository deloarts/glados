import { getProducts, legalBasisFor } from '@/features/products'
import type { ProductResponse } from '@/features/products'
import { getProjects } from '@/features/projects'
import { useUsersStore } from '@/core/stores/usersStore'
import type { ChecklistOwner } from '../types/checklist'
import type { ChecklistHeader } from '../utils/types'
import type { HeaderOwnerField } from '../utils/state'

export type OwnerData = Pick<ChecklistHeader, HeaderOwnerField | 'legalBasis'>

type MachineData = Pick<
  OwnerData,
  'designation' | 'machineType' | 'placingOnMarket' | 'installationSite' | 'installationLocation' | 'legalBasis'
>

/** The header fields of an owner without a product: empty, with the legal basis that applies today. */
export function noOwnerData(): OwnerData {
  return {
    ownerNumber: '',
    ownerCustomer: '',
    ownerProduct: '',
    ownerManager: '',
    ...machineDataOf(null),
  }
}

/** The machine data of a product as the header keeps it; without a product every field is empty. */
function machineDataOf(product: ProductResponse | null): MachineData {
  const placing = product?.planned_placing_on_market ?? ''
  return {
    designation: product?.designation ?? '',
    machineType: product?.machine_type ?? '',
    placingOnMarket: placing,
    installationSite: product?.installation_site ?? '',
    installationLocation: product?.installation_location ?? '',
    legalBasis: product?.legal_basis ?? legalBasisFor(placing),
  }
}

/**
 * Reads what the header shows about a checklist's owner: its number, its
 * customer, the product of a project, the designated user, and the machine
 * data of the product, which is the owner itself or the project's product.
 * A personal checklist has none of these.
 */
export function useOwnerData() {
  const usersStore = useUsersStore()

  async function managerName(userId: number | null | undefined): Promise<string> {
    if (!userId) return ''
    await usersStore.ensureLoaded()
    return usersStore.getById(userId)?.full_name ?? ''
  }

  async function product(id: number | null | undefined): Promise<ProductResponse | null> {
    if (!id) return null
    return (await getProducts({ id, limit: 1 })).items[0] ?? null
  }

  async function load(owner: ChecklistOwner): Promise<OwnerData> {
    if (owner.kind === 'project') {
      const project = (await getProjects({ id: owner.id, limit: 1 })).items[0]
      if (!project) return { ...noOwnerData(), ownerNumber: owner.label }
      return {
        ownerNumber: project.project_number,
        ownerCustomer: project.customer?.name ?? '',
        ownerProduct: project.product?.product_number ?? '',
        ownerManager: await managerName(project.designated_user_id),
        ...machineDataOf(await product(project.product?.id)),
      }
    }
    if (owner.kind === 'product') {
      const found = await product(owner.id)
      if (!found) return { ...noOwnerData(), ownerNumber: owner.label }
      return {
        ownerNumber: found.product_number,
        ownerCustomer: found.customer?.name ?? '',
        ownerProduct: '',
        ownerManager: await managerName(found.designated_user_id),
        ...machineDataOf(found),
      }
    }
    return noOwnerData()
  }

  return { load }
}
