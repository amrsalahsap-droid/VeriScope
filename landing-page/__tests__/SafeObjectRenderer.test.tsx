/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SafeObjectRenderer } from "../components/readiness/SafeObjectRenderer";

describe("SafeObjectRenderer plain object breakdown rendering", () => {
  it("renders plain object { functional: 18 } as a key/value row", () => {
    render(<SafeObjectRenderer value={{ functional: 18 }} />);
    expect(screen.getByText("Functional:")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.queryByText(/properties/)).not.toBeInTheDocument();
  });

  it("renders plain object { manual_junit_upload: 18 } with formatted key", () => {
    render(<SafeObjectRenderer value={{ manual_junit_upload: 18 }} />);
    expect(screen.getByText("manual JUnit upload:")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
  });

  it("renders complex nested object with view debug details toggle and no raw [object Object]", () => {
    const complexObject = {
      nested: {
        field: "val",
      },
    };
    render(
      <SafeObjectRenderer
        value={complexObject}
        onToggleDebug={() => {}}
      />
    );
    expect(screen.getByText(/Complex object/)).toBeInTheDocument();
    expect(screen.getByText("View debug details")).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });
});

describe("SafeObjectRenderer debug mode breakdown rendering", () => {
  it("renders mapping_source_breakdown as readable key/value rows", () => {
    render(
      <SafeObjectRenderer
        value={{ junit_external_ac_ref: 25 }}
        showDebug={true}
      />
    );
    expect(screen.getByText("Junit external ac ref:")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.queryByText(/^Object/)).not.toBeInTheDocument();
  });

  it("renders review_status_breakdown as readable key/value rows", () => {
    render(
      <SafeObjectRenderer
        value={{ system_suggested: 13, needs_review: 12 }}
        showDebug={true}
      />
    );
    expect(screen.getByText("System suggested:")).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();
    expect(screen.getByText("Needs review:")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.queryByText(/^Object/)).not.toBeInTheDocument();
  });

  it("renders confidence_breakdown as readable key/value rows", () => {
    render(
      <SafeObjectRenderer
        value={{ high: 0, medium: 25, low: 0 }}
        showDebug={true}
      />
    );
    expect(screen.getByText("High:")).toBeInTheDocument();
    expect(screen.getByText("Medium:")).toBeInTheDocument();
    expect(screen.getByText("Low:")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.queryByText(/^Object/)).not.toBeInTheDocument();
  });

  it("renders nested objects recursively as rows, not raw JSON", () => {
    render(
      <SafeObjectRenderer
        value={{ parent: { child_key: "child_value" } }}
        showDebug={true}
      />
    );
    expect(screen.getByText("Parent:")).toBeInTheDocument();
    expect(screen.getByText("Child key:")).toBeInTheDocument();
    expect(screen.getByText("Child value")).toBeInTheDocument();
    expect(screen.queryByText(/^Object/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });

  it("never shows 'Object { ... }' or '[object Object]' in any mode", () => {
    const { container } = render(
      <SafeObjectRenderer
        value={{ a: { b: 1 }, c: [1, 2], d: "hello" }}
        showDebug={true}
      />
    );
    const text = container.textContent || "";
    expect(text).not.toMatch(/Object \{/);
    expect(text).not.toMatch(/\[object Object\]/);
  });

  it("keeps large array content scrollable", () => {
    const bigArray = Array.from({ length: 50 }, (_, i) => ({ idx: i, value: `item-${i}` }));
    const { container } = render(
      <SafeObjectRenderer value={bigArray} showDebug={true} />
    );
    const scrollable = container.querySelector(".overflow-y-auto");
    expect(scrollable).toBeInTheDocument();
  });
});
