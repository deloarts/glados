// Layout for StateMachineDiagram. The graphs are tiny, so it stays simple:
// BFS layers by depth from the initial state, then every terminal state moves
// into the last layer so the diagram reads left to right from start to done.

export interface StateMachineLayoutState {
  value: string
  // Only picks the BFS root.
  initial?: boolean | null
  terminal?: boolean
}

export interface StateMachineLayoutEdge {
  from_state: string
  to_state: string
}

export interface StateMachineLayout {
  /** States grouped by layer (BFS depth from the root), left-to-right; each layer lists its states top-to-bottom in input order. */
  layers: string[][]
  /** Quick lookup from a state's value to the layer index it landed in. */
  layerOf: Record<string, number>
}

export function layoutStateMachine(
  states: StateMachineLayoutState[],
  edges: StateMachineLayoutEdge[],
): StateMachineLayout {
  if (states.length === 0) return { layers: [], layerOf: {} }

  const root = states.find((s) => s.initial === true)?.value ?? states[0]!.value

  const adjacency = new Map<string, string[]>()
  for (const s of states) adjacency.set(s.value, [])
  for (const e of edges) {
    if (!adjacency.has(e.from_state)) adjacency.set(e.from_state, [])
    adjacency.get(e.from_state)!.push(e.to_state)
  }

  // Marking depth before enqueueing keeps cycles from revisiting a node.
  const depth = new Map<string, number>()
  depth.set(root, 0)
  const queue: string[] = [root]
  while (queue.length > 0) {
    const current = queue.shift()!
    const currentDepth = depth.get(current)!
    for (const next of adjacency.get(current) ?? []) {
      if (depth.has(next)) continue
      depth.set(next, currentDepth + 1)
      queue.push(next)
    }
  }

  // An unreached state still gets a deterministic slot.
  let maxReachedDepth = Math.max(0, ...depth.values())
  for (const s of states) {
    if (!depth.has(s.value)) {
      maxReachedDepth += 1
      depth.set(s.value, maxReachedDepth)
    }
  }

  // Pull every terminal state into the single last layer, overriding
  // whatever (possibly much shallower) depth BFS found for it.
  const overallMaxDepth = Math.max(0, ...depth.values())
  for (const s of states) {
    if (s.terminal) depth.set(s.value, overallMaxDepth)
  }

  const layerCount = Math.max(0, ...depth.values()) + 1
  const layers: string[][] = Array.from({ length: layerCount }, () => [])
  for (const s of states) {
    layers[depth.get(s.value)!]!.push(s.value)
  }

  const layerOf: Record<string, number> = {}
  for (const s of states) layerOf[s.value] = depth.get(s.value)!

  return { layers, layerOf }
}
