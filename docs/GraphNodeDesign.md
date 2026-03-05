# Graph Node Design: Circle Renderer & Info Panel

This document covers two parts of the LightRAG WebUI graph:

1. **Node Circle / Border Ring** — how the colored ring around each node is rendered and reacts to interaction
2. **Node Info Panel** — the slide-in properties panel that appears when a node is clicked

---

## Part 1: Node Circle / Border Ring

### Library Stack

| Library | Version | Role |
|---|---|---|
| **sigma.js** | 3.0.2 | WebGL graph renderer |
| **@react-sigma/core** | 5.0.6 | React bindings for sigma.js |
| **@sigma/node-border** | 3.0.0 | Custom WebGL program that draws the border ring |

---

### Step 1 — Register the Border Renderer

**File:** `lightrag_webui/src/features/GraphViewer.tsx`

```tsx
import { NodeBorderProgram } from '@sigma/node-border'
import { NodeCircleProgram } from 'sigma/rendering'

const createSigmaSettings = (isDarkTheme: boolean): Partial<SigmaSettings> => ({
  defaultNodeType: 'default',
  nodeProgramClasses: {
    default: NodeBorderProgram,   // ← every node uses this WebGL program
    circel: NodeCircleProgram,
    point: NodePointProgram
  },
  // ...
})
```

`NodeBorderProgram` replaces sigma's built-in circle program. It renders two layers in a single WebGL draw call: an inner fill (`color`) and an outer ring (`borderColor` × `borderSize`).

---

### Step 2 — Attach Border Attributes to Every Node

**File:** `lightrag_webui/src/hooks/useLightragGraph.tsx`

```tsx
graph.addNode(rawNode.id, {
  label:       rawNode.labels.join(', '),
  color:       rawNode.color,
  x, y,
  size:        rawNode.size,
  // NodeBorderProgram-specific attributes:
  borderColor: Constants.nodeBorderColor,  // '#EEEEEE' — subtle gray ring
  borderSize:  0.2                         // ring thickness as fraction of node size
})
```

Both `borderColor` and `borderSize` must be set at node creation. They are consumed directly by `NodeBorderProgram`'s WebGL shader.

---

### Step 3 — Dynamic Color via `nodeReducer`

**File:** `lightrag_webui/src/components/graph/GraphControl.tsx`

sigma.js calls `nodeReducer` before every render frame, allowing per-frame appearance overrides:

```tsx
nodeReducer: (node, data) => {
  const newData = { ...data, highlighted: false, labelColor }
  const _focusedNode = focusedNode || selectedNode

  if (_focusedNode && graph.hasNode(_focusedNode)) {
    // Highlight the focused node and all its direct neighbors
    if (node === _focusedNode || graph.neighbors(_focusedNode).includes(node)) {
      newData.highlighted = true
      if (node === selectedNode) {
        // Orange ring on the specifically selected node
        newData.borderColor = Constants.nodeBorderColorSelected  // '#F57F17'
      }
    }
  }

  if (newData.highlighted) {
    // In dark theme: invert label color for contrast
    if (isDarkTheme) newData.labelColor = Constants.LabelColorHighlightedDarkTheme
  } else {
    // Dim body color of all non-relevant nodes
    newData.color = Constants.nodeColorDisabled  // '#E2E2E2'
  }
  return newData
}
```

---

### Color Constants

**File:** `lightrag_webui/src/lib/constants.ts`

```ts
export const nodeBorderColor         = '#EEEEEE'  // default ring — light gray
export const nodeBorderColorSelected = '#F57F17'  // selected ring — amber/orange
export const nodeColorDisabled       = '#E2E2E2'  // dimmed node body
export const minNodeSize             = 4
export const maxNodeSize             = 20
```

---

### Node State Reference

| State | Ring Color | Node Body | Label Color |
|---|---|---|---|
| **Default** | `#EEEEEE` gray | full color | theme default |
| **Hovered / Neighbor** | `#EEEEEE` gray | full color | inverted (dark theme) |
| **Selected** | `#F57F17` orange | full color | inverted (dark theme) |
| **Background (faded)** | `#EEEEEE` gray | `#E2E2E2` dimmed | theme default |

---

### Rendering Pipeline

```
graph.addNode({ borderColor: '#EEEEEE', borderSize: 0.2 })
        │
        ▼
  nodeReducer() ← runs every frame
  overrides borderColor → '#F57F17' for selected node
  overrides color → '#E2E2E2' for non-highlighted nodes
        │
        ▼
  NodeBorderProgram (WebGL shader)
  draws: inner circle (color) + outer ring (borderColor × borderSize)
```

---

### Porting Checklist

To replicate this design in another framework:

1. **Install** `@sigma/node-border` (or copy its WebGL shader source)
2. **Register** `NodeBorderProgram` as `defaultNodeType`
3. **Add** `borderColor` + `borderSize` to every node at creation time
4. **Implement** a `nodeReducer` (or equivalent event listeners) that:
   - Sets `borderColor = '#F57F17'` on `selectedNode`
   - Resets others to `'#EEEEEE'`
   - Sets `color = '#E2E2E2'` on non-highlighted nodes
5. **Define** the color constants in a shared config file

---

## Part 2: Node Info Panel

### Overview

When a user **clicks a node**, a glass-morphism panel slides in at the top-right of the graph canvas. It shows three color-coded sections: basic node info, properties, and relationships.

**File:** `lightrag_webui/src/components/graph/PropertiesView.tsx`  
**Mounted in:** `lightrag_webui/src/features/GraphViewer.tsx`

---

### How the Panel is Triggered

**1. Click event → state update**

**File:** `lightrag_webui/src/components/graph/GraphControl.tsx`

```tsx
clickNode: (event: NodeEvent) => {
  const graph = sigma.getGraph()
  if (graph.hasNode(event.node)) {
    setSelectedNode(event.node)   // → updates Zustand store
    setSelectedEdge(null)
  }
}
```

**2. Panel rendered conditionally**

**File:** `lightrag_webui/src/features/GraphViewer.tsx`

```tsx
{showPropertyPanel && (
  <div className="absolute top-2 right-2 z-10">
    <PropertiesView />
  </div>
)}
```

`showPropertyPanel` is a user-controlled setting from `useSettingsStore`. The panel is positioned **fixed to top-right** of the sigma container.

---

### Data Priority & Selection Logic

`PropertiesView` reacts to four possible states (in priority order):

```tsx
useEffect(() => {
  let element: RawNodeType | RawEdgeType | null = null

  if (focusedNode) {              // 1. Hover over a node (highest priority)
    element = getNode(focusedNode)
  } else if (selectedNode) {      // 2. Clicked node
    element = getNode(selectedNode)
  } else if (focusedEdge) {       // 3. Hover over an edge
    element = getEdge(focusedEdge, true)
  } else if (selectedEdge) {      // 4. Clicked edge (lowest priority)
    element = getEdge(selectedEdge, true)
  }

  if (element) {
    setCurrentElement(type === 'node'
      ? refineNodeProperties(element)   // enriches with relationships
      : refineEdgeProperties(element)   // enriches with source/target nodes
    )
  }
}, [focusedNode, selectedNode, focusedEdge, selectedEdge, graphDataVersion, ...])
```

Data comes entirely from the **local Zustand graph store** — no API calls on click.

---

### Panel Layout & Styling

```tsx
<div className="bg-background/80 max-w-xs rounded-lg border-2 p-2 text-xs backdrop-blur-lg">
  {currentType === 'node'
    ? <NodePropertiesView node={currentElement} />
    : <EdgePropertiesView edge={currentElement} />
  }
</div>
```

| CSS Technique | Value | Effect |
|---|---|---|
| `backdrop-blur-lg` | Tailwind | Glass-morphism blur |
| `bg-background/80` | Tailwind | 80% opacity background |
| `max-w-xs` | Tailwind | Max width ~320px |
| `border-2` | Tailwind | Visible border |
| `max-h-96 overflow-auto` | Tailwind | Scrollable sections |

---

### Node Panel Sections

The `NodePropertiesView` component renders **three sections**, each with a distinct header color:

#### Section 1 — Basic Info (Blue header)

```tsx
<h3 className="... text-blue-700">Node</h3>
<div className="bg-primary/5 max-h-96 overflow-auto rounded p-1">
  <PropertyRow name="ID"     value={String(node.id)} />
  <PropertyRow name="Labels" value={node.labels.join(', ')}
    onClick={() => useGraphStore.getState().setSelectedNode(node.id, true)} />
  <PropertyRow name="Degree" value={node.degree} />
</div>
```

| Field | Source | Notes |
|---|---|---|
| **ID** | `node.id` | Internal graph node identifier |
| **Labels** | `node.labels.join(', ')` | Clickable — re-selects the node |
| **Degree** | `node.degree` | Total edge connections (see degree calculation below) |

#### Section 2 — Properties (Amber header)

```tsx
<h3 className="... text-amber-700">Properties</h3>
<div className="bg-primary/5 max-h-96 overflow-auto rounded p-1">
  {Object.keys(node.properties).sort().map((name) => {
    if (name === 'created_at' || name === 'truncate') return null  // hidden
    return (
      <PropertyRow
        key={name}
        name={name}
        value={node.properties[name]}
        isEditable={name === 'description' || name === 'entity_id' || name === 'entity_type'}
      />
    )
  })}
</div>
```

| Property | Editable | Notes |
|---|---|---|
| `entity_id` | ✅ yes | Entity name/identifier |
| `entity_type` | ✅ yes | Entity category |
| `description` | ✅ yes | Free-text description |
| `keywords` | ✅ yes | Associated keywords |
| `source_id` | ❌ no | Source document ID; shows truncation indicator `†` if truncated |
| `created_at` | — | **Hidden** from display |
| `truncate` | — | **Hidden** from display (used internally for `†` indicator) |

Properties are sorted alphabetically and rendered using `PropertyRow`. Editable fields use the `EditablePropertyRow` component which allows inline editing.

The `<SEP>` separator token in string values is formatted as `;\n` for display:

```tsx
const formatValueWithSeparators = (value: any): string => {
  if (typeof value === 'string') return value.replace(/<SEP>/g, ';\n')
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}
```

#### Section 3 — Relationships (Emerald header)

```tsx
{node.relationships.length > 0 && (
  <>
    <h3 className="... text-emerald-700">Relationships</h3>
    <div className="bg-primary/5 max-h-96 overflow-auto rounded p-1">
      {node.relationships.map(({ type, id, label }) => (
        <PropertyRow
          key={id}
          name={type}        // always "Neighbour"
          value={label}      // neighbor's entity_id or labels
          onClick={() => useGraphStore.getState().setSelectedNode(id, true)}
        />
      ))}
    </div>
  </>
)}
```

Each relationship entry is **clickable** — clicking navigates the selection to that neighbor node.

---

### Relationships Derivation

`refineNodeProperties()` builds the relationships list from the live graph:

```tsx
const refineNodeProperties = (node: RawNodeType): NodeType => {
  const { sigmaGraph, rawGraph } = useGraphStore.getState()
  const relationships = []

  const edges = sigmaGraph.edges(node.id)   // all connected edges
  for (const edgeId of edges) {
    const edge = rawGraph.getEdge(edgeId, true)
    if (edge) {
      const neighbourId = node.id === edge.source ? edge.target : edge.source
      const neighbour = rawGraph.getNode(neighbourId)
      if (neighbour) {
        relationships.push({
          type: 'Neighbour',
          id: neighbourId,
          label: neighbour.properties['entity_id'] ?? neighbour.labels.join(', ')
        })
      }
    }
  }
  return { ...node, relationships }
}
```

---

### Degree Calculation

Degree is computed once when graph data is loaded, not on-the-fly:

**File:** `lightrag_webui/src/hooks/useLightragGraph.tsx`

```tsx
// Initialize all nodes with degree 0
for (const node of rawData.nodes) {
  node.degree = 0
}

// Increment both endpoints for every edge
for (const edge of rawData.edges) {
  const sourceNode = rawData.nodes[nodeIdMap[edge.source]]
  const targetNode = rawData.nodes[nodeIdMap[edge.target]]
  sourceNode.degree += 1
  targetNode.degree += 1
}
```

`degree` is the **total number of connected edges** (undirected). It also drives **node size** — higher-degree nodes are rendered larger:

```tsx
const range = maxDegree - minDegree
const scale = Constants.maxNodeSize - Constants.minNodeSize  // 20 - 4 = 16
node.size = minNodeSize + ((node.degree - minDegree) / range) * scale
```

---

### Action Buttons

The node panel header includes two icon buttons:

| Button | Icon | Action |
|---|---|---|
| **Expand** | `GitBranchPlus` | Calls `triggerNodeExpand(node.id)` — loads deeper neighbors |
| **Prune** | `Scissors` | Calls `triggerNodePrune(node.id)` — removes peripheral nodes |

```tsx
<Button onClick={() => useGraphStore.getState().triggerNodeExpand(node.id)}
        tooltip="Expand Node">
  <GitBranchPlus className="h-4 w-4" />
</Button>
<Button onClick={() => useGraphStore.getState().triggerNodePrune(node.id)}
        tooltip="Prune Node">
  <Scissors className="h-4 w-4" />
</Button>
```

---

### Data Flow Summary

```
User clicks node on canvas
        │
        ▼
clickNode event (GraphControl.tsx)
setSelectedNode(nodeId) → Zustand store
        │
        ▼
PropertiesView useEffect fires
getNode(selectedNode) ← rawGraph store (no API call)
        │
        ▼
refineNodeProperties()
  sigmaGraph.edges(node.id) → collect neighbor nodes
        │
        ▼
NodePropertiesView renders:
  ┌─────────────────────────────┐
  │ [Blue]   Node               │
  │   ID · Labels · Degree      │
  ├─────────────────────────────┤
  │ [Amber]  Properties         │
  │   entity_id · entity_type   │
  │   description · keywords    │
  │   source_id · ...           │
  ├─────────────────────────────┤
  │ [Emerald] Relationships     │
  │   Neighbour → Node A        │
  │   Neighbour → Node B        │
  └─────────────────────────────┘
```

---

## File Reference

| File | Role |
|---|---|
| `lightrag_webui/src/features/GraphViewer.tsx` | SigmaContainer setup; mounts PropertiesView top-right |
| `lightrag_webui/src/components/graph/GraphControl.tsx` | `clickNode` handler; `nodeReducer` for circle colors |
| `lightrag_webui/src/components/graph/PropertiesView.tsx` | Info panel: NodePropertiesView + EdgePropertiesView |
| `lightrag_webui/src/components/graph/EditablePropertyRow.tsx` | Inline-editable property fields |
| `lightrag_webui/src/hooks/useLightragGraph.tsx` | Graph data loading; degree + size calculation |
| `lightrag_webui/src/lib/constants.ts` | All color values and size limits |
| `lightrag_webui/src/stores/graph.ts` | Zustand store: selectedNode, focusedNode, rawGraph, sigmaGraph |
