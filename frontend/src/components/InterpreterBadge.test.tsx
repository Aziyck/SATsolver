import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithApp } from "../test/render";
import { InterpreterBadge } from "./InterpreterBadge";

describe("InterpreterBadge", () => {
  it("marks a job whose solvers ran on PyPy", () => {
    renderWithApp(<InterpreterBadge interpreter="pypy" />);
    expect(screen.getByText("PyPy")).toBeTruthy();
  });

  it("shows nothing for a job on Python or a job that runs no solver", () => {
    for (const interpreter of ["python", null] as const) {
      const { unmount } = renderWithApp(<InterpreterBadge interpreter={interpreter} />);
      expect(screen.queryByText("PyPy")).toBeNull();
      expect(screen.queryByText("Python")).toBeNull(); // the default carries no mark
      unmount();
    }
  });
});
