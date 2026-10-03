# Navigation and brand consistency

The founder rejected shifting sidebar items, mixed graph designs and inconsistent logos. No prior image is an authoritative specification.

## One source of navigation truth

Use one ordered registry for global destinations and one for desk-context views. Expanded desktop sidebar, collapsed rail and mobile drawer derive from the same global entries, labels, IDs and permissions. Theme changes must not change the list, order or active route. Do not add a destination because a screenshot has spare space.

**Proposed labels — not yet approved:**

| Scope | Ordered entries | Placement |
|---|---|---|
| Global | Home, My desks, Library | Desktop sidebar/rail; mobile drawer |
| Global utilities | Search, Settings, Profile | Stable utility group; search may additionally have a header shortcut |
| Current desk | Learn, Notes, Practice, Research, Graph | Desktop context tabs; mobile bottom context bar |
| Current desk actions | Shelf, History, Pause | Stable desk-header/actions, not a second conflicting global sidebar |

This is a single candidate in `design/navigation.proposed.json`. The founder may revise it at review; update the registry and all affected states together. No product layout is selected by providing that fixture.

“Learn” is the co-present reading/working/support surface, not a chat-only tool. The other tabs are alternate views of the same persistent desk and objects; switching does not erase work or reset context. “Notes” can focus on editing without moving the note into another data store. Global Library exposes reusable notes and saved resources with their permissions intact. Broader cross-desk graph views remain a later decision, not a duplicate global Graph button now.

## Branding

Working product name is Desk; CoLearni names the existing project/repository. No final brand name, logo, font file or icon asset is approved. Do not invent a new leaf/book/chat mark per screen.

Expanded sidebar: one chosen mark + wordmark after approval. Collapsed rail: mark only with an accessible product label; never squeeze, truncate or float the wordmark outside the rail. Mobile drawer/header use the same approved lockup. Until an asset exists, mark the design slot as pending or use an explicitly labelled text placeholder in a nonvisual technical test; do not present a newly generated logo as selected.

## Active and focus states

Active navigation uses one stable treatment for icon and label. No displaced highlight blob, rotated diamond, unexplained glow, or inconsistent padding. Keyboard focus is visually distinct from current-route selection. Mobile bottom-bar items have equal hit areas and labels, and represent only current-desk tabs. Outside a desk, hide that contextual bar; global destinations remain in the drawer/menu.

## Responsive invariants

The rail expands/collapses without changing route/order or losing editing selection. Tooltip/accessible labels remain available in icon-only mode. Mobile uses a global menu button and contextual bottom tabs. Drawer opening traps focus appropriately; closing returns to its trigger. Do not compress the entire desktop multi-column layout onto a phone or create a second desktop-style toolbar above the keyboard.

See MOBILE_INTERACTION.md for typing/selection and THEME_BRIEF.md for colour. Geometry values and exact breakpoint widths are prototype decisions to test, not settled product facts.
