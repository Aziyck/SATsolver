import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithApp } from "../test/render";
import { InterpreterSwitch } from "./InterpreterSwitch";

const AVAILABLE = { available: true, version: "3.12.15" };
const MISSING = { available: false, version: null };

function pypyRadio(): HTMLInputElement {
  return screen.getByRole("radio", { name: /PyPy/ }) as HTMLInputElement;
}

describe("InterpreterSwitch", () => {
  it("shows Python selected and offers PyPy with its version when the server found it", () => {
    renderWithApp(<InterpreterSwitch value="python" onChange={() => {}} pypy={AVAILABLE} />);

    expect((screen.getByRole("radio", { name: "Python" }) as HTMLInputElement).checked).toBe(true);
    expect(pypyRadio().checked).toBe(false);
    expect(pypyRadio().disabled).toBe(false);
    expect(screen.getByText(/PyPy 3\.12\.15/)).toBeTruthy();
    expect(screen.queryByText(/PyPy not found/)).toBeNull();
  });

  it("reports the choice of PyPy", () => {
    const onChange = vi.fn();
    renderWithApp(<InterpreterSwitch value="python" onChange={onChange} pypy={AVAILABLE} />);

    fireEvent.click(pypyRadio());

    expect(onChange).toHaveBeenCalledWith("pypy");
  });

  it("disables PyPy and says how to install it when the server found none", () => {
    const onChange = vi.fn();
    renderWithApp(<InterpreterSwitch value="python" onChange={onChange} pypy={MISSING} />);

    expect(pypyRadio().disabled).toBe(true);
    fireEvent.click(pypyRadio());
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/PyPy not found\. Install it from pypy\.org, then add its folder to PATH or set WIZSAT_SOLVER_PYTHON, and restart the server\./)).toBeTruthy();
  });

  it("shows Python selected, not PyPy, when a PyPy choice cannot be honoured", () => {
    // A copy of a PyPy job, on a server that has no PyPy now: the form must not claim PyPy.
    renderWithApp(<InterpreterSwitch value="pypy" onChange={() => {}} pypy={MISSING} />);

    expect((screen.getByRole("radio", { name: "Python" }) as HTMLInputElement).checked).toBe(true);
    expect(pypyRadio().checked).toBe(false);
  });
});
