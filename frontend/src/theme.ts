import { createTheme, rgba, type CSSVariablesResolver, type MantineColorsTuple } from "@mantine/core";

// Colours taken from the WizSAT logo: the hat's violet and the star's gold.
const wizard: MantineColorsTuple = [
  "#f3f0fc",
  "#e3dcf7",
  "#c4b5ee",
  "#a38ce5",
  "#876add",
  "#7453d8",
  "#6a47d6",
  "#5a39bd",
  "#4f32a9",
  "#432895",
];

const gold: MantineColorsTuple = [
  "#fff8e1",
  "#ffefc0",
  "#fde08a",
  "#fbd05a",
  "#f9c233",
  "#f8ba1d",
  "#f8b50c",
  "#dd9f00",
  "#c48c00",
  "#a97800",
];

export const theme = createTheme({
  primaryColor: "wizard",
  primaryShade: { light: 6, dark: 4 },
  colors: { wizard, gold },
  defaultRadius: "md",
  fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  fontFamilyMonospace: 'ui-monospace, "SFMono-Regular", "Cascadia Code", Menlo, Consolas, monospace',
  headings: { fontWeight: "650" },
  cursorType: "pointer",
  components: {
    Card: { defaultProps: { withBorder: true, radius: "lg", padding: "lg" } },
    Paper: { defaultProps: { radius: "lg" } },
    Tooltip: { defaultProps: { withArrow: true, openDelay: 250, multiline: true, maw: 320 } },
    Badge: { defaultProps: { radius: "sm" } },
  },
});

/**
 * The "light" variant (status badges, tags, light buttons) in the dark scheme.
 * With primaryShade.dark = 4, Mantine 8 paints it as pastel shade 2 at 15%
 * opacity with near-white shade 0 text, which reads as grey on a dark card.
 * Here: shade 5 at 24%, text shade 2. Shade 2 keeps every colour's text at
 * 6.7:1 or more on that background; shade 3 drops violet below 4.5:1.
 * The light scheme keeps Mantine's values. Only components given a plain
 * colour name (color="green") use these variables; "green.6" or a hex colour
 * gets Mantine's fixed rgba background instead.
 */
export const DARK_LIGHT_VARIANT = { shade: 5, alpha: 0.24, hoverAlpha: 0.32, textShade: 2 } as const;

export const cssVariablesResolver: CSSVariablesResolver = (current) => {
  const dark: Record<string, string> = {};
  for (const [name, shades] of Object.entries(current.colors)) {
    // "dark" is the surface greys, not a hue; a virtualColor() is an object
    // whose variables Mantine builds itself.
    if (name === "dark" || !Array.isArray(shades)) continue;
    const base = shades[DARK_LIGHT_VARIANT.shade];
    dark[`--mantine-color-${name}-light`] = rgba(base, DARK_LIGHT_VARIANT.alpha);
    dark[`--mantine-color-${name}-light-hover`] = rgba(base, DARK_LIGHT_VARIANT.hoverAlpha);
    dark[`--mantine-color-${name}-light-color`] = shades[DARK_LIGHT_VARIANT.textShade];
  }
  return { variables: {}, light: {}, dark };
};
