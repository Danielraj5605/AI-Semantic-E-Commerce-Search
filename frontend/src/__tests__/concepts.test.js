import { describe, it, expect } from "vitest";
import { measuredConfidence, LAYER_CAKE } from "../concepts";

const CAL = {
  bins: [
    { lo: 0.25, hi: 0.5, relevant: 1, n: 10, precision: 0.1 },
    { lo: 0.5, hi: 1.0, relevant: 9, n: 10, precision: 0.9 },
  ],
};

describe("measuredConfidence", () => {
  it("reads the bin the score falls in", () => {
    expect(measuredConfidence(0.3, CAL).precision).toBe(0.1);
    expect(measuredConfidence(0.5, CAL).precision).toBe(0.9);
    expect(measuredConfidence(0.99, CAL).precision).toBe(0.9);
  });
  it("says nothing when there is nothing to say", () => {
    expect(measuredConfidence(null, CAL)).toBeNull();
    expect(measuredConfidence(0.4, null)).toBeNull();
    expect(measuredConfidence(0.1, CAL)).toBeNull();
  });
  it("states its evidence", () => {
    expect(measuredConfidence(0.7, CAL).text).toMatch(/90% of 10 labelled results/);
  });
});

describe("layer cake", () => {
  it("has eight layers, each with a stated scope", () => {
    expect(LAYER_CAKE).toHaveLength(8);
    LAYER_CAKE.forEach((l) => expect(l.here.length).toBeGreaterThan(40));
  });
});
