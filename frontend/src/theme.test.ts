import { mergeMantineTheme, DEFAULT_THEME } from "@mantine/core";
import { describe, expect, it } from "vitest";
import { cssVariablesResolver, theme } from "./theme";

describe("cssVariablesResolver", () => {
  const full = mergeMantineTheme(DEFAULT_THEME, theme);
  const vars = cssVariablesResolver(full);

  it("makes the light variant stronger in the dark scheme only", () => {
    // blue-5 is #339af0. Mantine's own dark value (primaryShade.dark = 4) is blue-2 at 0.15.
    expect(vars.dark["--mantine-color-blue-light"]).toBe("rgba(51, 154, 240, 0.24)");
    expect(vars.dark["--mantine-color-blue-light-color"]).toBe(full.colors.blue[2]);
    expect(vars.light).toEqual({});
    expect(vars.variables).toEqual({});
  });

  it("covers the app's own colours and leaves the surface greys alone", () => {
    for (const name of ["wizard", "gold", "green", "orange", "gray"]) {
      expect(vars.dark[`--mantine-color-${name}-light`]).toMatch(/^rgba\(/);
    }
    expect(vars.dark["--mantine-color-dark-light"]).toBeUndefined();
  });
});
