// The file fields MachineFileStrip needs, shared by made and source item
// files. A plain .ts file, since type exports from an SFC are fragile.
export interface MachineStripFile {
  id: number
  file_name: string
  mime_type: string
  category: string
}
