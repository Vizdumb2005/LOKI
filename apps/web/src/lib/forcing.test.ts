import { describe, expect, it } from "vitest";
import { orderWithSalient, salientOf } from "./forcing";

const options = [
  { id: "red", label: "Red" },
  { id: "black", label: "Black" },
  { id: "green", label: "Green" },
];

describe("orderWithSalient", () => {
  it("moves the salient option first and preserves the rest", () => {
    const ordered = orderWithSalient(options, "green");
    expect(ordered.map((o) => o.id)).toEqual(["green", "red", "black"]);
  });

  it("leaves the list untouched when the first option is already salient", () => {
    expect(orderWithSalient(options, "red").map((o) => o.id)).toEqual([
      "red",
      "black",
      "green",
    ]);
  });

  it("is a no-op without a salient id or an unknown id", () => {
    expect(orderWithSalient(options, null)).toBe(options);
    expect(orderWithSalient(options, "purple")).toBe(options);
  });

  it("never drops or duplicates options", () => {
    const ordered = orderWithSalient(options, "black");
    expect(ordered).toHaveLength(3);
    expect(new Set(ordered.map((o) => o.id))).toEqual(new Set(options.map((o) => o.id)));
  });
});

describe("salientOf", () => {
  it("finds the salient option and tolerates unknown ids", () => {
    expect(salientOf(options, "black")?.id).toBe("black");
    expect(salientOf(options, "purple")).toBeNull();
    expect(salientOf(options, null)).toBeNull();
  });
});
