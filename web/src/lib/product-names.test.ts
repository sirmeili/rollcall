import { describe, expect, it } from "vitest";
import { catalogName, isDefaultName } from "./product-names.ts";

// The same examples as the server's default-name tests: keep the two in step.
describe("isDefaultName", () => {
  it.each([
    ["PLA Basic #FF5C8D", "FF5C8DFF"],
    ["PLA #FFFFFF", "FFFFFFFF"],
    ["PLA Basic #ff5c8d", "FF5C8DFF"],
    ["PLA Basic #Ff5C8d", "ff5c8dff"],
    ["My own name #FF5C8D", "FF5C8DFF"],
  ])("%s with color %s is a default name", (name, color) => {
    expect(isDefaultName(name, color)).toBe(true);
  });

  it.each([
    ["Hot Pink PLA Basic", "FF5C8DFF"],
    ["PLA Basic #FF5C8E", "FF5C8DFF"],
    ["PLA Basic #FF5C8", "FF5C8DFF"],
    ["PLA Basic#FF5C8D", "FF5C8DFF"],
    ["PLA Basic #FF5C8D ", "FF5C8DFF"],
    ["PLA Basic #FF5C8DFF", "FF5C8DFF"],
    ["PLA Basic #FF5C8D (spare)", "FF5C8DFF"],
    ["#FF5C8D", "FF5C8DFF"],
  ])("%s with color %s is not a default name", (name, color) => {
    expect(isDefaultName(name, color)).toBe(false);
  });
});

describe("catalogName", () => {
  it("is the color's name, then its filament line's", () => {
    expect(catalogName("Hot Pink", "PLA Basic")).toBe("Hot Pink PLA Basic");
  });

  it("is cut to 100 characters", () => {
    const name = catalogName("A".repeat(95), "PLA Basic");
    expect(name).toBe(`${"A".repeat(95)} PLA `);
    expect(name).toHaveLength(100);
  });
});
