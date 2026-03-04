# LightRAG Knowledge Graph Viewer — Complete Porting Guide

> **Purpose:** This document provides everything needed to port the LightRAG WebUI's interactive knowledge graph visualization to another application. It covers architecture, technology stack, data models, rendering pipeline, user interactions, UX patterns, and reference code.

---

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Model & Types](#3-data-model--types)
4. [Data Pipeline: API → Graph Rendering](#4-data-pipeline-api--graph-rendering)
5. [Graph Rendering Configuration](#5-graph-rendering-configuration)
6. [Layout Algorithms](#6-layout-algorithms)
7. [Node & Edge Visual Reducers](#7-node--edge-visual-reducers)
8. [User Interactions & UX](#8-user-interactions--ux)
9. [Properties Panel & Entity Editing](#9-properties-panel--entity-editing)
10. [Search System](#10-search-system)
11. [State Management](#11-state-management)
12. [API Endpoints](#12-api-endpoints)
13. [Component Hierarchy](#13-component-hierarchy)
14. [Constants & Theming](#14-constants--theming)
15. [Key Algorithms Reference](#15-key-algorithms-reference)
16. [Porting Checklist](#16-porting-checklist)

---

## 1. Technology Stack

| Layer | Library | Version | Purpose |
|-------|---------|---------|---------|
| **Graph data structure** | `graphology` | ^0.26.0 | In-memory graph data model (nodes, edges, attributes) |
| **Graph rendering** | `sigma` (Sigma.js v3) | ^3.0.2 | WebGL-based graph renderer |
| **React bindings** | `@react-sigma/core` | ^5.0.6 | React wrapper for Sigma.js |
| **Layout algorithms** | `@react-sigma/layout-forceatlas2`, `layout-force`, `layout-circular`, `layout-circlepack`, `layout-noverlap`, `layout-random` | ^5.0.6 | Multiple layout strategies |
| **Edge rendering** | `@sigma/edge-curve` | ^3.1.0 | Curved edge programs |
| **Node rendering** | `@sigma/node-border` | ^3.0.0 | Node border rendering |
| **Full-text search** | `minisearch` | ^7.2.0 | Client-side fuzzy search for node/edge labels |
| **State management** | `zustand` | ^5.0.11 | Lightweight store with selectors |
| **UI framework** | React 19 + TypeScript | ^19.2.4 | Component framework |
| **UI components** | Radix UI primitives | various | Dialogs, popovers, tooltips, checkboxes |
| **Styling** | Tailwind CSS v4 | ^4.2.0 | Utility-first CSS |
| **HTTP client** | `axios` | ^1.13.5 | API communication |
| **RNG** | `seedrandom` | ^3.0.5 | Deterministic random node positions |
| **Test data** | `graphology-generators`, `@faker-js/faker` | — | Random graph generation for dev mode |

### NPM Install Command (core graph dependencies only)
```bash
npm install graphology sigma @react-sigma/core \
  @react-sigma/layout-forceatlas2 @react-sigma/layout-force \
  @react-sigma/layout-circular @react-sigma/layout-circlepack \
  @react-sigma/layout-noverlap @react-sigma/layout-random \
  @sigma/edge-curve @sigma/node-border \
  minisearch seedrandom zustand
```

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GraphViewer.tsx                           │
│  (Main container - initializes SigmaContainer, theme, layout)   │
├──────────────────┬──────────────────────────────────────────────┤
│                  │                                              │
│  GraphControl    │  SigmaContainer (WebGL Canvas)               │
│  ├─ Events       │  ├─ Node rendering (NodeBorderProgram)       │
│  ├─ Reducers     │  ├─ Edge rendering (CurvedEdgeProgram)       │
│  └─ Layout       │  └─ Label rendering (grid-based)             │
│                  │                                              │
├──────────────────┼──────────────────────────────────────────────┤
│  Controls Panel  │  Properties Panel (right side)               │
│  ├─ GraphLabels  │  ├─ PropertiesView                          │
│  ├─ GraphSearch  │  ├─ EditablePropertyRow                     │
│  ├─ LayoutsCtrl  │  ├─ PropertyEditDialog                     │
│  ├─ ZoomControl  │  └─ MergeDialog                             │
│  ├─ FullScreen   │                                              │
│  ├─ LegendBtn    │  Legend (bottom-right popup)                 │
│  └─ Settings     │  SettingsDisplay (status bar)                │
└──────────────────┴──────────────────────────────────────────────┘

State Layer:
  ├─ graphStore (Zustand) → graph data, selection, search engine
  └─ settingsStore (Zustand, persisted) → UI toggles, query params
```

### Data Flow
```
API Response (nodes/edges JSON)
    ↓
useLightragGraph hook
    ├─ Build RawGraph (with lookup maps, degree calc, sizing)
    ├─ Create Graphology DirectedGraph (with positions, colors, weights)
    └─ Index MiniSearch (for search)
    ↓
Zustand Store (rawGraph + sigmaGraph)
    ↓
SigmaContainer → WebGL Rendering
    ↓
GraphControl → Visual Reducers (hover/select highlighting)
```

---

## 3. Data Model & Types

### API Response Types

```typescript
// What the backend returns
type LightragGraphType = {
  nodes: LightragNodeType[]
  edges: LightragEdgeType[]
  is_truncated?: boolean
}

type LightragNodeType = {
  id: string                           // Unique node identifier
  labels: string[]                     // Entity type categories
  properties: Record<string, any>      // e.g. { entity_id, entity_type, description, source_id }
}

type LightragEdgeType = {
  id: string
  source: string                       // Source node ID
  target: string                       // Target node ID
  type: string                         // Relationship type label
  properties: Record<string, any>      // e.g. { keywords, weight, description, source_id }
}
```

### Internal Graph Types (after transformation)

```typescript
// Enriched node type for internal use
type RawNodeType = {
  id: string
  labels: string[]
  properties: Record<string, any>

  // Added during transformation:
  size: number          // Calculated from node degree (sqrt scaling)
  x: number             // Seeded random position [0, 1]
  y: number             // Seeded random position [0, 1]
  color: string         // Resolved from entity_type → color map
  degree: number        // Count of connected edges
}

// Enriched edge type for internal use
type RawEdgeType = {
  id: string
  source: string
  target: string
  type?: string
  properties: Record<string, any>

  // Added during transformation:
  dynamicId: string     // Sigma.js internal edge ID (assigned by graphology)
}

// Graph wrapper with O(1) lookups
class RawGraph {
  nodes: RawNodeType[] = []
  edges: RawEdgeType[] = []
  nodeIdMap: Record<string, number> = {}       // node.id → array index
  edgeIdMap: Record<string, number> = {}       // edge.id → array index
  edgeDynamicIdMap: Record<string, number> = {} // sigma dynamicId → array index

  getNode(nodeId: string): RawNodeType | undefined
  getEdge(edgeId: string, dynamicId?: boolean): RawEdgeType | undefined
}
```

### Sigma.js Node/Edge Attributes

```typescript
// What Sigma.js sees for each node
type SigmaNodeAttributes = {
  label: string         // Display text
  color: string         // Fill color
  size: number          // Radius
  x: number             // Position
  y: number             // Position
  borderColor: string   // Border color
  borderSize: number    // Border width (0.2)
  highlighted: boolean  // Highlight state
  labelColor?: string   // Override label color
}

// What Sigma.js sees for each edge
type SigmaEdgeAttributes = {
  label: string              // Relationship keywords
  size: number               // Thickness (weight-based)
  originalWeight: number     // Original weight for recalculation
  type: 'curvedNoArrow'      // Edge rendering program
  color?: string             // Override color
  hidden?: boolean           // Visibility toggle
  labelColor?: string        // Override label color
}
```

---

## 4. Data Pipeline: API → Graph Rendering

### Step 1: Fetch from API

```typescript
// API call
const data = await queryGraphs(label, maxDepth, maxNodes)
// Returns: { nodes: [...], edges: [...], is_truncated?: boolean }
```

### Step 2: Build RawGraph

```typescript
function buildRawGraph(data: LightragGraphType): RawGraph {
  const rawGraph = new RawGraph()

  // 1. Index nodes
  data.nodes.forEach((node, index) => {
    rawGraph.nodeIdMap[node.id] = index
    rawGraph.nodes.push({
      ...node,
      degree: 0,
      size: 0,
      x: 0,
      y: 0,
      color: resolveNodeColor(node.properties?.entity_type)
    })
  })

  // 2. Calculate degree from edges
  data.edges.forEach((edge, index) => {
    rawGraph.edgeIdMap[edge.id] = index
    const sourceIdx = rawGraph.nodeIdMap[edge.source]
    const targetIdx = rawGraph.nodeIdMap[edge.target]
    if (sourceIdx !== undefined && targetIdx !== undefined) {
      rawGraph.nodes[sourceIdx].degree += 1
      rawGraph.nodes[targetIdx].degree += 1
    }
    rawGraph.edges.push({ ...edge, dynamicId: '' })
  })

  // 3. Scale node sizes based on degree (sqrt normalization)
  let minDegree = Infinity, maxDegree = 0
  rawGraph.nodes.forEach(n => {
    minDegree = Math.min(minDegree, n.degree)
    maxDegree = Math.max(maxDegree, n.degree)
  })

  const degreeRange = maxDegree - minDegree
  const sizeScale = Constants.maxNodeSize - Constants.minNodeSize
  rawGraph.nodes.forEach(node => {
    if (degreeRange > 0) {
      node.size = Constants.minNodeSize +
        sizeScale * Math.pow((node.degree - minDegree) / degreeRange, 0.5)
    } else {
      node.size = Constants.minNodeSize
    }
  })

  return rawGraph
}
```

### Step 3: Create Sigma Graph (Graphology instance)

```typescript
function createSigmaGraph(rawGraph: RawGraph): UndirectedGraph {
  const graph = new UndirectedGraph()

  // Add nodes with seeded random positions
  for (const node of rawGraph.nodes) {
    const rng = seedrandom(node.id + Date.now())
    graph.addNode(node.id, {
      label: node.properties?.entity_id || node.id,
      color: node.color,
      size: node.size,
      x: rng(),
      y: rng(),
      borderColor: Constants.nodeBorderColor,
      borderSize: 0.2,
    })
  }

  // Add edges with weight-based sizing
  let minWeight = Infinity, maxWeight = 0
  for (const edge of rawGraph.edges) {
    const weight = edge.properties?.weight || 1
    minWeight = Math.min(minWeight, weight)
    maxWeight = Math.max(maxWeight, weight)
  }

  const weightRange = maxWeight - minWeight
  const edgeSizeScale = maxEdgeSize - minEdgeSize

  for (const edge of rawGraph.edges) {
    const weight = edge.properties?.weight || 1
    let edgeSize = minEdgeSize
    if (weightRange > 0) {
      edgeSize = minEdgeSize +
        edgeSizeScale * Math.pow((weight - minWeight) / weightRange, 0.5)
    }

    edge.dynamicId = graph.addEdge(edge.source, edge.target, {
      label: edge.properties?.keywords || '',
      size: edgeSize,
      originalWeight: weight,
      type: 'curvedNoArrow',
    })

    // Track dynamic ID for lookups
    rawGraph.edgeDynamicIdMap[edge.dynamicId] = rawGraph.edgeIdMap[edge.id]
  }

  return graph
}
```

### Step 4: Index for Search

```typescript
function indexForSearch(rawGraph: RawGraph): MiniSearch {
  const searchEngine = new MiniSearch({
    fields: ['label'],
    storeFields: ['label', 'type', 'id'],
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
    }
  })

  const documents = [
    ...rawGraph.nodes.map(n => ({
      id: `node-${n.id}`,
      label: n.properties?.entity_id || n.id,
      type: 'nodes',
      nodeId: n.id,
    })),
    // Optionally edges too
  ]

  searchEngine.addAll(documents)
  return searchEngine
}
```

---

## 5. Graph Rendering Configuration

### Sigma.js Settings

```typescript
import { EdgeArrowProgram } from 'sigma/rendering'
import { EdgeCurvedArrowProgram, createEdgeCurveProgram } from '@sigma/edge-curve'
import { NodeBorderProgram } from '@sigma/node-border'
import NodeCircleProgram from 'sigma/rendering/node.circle'
import NodePointProgram from 'sigma/rendering/node.point'

const sigmaSettings: Partial<SigmaSettings> = {
  allowInvalidContainer: true,

  // Node programs
  defaultNodeType: 'default',
  nodeProgramClasses: {
    default: NodeBorderProgram,    // Renders nodes with a border ring
    circle: NodeCircleProgram,
    point: NodePointProgram,
  },

  // Edge programs
  defaultEdgeType: 'curvedNoArrow',
  edgeProgramClasses: {
    arrow: EdgeArrowProgram,
    curvedArrow: EdgeCurvedArrowProgram,
    curvedNoArrow: createEdgeCurveProgram(),   // Curved edges, no arrowheads
  },

  // Labels
  labelGridCellSize: 60,           // Grid cell for label deconfliction
  labelRenderedSizeThreshold: 12,  // Min zoom to show labels
  labelSize: 12,
  edgeLabelSize: 8,
  renderEdgeLabels: false,         // Off by default (toggle in settings)
  enableEdgeEvents: true,          // Enable click/hover on edges

  // Theme-aware colors
  labelColor: { color: isDark ? '#e0e0e0' : '#333', attribute: 'labelColor' },
  edgeLabelColor: { color: isDark ? '#e0e0e0' : '#333', attribute: 'labelColor' },
}
```

### SigmaContainer Setup

```tsx
<SigmaContainer
  ref={sigmaRef}
  style={{ height: '100%', width: '100%' }}
  settings={sigmaSettings}
  className="bg-background"
>
  <GraphControl />
  <FocusOnNode node={selectedNode} move={moveToSelectedNode} />
  {showNodeSearchBar && <GraphSearch onFocus={onSearchFocus} onSelect={onSearchSelect} />}
  <GraphEvents />   {/* Drag events */}
  <LayoutsControl />
  <ZoomControl />
  <FullScreenControl />
  <LegendButton />
  <Settings />
  <SettingsDisplay />
  {showPropertyPanel && <PropertiesView />}
  {showLegend && <Legend />}
</SigmaContainer>
```

---

## 6. Layout Algorithms

Six layout algorithms are available, switchable at runtime with animated transitions. They fall into two categories:

### 6.1 Layout Categories

**Static layouts** — compute positions instantly, no continuous animation:

| Layout | Package | Hook | Description |
|--------|---------|------|-------------|
| **Circular** | `@react-sigma/layout-circular` | `useLayoutCircular` | Nodes arranged on a circle |
| **Circlepack** | `@react-sigma/layout-circlepack` | `useLayoutCirclepack` | Nested circles by group |
| **Random** | `@react-sigma/layout-random` | `useLayoutRandom` | Random positions (baseline/reset) |

**Iterative layouts** — run physics simulations, support continuous play/pause animation via Web Workers:

| Layout | Package | Layout Hook | Worker Hook | Description |
|--------|---------|-------------|-------------|-------------|
| **No-overlap** | `@react-sigma/layout-noverlap` | `useLayoutNoverlap` | `useWorkerLayoutNoverlap` | Removes node overlaps |
| **Force Directed** | `@react-sigma/layout-force` | `useLayoutForce` | `useWorkerLayoutForce` | Spring-electric model |
| **Force Atlas** | `@react-sigma/layout-forceatlas2` | `useLayoutForceAtlas2` | `useWorkerLayoutForceAtlas2` | Physics-based force-directed (default on load) |

> **Key distinction:** Only the 3 iterative layouts have both a `layout` hook (for computing positions synchronously) and a `worker` hook (for background continuous simulation). Static layouts only have a `layout` hook. The play/pause animation button is **only shown** for layouts that have a worker.

### 6.2 Layout Parameter Configuration

Each layout hook is initialized with specific parameters. Getting these right is critical for good visual results.

```typescript
import { useLayoutCircular } from '@react-sigma/layout-circular'
import { useLayoutCirclepack } from '@react-sigma/layout-circlepack'
import { useLayoutRandom } from '@react-sigma/layout-random'
import { useLayoutNoverlap, useWorkerLayoutNoverlap } from '@react-sigma/layout-noverlap'
import { useLayoutForce, useWorkerLayoutForce } from '@react-sigma/layout-force'
import { useLayoutForceAtlas2, useWorkerLayoutForceAtlas2 } from '@react-sigma/layout-forceatlas2'

// maxIterations is a user-configurable setting (default: 15, range: 1-30)
const maxIterations = useSettingsStore.use.graphLayoutMaxIterations()

// --- Static layouts (no parameters needed) ---
const layoutCircular = useLayoutCircular()
const layoutCirclepack = useLayoutCirclepack()
const layoutRandom = useLayoutRandom()

// --- Iterative layouts (parameters are tuned for good convergence) ---
const layoutNoverlap = useLayoutNoverlap({
  maxIterations: maxIterations,
  settings: {
    margin: 5,        // Minimum space between nodes
    expansion: 1.1,   // How much to expand on each iteration
    gridSize: 1,      // Spatial indexing grid size
    ratio: 1,         // Scaling ratio
    speed: 3,         // Movement speed per iteration
  }
})

const layoutForce = useLayoutForce({
  maxIterations: maxIterations,
  settings: {
    attraction: 0.0003,  // Low attraction to reduce oscillation
    repulsion: 0.02,     // Low repulsion to reduce oscillation
    gravity: 0.02,       // Pulls nodes toward center
    inertia: 0.4,        // Damping factor (lower = more damping)
    maxMove: 100,        // Max pixels a node moves per step (prevents jumps)
  }
})

const layoutForceAtlas2 = useLayoutForceAtlas2({
  iterations: maxIterations  // Note: 'iterations' not 'maxIterations'
})

// --- Worker hooks (for play/pause continuous animation) ---
const workerNoverlap = useWorkerLayoutNoverlap()
const workerForce = useWorkerLayoutForce()
const workerForceAtlas2 = useWorkerLayoutForceAtlas2()
```

### 6.3 Layout Registry

Layouts are stored in a registry map. Each entry has a `layout` hook (always present) and an optional `worker` hook (only for iterative layouts). The UI uses this structure to decide whether to show the play/pause button.

```typescript
type LayoutName = 'Circular' | 'Circlepack' | 'Random' | 'Noverlaps' | 'Force Directed' | 'Force Atlas'

const layouts = useMemo(() => {
  return {
    Circular: {
      layout: layoutCircular
      // No worker — static layout
    },
    Circlepack: {
      layout: layoutCirclepack
    },
    Random: {
      layout: layoutRandom
    },
    Noverlaps: {
      layout: layoutNoverlap,
      worker: workerNoverlap     // Has worker — supports play/pause
    },
    'Force Directed': {
      layout: layoutForce,
      worker: workerForce
    },
    'Force Atlas': {
      layout: layoutForceAtlas2,
      worker: workerForceAtlas2
    }
  } as { [key: string]: { layout: LayoutHook; worker?: LayoutWorkerHook } }
}, [layoutCirclepack, layoutCircular, layoutForce, layoutForceAtlas2,
    layoutNoverlap, layoutRandom, workerForce, workerNoverlap, workerForceAtlas2])
```

### 6.4 Initial Layout on Graph Load (in GraphControl)

The initial layout is applied in `GraphControl.tsx`, **not** in `LayoutsControl.tsx`. This runs ForceAtlas2 synchronously once when the graph first loads:

```typescript
// In GraphControl.tsx
const { assign: assignLayout } = useLayoutForceAtlas2({
  iterations: maxIterations  // Default: 15, configurable 1-30
})

useEffect(() => {
  if (sigmaGraph && sigma) {
    try {
      if (typeof sigma.setGraph === 'function') {
        sigma.setGraph(sigmaGraph as unknown as AbstractGraph<NodeType, EdgeType>)
      } else {
        (sigma as any).graph = sigmaGraph
      }
    } catch (error) {
      console.error('Error setting graph on sigma instance:', error)
    }

    assignLayout()  // ForceAtlas2 applied synchronously on first load
  }
}, [sigma, sigmaGraph, assignLayout, maxIterations])
```

### 6.5 Layout Switching with Animation (in LayoutsControl)

When the user selects a layout from the dropdown, positions are computed from the layout hook and nodes are animated to their new positions:

```typescript
const runLayout = useCallback((newLayout: LayoutName) => {
  const { positions } = layouts[newLayout].layout

  try {
    const graph = sigma.getGraph()
    if (!graph) return

    const pos = positions()
    animateNodes(graph, pos, { duration: 400 })  // 400ms smooth transition
    setLayout(newLayout)
  } catch (error) {
    console.error('Error running layout:', error)
  }
}, [layouts, sigma])
```

### 6.6 Play/Pause Continuous Animation (WorkerLayoutControl)

For the 3 iterative layouts, a `WorkerLayoutControl` component provides play/pause. **Critical:** it uses `mainLayout.positions()` (the synchronous layout hook) to compute positions, not the worker directly. The worker hook is only used for its `kill()`/`stop()` methods.

```typescript
interface ExtendedWorkerLayoutControlProps extends WorkerLayoutControlProps {
  mainLayout: LayoutHook  // The synchronous layout hook, used for position computation
}

const WorkerLayoutControl = ({ layout, mainLayout }: ExtendedWorkerLayoutControlProps) => {
  const sigma = useSigma()
  const [isRunning, setIsRunning] = useState(false)
  const animationTimerRef = useRef<number | null>(null)

  // Compute positions using the main (synchronous) layout hook, then animate
  const updatePositions = useCallback(() => {
    if (!sigma) return
    const graph = sigma.getGraph()
    if (!graph || graph.order === 0) return

    const positions = mainLayout.positions()         // <-- Uses mainLayout, NOT worker
    animateNodes(graph, positions, { duration: 300 }) // 300ms per frame
  }, [sigma, mainLayout])

  const handleClick = useCallback(() => {
    if (isRunning) {
      // --- STOP ---
      if (animationTimerRef.current) {
        window.clearInterval(animationTimerRef.current)
        animationTimerRef.current = null
      }
      // Kill the worker layout
      try {
        if (typeof layout.kill === 'function') layout.kill()
        else if (typeof layout.stop === 'function') layout.stop()
      } catch (error) { /* ignore */ }
      setIsRunning(false)
    } else {
      // --- START ---
      updatePositions()  // Immediate first frame

      // Continuous updates every 200ms
      animationTimerRef.current = window.setInterval(updatePositions, 200)
      setIsRunning(true)

      // Auto-stop after 3 seconds
      setTimeout(() => {
        if (animationTimerRef.current) {
          window.clearInterval(animationTimerRef.current)
          animationTimerRef.current = null
          setIsRunning(false)
          try {
            if (typeof layout.kill === 'function') layout.kill()
            else if (typeof layout.stop === 'function') layout.stop()
          } catch (error) { /* ignore */ }
        }
      }, 3000)
    }
  }, [isRunning, layout, updatePositions])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationTimerRef.current) {
        window.clearInterval(animationTimerRef.current)
        animationTimerRef.current = null
      }
    }
  }, [])

  return (
    <Button size="icon" onClick={handleClick}>
      {isRunning ? <PauseIcon /> : <PlayIcon />}
    </Button>
  )
}
```

### 6.7 Conditional Play/Pause in the UI

The play/pause button only renders when the currently selected layout has a `worker` property:

```typescript
// In LayoutsControl render
<div>
  {/* Play/pause button — only shown for iterative layouts */}
  {layouts[layout] && 'worker' in layouts[layout] && (
    <WorkerLayoutControl
      layout={layouts[layout].worker!}      // Worker hook (for kill/stop)
      mainLayout={layouts[layout].layout}   // Layout hook (for positions)
    />
  )}
</div>

<div>
  {/* Layout dropdown — always shown */}
  <Popover>
    <PopoverTrigger>
      <Button><GripIcon /></Button>
    </PopoverTrigger>
    <PopoverContent>
      <Command>
        <CommandList>
          <CommandGroup>
            {Object.keys(layouts).map((name) => (
              <CommandItem onSelect={() => runLayout(name as LayoutName)} key={name}>
                {name}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
</div>
```

### 6.8 Porting Pitfalls

| Pitfall | Explanation |
|---------|-------------|
| **Missing Force parameters** | Without the tuned `attraction`, `repulsion`, `gravity`, `inertia`, and `maxMove` settings for Force Directed, nodes will oscillate wildly or fly off-screen |
| **Using worker for positions** | The worker hook does NOT provide `positions()` — you must pass the synchronous layout hook as `mainLayout` and call `mainLayout.positions()` |
| **No play/pause for static layouts** | Circular, Circlepack, and Random are instant — showing a play/pause button for them will error |
| **Missing auto-stop** | Without the 3-second auto-stop timeout, the animation runs forever and can drain CPU |
| **Wrong initial layout location** | ForceAtlas2 initial layout runs in `GraphControl` on graph load, NOT in `LayoutsControl` — if you put it in the wrong component, it may not fire or may fire too late |
| **Noverlap `iterations` vs `maxIterations`** | ForceAtlas2 uses `iterations` param; Noverlap and Force use `maxIterations` — mixing them up causes silent failures |

---

## 7. Node & Edge Visual Reducers

Reducers dynamically modify node/edge appearance based on interaction state. They run on every frame for every node/edge.

### Node Reducer

```typescript
nodeReducer: (node: string, data: NodeAttributes) => {
  const graph = sigma.getGraph()
  if (!graph.hasNode(node)) return { ...data, highlighted: false }

  const result = { ...data, highlighted: false, labelColor }
  const activeNode = focusedNode || selectedNode
  const activeEdge = focusedEdge || selectedEdge

  // Case 1: A node is focused/selected
  if (activeNode && graph.hasNode(activeNode)) {
    const isActiveOrNeighbor =
      node === activeNode || graph.neighbors(activeNode).includes(node)

    if (isActiveOrNeighbor) {
      result.highlighted = true
      if (node === selectedNode) {
        result.borderColor = '#ff6600'  // Orange border for selected node
      }
    } else {
      result.color = '#e0e0e0'  // Gray out non-neighbor nodes
    }
  }

  // Case 2: An edge is focused/selected
  else if (activeEdge && graph.hasEdge(activeEdge)) {
    if (graph.extremities(activeEdge).includes(node)) {
      result.highlighted = true
      result.size = 3  // Enlarge endpoint nodes
    }
  }

  // Dark theme: brighten highlighted node labels
  if (result.highlighted && isDarkTheme) {
    result.labelColor = '#ffffff'
  }

  return result
}
```

### Edge Reducer

```typescript
edgeReducer: (edge: string, data: EdgeAttributes) => {
  const graph = sigma.getGraph()
  if (!graph.hasEdge(edge)) return { ...data, hidden: false }

  const result = { ...data, hidden: false, color: defaultEdgeColor }
  const activeNode = focusedNode || selectedNode
  const highlightColor = isDarkTheme ? '#88ccff' : '#4488cc'

  // Case 1: A node is active → highlight its edges
  if (activeNode && graph.hasNode(activeNode)) {
    const isConnected = graph.extremities(edge).includes(activeNode)

    if (hideUnselectedEdges) {
      result.hidden = !isConnected  // Hide unconnected edges
    } else if (isConnected) {
      result.color = highlightColor  // Color connected edges
    }
  }

  // Case 2: An edge is focused/selected
  else if (selectedEdge || focusedEdge) {
    if (edge === selectedEdge) {
      result.color = '#ff6600'       // Orange for selected
    } else if (edge === focusedEdge) {
      result.color = highlightColor  // Blue for hovered
    } else if (hideUnselectedEdges) {
      result.hidden = true
    }
  }

  return result
}
```

### Visual Highlight Summary

| State | Affected Node | Affected Edges | Non-affected |
|-------|--------------|----------------|--------------|
| **Hover node** | Highlighted + neighbors highlighted | Connected edges colored blue | Nodes grayed, edges optionally hidden |
| **Click node** | Orange border + neighbors highlighted | Connected edges colored blue | Nodes grayed, edges optionally hidden |
| **Hover edge** | Both endpoints highlighted (size 3) | Edge colored blue | Others unchanged |
| **Click edge** | Both endpoints highlighted | Edge colored orange | Others optionally hidden |
| **No selection** | Normal colors | Normal colors | — |

---

## 8. User Interactions & UX

### 8.1 Node Drag

```typescript
// In GraphViewer.tsx → GraphEvents component
registerEvents({
  downNode: (e) => {
    setDraggedNode(e.node)
    graph.setNodeAttribute(e.node, 'highlighted', true)
  },
  mousemovebody: (e) => {
    if (draggedNode) {
      // Convert viewport coordinates to graph coordinates
      const pos = sigma.viewportToGraph(e)
      graph.setNodeAttribute(draggedNode, 'x', pos.x)
      graph.setNodeAttribute(draggedNode, 'y', pos.y)
      e.preventSigmaDefault()  // Prevent camera pan
    }
  },
  mouseup: () => {
    if (draggedNode) {
      graph.removeNodeAttribute(draggedNode, 'highlighted')
      setDraggedNode(null)
    }
  },
  mousedown: () => {
    // Lock bounding box during drag to prevent camera drift
    if (!sigma.getCustomBBox()) {
      sigma.setCustomBBox(sigma.getBBox())
    }
  }
})
```

### 8.2 Click Events

| Event | Target | Action |
|-------|--------|--------|
| `clickNode` | Node | Set `selectedNode`, open properties panel |
| `clickEdge` | Edge | Set `selectedEdge`, open properties panel |
| `clickStage` | Background | Clear all selection, close properties |
| `enterNode` | Node hover | Set `focusedNode`, trigger reducer |
| `leaveNode` | Node unhover | Clear `focusedNode` |
| `enterEdge` | Edge hover | Set `focusedEdge`, trigger reducer |
| `leaveEdge` | Edge unhover | Clear `focusedEdge` |

### 8.3 Camera Controls

```typescript
// Zoom: 1.5x factor, 200ms animation
zoomIn({ factor: 1.5, duration: 200 })
zoomOut({ factor: 1.5, duration: 200 })

// Reset view: center camera, 1000ms animation
sigma.setCustomBBox(null)
camera.animate({ x: 0.5, y: 0.5, ratio: 1.1 }, { duration: 1000 })

// Rotate: π/8 radians (22.5°), 200ms animation
camera.animate({ angle: currentAngle ± Math.PI / 8 }, { duration: 200 })

// Focus on node: animated camera move to node position
const gotoNode = (nodeId: string) => {
  const pos = sigma.getNodeDisplayData(nodeId)
  camera.animate({ x: pos.x, y: pos.y, ratio: 0.3 }, { duration: 500 })
}
```

### 8.4 Node Expansion (subgraph exploration)

```typescript
// Triggered from properties panel "expand" button
// 1. Fetch extended subgraph
const expanded = await queryGraphs(nodeId, depth=2, maxNodes=1000)

// 2. Calculate positions around parent (polar coordinates)
const angle = (2 * Math.PI * nodeIndex) / totalNewNodes
const spreadFactor = Math.sqrt(nodeSize) * 4 / cameraRatio
const x = parentX + Math.cos(randomAngle + angle) * spreadFactor
const y = parentY + Math.sin(randomAngle + angle) * spreadFactor

// 3. Merge into existing graph (add new, skip duplicates)
// 4. Recalculate sizes for entire graph
// 5. Update both rawGraph and sigmaGraph
```

### 8.5 Node Pruning (deletion)

```typescript
// Triggered from properties panel "prune" button
// 1. Find nodes that would become isolated after deletion
// 2. Validate: don't delete all remaining nodes
// 3. Cascade delete: node + all connected edges from both graphs
// 4. Update index maps
// 5. Clear selection, close properties panel
```

### 8.6 Search

```typescript
// MiniSearch with prefix + fuzzy matching
const searchEngine = new MiniSearch({
  fields: ['label'],
  searchOptions: { prefix: true, fuzzy: 0.2 }
})

// Two-tier search:
// 1. Prefix/fuzzy match via MiniSearch
// 2. Fallback: substring match if <5 results
// Max 50 results displayed

// On select: focus camera + select node
// On hover (focus): highlight node temporarily
```

---

## 9. Properties Panel & Entity Editing

### Properties Display

When a node is selected, the panel shows:
```
┌─────────────────────────────┐
│  Entity: "Barack Obama"      │  [Expand] [Prune]
├─────────────────────────────┤
│  ID:          node_123       │
│  Labels:      Person         │
│  Degree:      12             │
├─────────────────────────────┤
│  Properties:                 │
│  entity_id:   Barack Obama ✏│  ← Editable
│  entity_type: PERSON       ✏│  ← Editable
│  description: 44th Pres... ✏│  ← Editable (large textarea)
│  keywords:    president... ✏│  ← Editable
│  source_id:   doc_456        │  ← Read-only
├─────────────────────────────┤
│  Relationships:              │
│  ├─ Michelle Obama (SPOUSE)  │  ← Click to navigate
│  ├─ White House (LOCATED)    │
│  └─ Democratic Party (MEMBER)│
└─────────────────────────────┘
```

### Editable Properties
- `entity_id` — Can trigger entity merge if name matches existing entity
- `entity_type` — Entity category
- `description` — Long text with `<SEP>` delimiter support
- `keywords` — Comma-separated tags

### Edit Dialog

```typescript
// Textarea size adapts to property type
const textareaConfig = {
  description: { rows: 'auto', maxHeight: '70vh', minHeight: '20em' },
  entity_id:   { rows: 2 },
  keywords:    { rows: 4 },
  default:     { rows: 5 }
}
```

### Entity Merge Workflow

```
1. User edits entity_id to match an existing entity name
2. System checks: checkEntityNameExists(newName)
3. If exists AND allowMerge=true:
   a. API call: updateEntity(id, {entity_name: newName}, allowMerge=true)
   b. Backend merges entities
   c. Response: { operation_summary: { merged: true, final_entity: "..." } }
   d. MergeDialog appears: "Entity X merged into Entity Y"
   e. User chooses: "Keep Current View" or "Navigate to Merged Entity"
   f. Graph re-fetches with updated data
4. If exists AND allowMerge=false:
   → Error: "Duplicate entity name"
```

### API Calls for Editing

```typescript
// Update entity properties
POST /graph/entity/edit
Body: {
  entity_name: string,
  updated_data: Record<string, any>,
  allow_rename: boolean,
  allow_merge: boolean
}
Response: {
  status: string,
  operation_summary: {
    operation_status: 'success' | 'partial_success' | 'failure',
    merged: boolean,
    final_entity: string | null,
    merge_error: string | null
  }
}

// Update relation properties
POST /graph/relation/edit
Body: {
  source_id: string,
  target_id: string,
  updated_data: Record<string, any>
}

// Check entity existence
GET /graph/entity/exists?name={name}
Response: { exists: boolean }
```

---

## 10. Search System

### Architecture

```typescript
// Built on MiniSearch for client-side full-text search
// Indexed when graph data loads

const searchOptions = {
  prefix: true,        // "Bar" matches "Barack"
  fuzzy: 0.2,          // Typo tolerance
  maxResults: 50       // Cap results
}

// Two-tier search strategy:
async function searchNodes(query: string): Promise<SearchResult[]> {
  // Tier 1: MiniSearch prefix + fuzzy
  let results = searchEngine.search(query, searchOptions)

  // Tier 2: Fallback to substring match if <5 results
  if (results.length < 5) {
    const additionalResults = allNodes.filter(
      n => n.label.toLowerCase().includes(query.toLowerCase())
    )
    results = [...results, ...additionalResults]
  }

  return results.slice(0, 50)
}
```

### Search UX

- **Async dropdown** with debounced input (500ms)
- **Color-coded results**: Each node shows its type color as a dot
- **Node size indicator**: Dot size scales 8-16px with node importance
- **Selection behavior**: Click selects + focuses camera; hover highlights node
- **Label dropdown** (GraphLabels component): Separate selector for entity type filtering
  - Popular labels fetched from backend
  - Search history persisted
  - Re-selecting same label switches to `*` (show all)

---

## 11. State Management

### Graph Store (Zustand)

```typescript
interface GraphStore {
  // === Selection State ===
  selectedNode: string | null      // Currently selected node
  focusedNode: string | null       // Currently hovered node
  selectedEdge: string | null      // Currently selected edge
  focusedEdge: string | null       // Currently hovered edge
  moveToSelectedNode: boolean      // Camera should animate to selected node

  // === Graph Data ===
  rawGraph: RawGraph | null        // Transformed API data with lookup maps
  sigmaGraph: DirectedGraph | null // Graphology instance for rendering
  sigmaInstance: any               // Sigma.js renderer reference

  // === UI State ===
  isFetching: boolean              // Loading indicator
  graphIsEmpty: boolean            // Show empty state
  graphDataVersion: number         // Increment to force re-fetch

  // === Search ===
  searchEngine: MiniSearch | null  // Full-text search index
  typeColorMap: Map<string, string>// Entity type → color mapping

  // === Operations ===
  nodeToExpand: string | null      // Trigger node expansion
  nodeToPrune: string | null       // Trigger node deletion
  graphDataFetchAttempted: boolean // Prevent duplicate fetches

  // === Actions ===
  setSelectedNode(id: string | null, moveCamera?: boolean): void
  setFocusedNode(id: string | null): void
  setSelectedEdge(id: string | null): void
  clearSelection(): void
  setSigmaGraph(graph: DirectedGraph): void
  setRawGraph(graph: RawGraph): void
  incrementGraphDataVersion(): void
  updateNodeAndSelect(nodeId, entityId, propName, value): void
  updateEdgeAndSelect(edgeId, dynamicId, srcId, tgtId, propName, value): void
  triggerNodeExpand(nodeId: string): void
  triggerNodePrune(nodeId: string): void
}
```

### Settings Store (Zustand + localStorage persistence)

```typescript
interface SettingsStore {
  // === Display Toggles ===
  showPropertyPanel: boolean       // Default: true
  showNodeSearchBar: boolean       // Default: true
  showNodeLabel: boolean           // Default: true
  showEdgeLabel: boolean           // Default: false
  showLegend: boolean              // Default: false
  enableEdgeEvents: boolean        // Default: true

  // === Interaction ===
  enableNodeDrag: boolean          // Default: true
  enableHideUnselectedEdges: boolean // Default: true

  // === Edge Sizing ===
  minEdgeSize: number              // Default: 1
  maxEdgeSize: number              // Default: 1 (range 1-10)

  // === Graph Query Parameters ===
  graphQueryMaxDepth: number       // Default: 3
  graphMaxNodes: number            // Default: 1000
  backendMaxGraphNodes: number | null
  graphLayoutMaxIterations: number // Default: 15 (range 1-30)

  // === Query Label ===
  queryLabel: string               // Current entity type filter
  setQueryLabel(label: string): void
  setGraphMaxNodes(n: number, triggerRefresh?: boolean): void

  // === Health Check ===
  enableHealthCheck: boolean       // Default: true

  // === Theme ===
  theme: 'light' | 'dark' | 'system'
}
```

### State Persistence

```typescript
// Settings store persisted to localStorage with version key
persist(stateCreator, {
  name: 'lightrag-settings',
  version: 19,  // Increment on schema changes
  partialize: (state) => ({
    // Only persist user preferences, not transient state
    showPropertyPanel: state.showPropertyPanel,
    enableNodeDrag: state.enableNodeDrag,
    graphQueryMaxDepth: state.graphQueryMaxDepth,
    // ... etc
  })
})
```

---

## 12. API Endpoints

### Graph Data Endpoints

| Endpoint | Method | Purpose | Params |
|----------|--------|---------|--------|
| `GET /graphs` | GET | **Primary graph fetch** | `label`, `max_depth`, `max_nodes` |
| `GET /graph/label/list` | GET | All entity type labels | — |
| `GET /graph/label/popular` | GET | Popular labels | `limit` |
| `GET /graph/label/search` | GET | Search labels | `q`, `limit` |
| `GET /graph/entity/exists` | GET | Check entity exists | `name` |
| `POST /graph/entity/edit` | POST | Update entity | `entity_name`, `updated_data`, `allow_rename`, `allow_merge` |
| `POST /graph/relation/edit` | POST | Update relation | `source_id`, `target_id`, `updated_data` |

### Query Endpoints (for RAG retrieval, not graph-specific)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /query` | POST | Synchronous query |
| `POST /query/stream` | POST | Streaming query (NDJSON) |

### System Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /health` | GET | Health check + pipeline status |
| `GET /auth-status` | GET | Auth mode + guest token |
| `POST /login` | POST | User login |

---

## 13. Component Hierarchy

```
GraphViewer (features/GraphViewer.tsx)
│
├── SigmaContainer (@react-sigma/core)
│   │
│   ├── GraphControl (graph/GraphControl.tsx)
│   │   ├── Event registration (click, hover, enter/leave)
│   │   ├── Node reducer (highlighting logic)
│   │   ├── Edge reducer (highlighting logic)
│   │   ├── ForceAtlas2 layout initialization
│   │   └── Edge sizing calculation
│   │
│   ├── GraphEvents (inline in GraphViewer.tsx)
│   │   └── Node drag handlers (down, move, up)
│   │
│   ├── FocusOnNode (graph/FocusOnNode.tsx)
│   │   └── Camera animation to selected node
│   │
│   ├── GraphSearch (graph/GraphSearch.tsx)
│   │   └── AsyncSelect with MiniSearch backend
│   │
│   ├── GraphLabels (graph/GraphLabels.tsx)
│   │   └── Entity type filter dropdown + refresh
│   │
│   ├── LayoutsControl (graph/LayoutsControl.tsx)
│   │   └── Layout switcher with play/pause animation
│   │
│   ├── ZoomControl (graph/ZoomControl.tsx)
│   │   └── Zoom in/out, reset, rotate buttons
│   │
│   ├── FullScreenControl (graph/FullScreenControl.tsx)
│   │   └── Toggle fullscreen mode
│   │
│   ├── LegendButton (graph/LegendButton.tsx)
│   │   └── Toggle legend visibility
│   │
│   ├── Settings (graph/Settings.tsx)
│   │   └── Popover with all configurable options
│   │
│   ├── SettingsDisplay (graph/SettingsDisplay.tsx)
│   │   └── Status bar: depth & max nodes
│   │
│   ├── PropertiesView (graph/PropertiesView.tsx)
│   │   ├── Node/Edge property display
│   │   ├── Relationship navigation
│   │   ├── Expand/Prune actions
│   │   └── EditablePropertyRow (graph/EditablePropertyRow.tsx)
│   │       ├── PropertyEditDialog (graph/PropertyEditDialog.tsx)
│   │       └── MergeDialog (graph/MergeDialog.tsx)
│   │
│   └── Legend (graph/Legend.tsx)
│       └── Color-coded entity type reference
│
└── Hooks
    ├── useLightragGraph (hooks/useLightragGraph.tsx)
    │   └── Data fetch, transform, and index pipeline
    └── useRandomGraph (hooks/useRandomGraph.tsx)
        └── Dev mode: Erdős–Rényi random graph generator
```

---

## 14. Constants & Theming

```typescript
// Node sizing
const minNodeSize = 3
const maxNodeSize = 15

// Edge sizing (user-configurable)
const defaultMinEdgeSize = 1
const defaultMaxEdgeSize = 1  // Can be set up to 10

// Node colors
const nodeBorderColor = '#ffffff'
const nodeBorderColorSelected = '#ff6600'
const nodeColorDisabled = '#e0e0e0'

// Edge colors
const edgeColorLightTheme = '#cccccc'
const edgeColorDarkTheme = '#555555'
const edgeColorHighlightedLightTheme = '#4488cc'
const edgeColorHighlightedDarkTheme = '#88ccff'
const edgeColorSelected = '#ff6600'

// Label colors
const labelColorLightTheme = '#333333'
const labelColorDarkTheme = '#e0e0e0'
const labelColorHighlightedDarkTheme = '#ffffff'

// Entity type → color mapping
// Colors are resolved per entity_type using a deterministic color palette
// The typeColorMap is stored in the graph store and displayed in the Legend
```

### Theme Support

The graph supports three theme modes:
- **Light**: Light backgrounds, dark text, muted edge colors
- **Dark**: Dark backgrounds, light text, bright edge highlights
- **System**: Follows OS preference via `prefers-color-scheme` media query

Theme switching is debounced (150ms) to prevent WebGL rendering artifacts.

---

## 15. Key Algorithms Reference

### A. Node Size from Degree (sqrt normalization)

```
nodeSize = minNodeSize + (maxNodeSize - minNodeSize) × √((degree - minDegree) / (maxDegree - minDegree))
```

Rationale: Square root prevents high-degree nodes from dominating the visualization.

### B. Edge Size from Weight (sqrt normalization)

```
edgeSize = minEdgeSize + (maxEdgeSize - minEdgeSize) × √((weight - minWeight) / (maxWeight - minWeight))
```

### C. Node Expansion Position Calculation

```
angle = 2π × (nodeIndex / totalNewNodes)
spreadFactor = √(parentNodeSize) × 4 / cameraRatio
x = parentX + cos(randomOffset + angle) × spreadFactor
y = parentY + sin(randomOffset + angle) × spreadFactor
```

### D. Neighbor Highlighting

```
highlighted = (node === focusedNode) OR (node ∈ graph.neighbors(focusedNode))
```

### E. Edge Connection Test

```
isConnected = focusedNode ∈ graph.extremities(edge)
```

---

## 16. Porting Checklist

### Phase 1: Core Graph Rendering
- [ ] Install graphology, sigma, @react-sigma/core, @sigma/edge-curve, @sigma/node-border
- [ ] Create graph data model (nodes/edges with attributes)
- [ ] Set up SigmaContainer with node/edge programs
- [ ] Implement data transform pipeline (API → RawGraph → Graphology)
- [ ] Apply ForceAtlas2 layout on graph load
- [ ] Implement node/edge reducers for dynamic styling

### Phase 2: Basic Interactions
- [ ] Node click → select + show properties
- [ ] Node hover → highlight + neighbors
- [ ] Edge click → select + show properties
- [ ] Edge hover → highlight + endpoints
- [ ] Background click → clear selection
- [ ] Node drag to reposition
- [ ] Camera: zoom, pan, reset, rotate

### Phase 3: Search & Navigation
- [ ] Index nodes with MiniSearch
- [ ] Search dropdown with fuzzy matching
- [ ] Focus camera on selected search result
- [ ] Entity label filter dropdown
- [ ] Focus-on-node with camera animation

### Phase 4: Properties Panel
- [ ] Display node properties (ID, labels, degree, custom props)
- [ ] Display edge properties
- [ ] Show relationships with click-to-navigate
- [ ] Edit dialog for text properties
- [ ] Entity merge workflow (if applicable)

### Phase 5: Layout Controls
- [ ] Layout switcher (6 algorithms)
- [ ] Animated transitions between layouts
- [ ] Play/pause for continuous layout
- [ ] Auto-stop after 3 seconds

### Phase 6: Polish
- [ ] Legend (entity type → color)
- [ ] Settings panel (toggles for all features)
- [ ] Dark/light/system theme support
- [ ] Fullscreen toggle
- [ ] Node expand/prune (subgraph exploration)
- [ ] Status bar (depth, max nodes)
- [ ] Persisted settings (localStorage)

---

## Source Files Reference

| File | Purpose |
|------|---------|
| `lightrag_webui/src/features/GraphViewer.tsx` | Main graph page container |
| `lightrag_webui/src/components/graph/GraphControl.tsx` | Events, reducers, layout |
| `lightrag_webui/src/components/graph/GraphSearch.tsx` | Search with MiniSearch |
| `lightrag_webui/src/components/graph/GraphLabels.tsx` | Entity type filter |
| `lightrag_webui/src/components/graph/LayoutsControl.tsx` | Layout switching UI |
| `lightrag_webui/src/components/graph/ZoomControl.tsx` | Camera controls |
| `lightrag_webui/src/components/graph/FullScreenControl.tsx` | Fullscreen toggle |
| `lightrag_webui/src/components/graph/FocusOnNode.tsx` | Camera focus animation |
| `lightrag_webui/src/components/graph/PropertiesView.tsx` | Properties display |
| `lightrag_webui/src/components/graph/EditablePropertyRow.tsx` | Property editing |
| `lightrag_webui/src/components/graph/PropertyEditDialog.tsx` | Edit modal |
| `lightrag_webui/src/components/graph/MergeDialog.tsx` | Entity merge confirmation |
| `lightrag_webui/src/components/graph/Settings.tsx` | Settings popover |
| `lightrag_webui/src/components/graph/SettingsDisplay.tsx` | Status bar |
| `lightrag_webui/src/components/graph/Legend.tsx` | Color legend |
| `lightrag_webui/src/components/graph/LegendButton.tsx` | Legend toggle |
| `lightrag_webui/src/hooks/useLightragGraph.tsx` | Data pipeline hook |
| `lightrag_webui/src/hooks/useRandomGraph.tsx` | Dev random graph |
| `lightrag_webui/src/stores/graph.ts` | Graph state (Zustand) |
| `lightrag_webui/src/stores/settings.ts` | Settings state (persisted) |
| `lightrag_webui/src/api/lightrag.ts` | API client |
