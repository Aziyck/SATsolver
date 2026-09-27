import { createTheme, type MantineColorsTuple } from "@mantine/core";

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
