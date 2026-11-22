# The shopping list is worked out live, not stored

Each shopping list item's need is worked out from its reasons every time the list is read: low stock (`threshold − sealed + 1` spools while the product is low), the shortfalls of the print requests holding filament on it, and spools added by hand. Nothing removes a reason. When its cause goes (a request is cancelled, rejected, done or fully held, or a product stops being low), the reason stops existing and the need falls with it. The archived spec's `shopping_item` table (`docs/archive/SPEC-v1.md`, 2.6), with a stored quantity, a source and an `open`, `ordered`, `received` or `dismissed` status, is replaced by these live reasons. Only what people did is stored: on order, dismissals, hand-added reasons, suggestions and the shopping list history. This was settled when #78 was specified, so that a reason disappears by itself when its cause does and nobody cleans the list up by hand (#78, user stories 7 and 8).

## Consequences

- A product with no reasons left and nothing on order leaves the list by itself.
- Reading the list does the arithmetic each time: the low-stock counts, the requests' shortfalls and the net weights. Its cost grows with the number of products and holding requests.
- Need is never stored, so it has no history. The shopping list history records only what people did, with the resulting on-order count.
- Inventory asks Print Requests for the requests' shortfalls through a hook (ADR-0020), so the request reasons are only as current as the holds they are worked out from.
