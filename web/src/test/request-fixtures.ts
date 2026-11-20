/** Made-up print requests for the unit tests. */

import type { Choice, PrintRequest, RequestRow } from "#lib/api/requests.ts";

export function row(fields: Partial<RequestRow> = {}): RequestRow {
  return {
    id: 41,
    title: "Wingspan insert",
    quantity: 2,
    needed_by: "2026-11-21",
    priority: "urgent",
    status: "submitted",
    requester: { id: 2, username: "sam" },
    model: "both",
    choices: [
      { name: "Blue PLA", hexes: ["0A2CA5"] },
      { name: "Hot Pink PLA Basic", hexes: ["FF69B4"] },
    ],
    created_at: "2026-11-16T15:00:00Z",
    ...fields,
  };
}

export function choice(fields: Partial<Choice> = {}): Choice {
  return {
    id: 1,
    kind: "catalog_color",
    note: "",
    name: "Hot Pink PLA Basic",
    hexes: ["FF69B4"],
    material: "PLA",
    product_id: null,
    sealed: null,
    open: null,
    catalog_color: "hot-pink",
    color_name: "Hot Pink",
    line: "PLA Basic",
    bambu_code: null,
    in_catalog: true,
    multi_color: false,
    similar: [],
    held: null,
    grams: null,
    short_g: null,
    holds: null,
    available_g: 0,
    ...fields,
  };
}

export function request(fields: Partial<PrintRequest> = {}): PrintRequest {
  return {
    id: 41,
    title: "Wingspan insert",
    notes: "The version with the egg tray.",
    quantity: 2,
    needed_by: "2026-11-21",
    priority: "normal",
    link: "https://makerworld.com/models/412877",
    status: "submitted",
    requester: { id: 2, username: "sam" },
    file: { name: "wingspan.3mf", size: 19_503_513, kind: "3mf", missing: false },
    photos: [],
    choices: [
      choice({
        kind: "product",
        name: "Blue PLA",
        hexes: ["0A2CA5"],
        id: 1,
        product_id: 7,
        sealed: 2,
        open: 1,
        available_g: 2620,
        catalog_color: null,
        color_name: null,
        line: null,
        note: "main body",
      }),
      choice({
        id: 2,
        similar: [
          {
            product_id: 9,
            name: "Magenta PLA",
            hex: "EC008C",
            material: "PLA",
            delta_e: 4,
            sealed: 1,
            open: 0,
            different_material: false,
          },
        ],
      }),
    ],
    history: [
      {
        kind: "priority_changed",
        username: "dana",
        at: "2026-11-17T15:00:00Z",
        fields: null,
        from_value: "urgent",
        to_value: "normal",
        note: null,
        automatic: false,
      },
      {
        kind: "edited",
        username: "sam",
        at: "2026-11-17T10:00:00Z",
        fields: ["notes", "needed_by"],
        from_value: null,
        to_value: null,
        note: null,
        automatic: false,
      },
      {
        kind: "submitted",
        username: "sam",
        at: "2026-11-16T15:00:00Z",
        fields: null,
        from_value: null,
        to_value: null,
        note: "From the shared folder",
        automatic: false,
      },
    ],
    created_at: "2026-11-16T15:00:00Z",
    updated_at: "2026-11-17T15:00:00Z",
    can_edit: false,
    can_change_priority: false,
    can_change_photos: false,
    can_change_holds: false,
    moves: [],
    attempt: 1,
    store_address: "https://store.example",
    ...fields,
  };
}
