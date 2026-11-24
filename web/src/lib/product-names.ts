/** Product names: the default name a product is given when first seen on a tag or in the
 * AMS, and the catalog name it takes when linked. The server has its own copy of these
 * rules; each side's tests pin the same examples. */

/** Whether a name is still the product's default name: it ends with " #" and the first six
 * hex digits of its color, in any case. A typed name that ends that way counts too. */
export function isDefaultName(name: string, colorRgba: string): boolean {
  const suffix = ` #${colorRgba.slice(0, 6)}`.toLowerCase();
  return name.toLowerCase().endsWith(suffix);
}

/** The longest a product's name can be, as on the server. */
export const NAME_LENGTH = 100;

/** "Hot Pink PLA Basic": the color's name, then its filament line's, cut to NAME_LENGTH. */
export function catalogName(color: string, line: string): string {
  return `${color} ${line}`.slice(0, NAME_LENGTH);
}
