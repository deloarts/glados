/**
 * Shape placeholder image and mesh for a source item without files of its
 * own. A custom or empty dimension gets none. Static imports let Vite bundle
 * the assets; the .3mf files need ?url since Vite does not know the
 * extension.
 */
import blockImage from '@/assets/placeholder/block.png'
import blockMesh from '@/assets/placeholder/block.3mf?url'
import profileImage from '@/assets/placeholder/profile.png'
import profileMesh from '@/assets/placeholder/profile.3mf?url'
import tubeImage from '@/assets/placeholder/tube.png'
import tubeMesh from '@/assets/placeholder/tube.3mf?url'
import turnedImage from '@/assets/placeholder/turned.png'
import turnedMesh from '@/assets/placeholder/turned.3mf?url'

import { detectDimensionShape, type DimensionShape } from './dimensionSpec'

export { detectDimensionShape }

export interface SourceItemPlaceholderFiles {
  image: string
  mesh: string
}

const PLACEHOLDERS: Record<DimensionShape, SourceItemPlaceholderFiles> = {
  box: { image: blockImage, mesh: blockMesh },
  'hollow-box': { image: profileImage, mesh: profileMesh },
  rod: { image: turnedImage, mesh: turnedMesh },
  'hollow-rod': { image: tubeImage, mesh: tubeMesh },
}

export function sourceItemPlaceholder(
  dimension: string | null | undefined,
): SourceItemPlaceholderFiles | null {
  const shape = detectDimensionShape(dimension)
  return shape ? PLACEHOLDERS[shape] : null
}
