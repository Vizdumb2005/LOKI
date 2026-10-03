import { describe, expect, it } from "vitest";
import { matchTranscript, targetsFromOptions, tokenize } from "./matcher";

const TARGETS = targetsFromOptions([
  { id: "red", label: "Red", voice: ["red"] },
  { id: "black", label: "Black", voice: ["black"] },
  {
    id: "rface",
    label: "Jack, Queen or King",
    voice: ["jack", "queen", "king", "face", "picture"],
  },
  { id: "r10", label: "Ten", voice: ["ten", "10"] },
]);

describe("tokenize", () => {
  it("lowercases, strips punctuation, and drops empties", () => {
    expect(tokenize("The Red card!")).toEqual(["the", "red", "card"]);
  });
});

describe("matchTranscript", () => {
  it("matches a spoken label", () => {
    expect(matchTranscript("black", TARGETS)).toEqual({ status: "matched", answerId: "black" });
  });

  it("matches inside a longer sentence", () => {
    expect(matchTranscript("um i think it is the ten of course", TARGETS)).toEqual({
      status: "matched",
      answerId: "r10",
    });
  });

  it("matches number words", () => {
    expect(matchTranscript("ten", TARGETS)).toEqual({ status: "matched", answerId: "r10" });
  });

  it("flags ambiguity instead of guessing", () => {
    const result = matchTranscript("red or black", TARGETS);
    expect(result).toEqual({ status: "ambiguous", candidates: ["black", "red"] });
  });

  it("reports no match for silence of meaning", () => {
    expect(matchTranscript("hello there", TARGETS)).toEqual({ status: "no_match" });
    expect(matchTranscript("", TARGETS)).toEqual({ status: "no_match" });
  });
});
