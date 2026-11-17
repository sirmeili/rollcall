import { describe, expect, it } from "vitest";
import { unapproved } from "./audit-policy.js";

const advisory = (id: string, severity: string) => ({
  title: "an advisory",
  severity,
  url: `https://github.com/advisories/${id}`,
});

describe("unapproved", () => {
  it("passes a clean report", () => {
    expect(unapproved({})).toEqual([]);
    expect(unapproved({ vulnerabilities: {} })).toEqual([]);
  });

  it("passes the approved exception at its severity, and packages that only depend on it", () => {
    const report = {
      vulnerabilities: {
        deepmerge: { via: [advisory("GHSA-gcqx-w48m-w2h4", "low")] },
        "@sveltejs/kit": { via: ["deepmerge", null] },
      },
    };
    expect(unapproved(report)).toEqual([]);
  });

  it("fails the exception if its severity is raised", () => {
    const report = {
      vulnerabilities: { deepmerge: { via: [advisory("GHSA-gcqx-w48m-w2h4", "high")] } },
    };
    expect(unapproved(report)).toHaveLength(1);
  });

  it("passes picomatch's ReDoS advisory at high, and fails it if raised to critical", () => {
    const at = (severity: string) => ({
      vulnerabilities: {
        picomatch: { via: [advisory("GHSA-fc5q-39xc-vjpf", severity)] },
        vite: { via: ["picomatch"] },
      },
    });
    expect(unapproved(at("high"))).toEqual([]);
    expect(unapproved(at("critical"))).toHaveLength(1);
  });

  it("fails any other advisory, even a low one", () => {
    const report = {
      vulnerabilities: { other: { via: [advisory("GHSA-xxxx-yyyy-zzzz", "low")] } },
    };
    expect(unapproved(report)[0]).toContain("other: an advisory (low)");
  });

  it("treats an advisory with missing fields as critical", () => {
    expect(unapproved({ vulnerabilities: { odd: { via: [{}] } } })).toHaveLength(1);
  });
});
