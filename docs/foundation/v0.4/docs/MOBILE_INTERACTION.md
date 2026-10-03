# Mobile writing, navigation and graph interaction

## Accepted behaviour

Global destinations move into a menu/sidebar drawer. The bottom navigation area represents views of the current desk. Their labels/order derive from the same desk-tab registry as desktop. Collapsed desktop branding uses only the selected mark, not a squeezed wordmark. Active icon/label highlighting is aligned and consistent.

## Notes, worksheets and annotations

Mobile writing should resemble normal phone text editing. Default view has no always-visible desktop Markdown toolbar. Long-press/select a passage, preserve the system selection handles and clipboard actions, and offer relevant formatting contextually. Plain writing requires no Markdown knowledge. Rich responses and worked-example annotations use the same interaction foundation.

**Implementation caveat:** a browser's selection API exposes selection state; it is not a portable guarantee that an app can add arbitrary commands to every native iOS/Android edit menu. Test the chosen editor on actual target browser/device combinations. Use a compact app-controlled selection panel or bottom sheet where needed, without claiming it is a native phone menu. [U1]

Provide an explicit, accessible Format/Insert action as an alternative to long-press. It may be secondary or contextual, but must work for keyboard, assistive technology and non-gesture users. Table, equation, heading and code insertion cannot depend exclusively on a text selection. No hidden-only slash-command requirement.

## Editing focus and keyboard

Keep the caret/selection visible when the software keyboard opens. Do not overlay bottom tabs, tutor messages or toast notifications on the editor. A proposed behaviour is to hide/compact the desk-context bar while the keyboard is open and restore it when editing ends; verify before final selection. Preserve drafts and scroll/selection on tab switches, autosave, reconnect and undo. Do not impose a timed long-press gesture that prevents ordinary text selection.

Mobile test matrix includes iOS Safari and Android Chrome, software keyboard, orientation changes, IME, hardware keyboard, selection/clipboard, screen-reader use and zoom. Desktop emulation alone cannot establish native mobile-menu behaviour.

## Tutor behaviour

Saving/typing does not solicit critique. Shared saved content enters the next relevant teaching context under the same privacy rules as desktop. An explicit Check my explanation action targets a selected revision and places feedback outside learner text. Do not automatically select, pan or replace the note after a tutor action.

## Graph

Carry the same concept/relationship semantics and hierarchy as desktop. Offer a focused labelled view and list/tree alternative. Node selection shows readable details in an accessible sheet/panel without depending on hover. Preserve a deliberate route back to the learning surface. Do not replace labelled rectangular nodes with decorative unlabeled circles merely to fit a phone.

## Accessibility targets

For prototype design, aim for comfortably sized controls (for example 44 CSS pixels where practical); this is our design target, not a blanket claim about WCAG's minimum. WCAG 2.2 target-size and spacing requirements have specific exceptions and need actual checks. Text contrast, visible focus and non-colour labels are separate requirements. [U2, U3]

## Required separate visual reviews

Mobile main desk; global drawer open; active note selection with keyboard/context formatting; worksheet response; graph/list view; then their relevant dark-mode variants. Each is produced and reviewed separately. No all-in-one phone collage.
