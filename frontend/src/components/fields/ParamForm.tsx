import {
  ActionIcon,
  Badge,
  Button,
  Chip,
  Collapse,
  FileButton,
  Group,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { IconArrowBackUp, IconDice5, IconFileUpload, IconRestore, IconTrash } from "@tabler/icons-react";
import { useState, type ReactNode } from "react";
import type { Field } from "../../api/types";
import { edgesAsText, parseEdges } from "../../lib/edges";
import { formatCount } from "../../lib/format";
import { changedFields, cloneValue, displayValue, isDefaultValue, isNumericKind, isVisible, parseNumberList, type Values } from "../../lib/params";
import { asGrid, emptyGrid, parsePuzzle, sudokuSize } from "../../lib/sudoku";
import { SudokuEditor } from "../views/SudokuBoard";

export interface ParamFormProps {
  fields: Field[];
  values: Values;
  onChange: (name: string, value: unknown) => void;
  errors?: Record<string, string>;
  /** Benchmark mode: sweepable fields accept lists and ranges. */
  sweep?: boolean;
  /** Field names rendered elsewhere by the parent (e.g. an interactive editor). */
  hide?: string[];
  /** Show a reset button on every field that differs from its default. */
  resettable?: boolean;
}

export function ParamForm({ fields, values, onChange, errors = {}, sweep = false, hide = [], resettable = false }: ParamFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const visible = fields.filter((field) => isVisible(field, values) && !hide.includes(field.name));
  const basic = visible.filter((field) => !field.advanced);
  const advanced = visible.filter((field) => field.advanced);
  const advancedChanged = resettable ? advanced.filter((field) => !isDefaultValue(field, values[field.name])).length : 0;

  const render = (field: Field) => {
    const input = <ParamInput key={field.name} field={field} value={values[field.name]} values={values} onChange={onChange} error={errors[field.name]} sweep={sweep} />;
    if (!resettable) return input;
    return (
      <ResettableField key={field.name} field={field} value={values[field.name]} onReset={() => onChange(field.name, cloneValue(field.default))}>
        {input}
      </ResettableField>
    );
  };

  return (
    <Stack gap="sm">
      {basic.map(render)}
      {advanced.length ? (
        <>
          <Button variant="subtle" size="compact-sm" onClick={() => setShowAdvanced((open) => !open)} style={{ alignSelf: "flex-start" }}>
            {showAdvanced ? "Hide advanced options" : `Advanced options (${advanced.length})`}
            {advancedChanged && !showAdvanced ? ` - ${advancedChanged} changed` : ""}
          </Button>
          <Collapse in={showAdvanced}>
            <Stack gap="sm">{advanced.map(render)}</Stack>
          </Collapse>
        </>
      ) : null}
    </Stack>
  );
}

/** Wraps a field with a small "back to default" button when its value was changed. */
function ResettableField({ field, value, onReset, children }: { field: Field; value: unknown; onReset: () => void; children: ReactNode }) {
  const changed = !isDefaultValue(field, value);
  return (
    <div className="wz-field">
      {children}
      {changed ? (
        <Tooltip label={`Back to the default: ${displayValue(field, field.default)}`}>
          <ActionIcon className="wz-field-reset" variant="subtle" size="sm" onClick={onReset} aria-label={`Reset ${field.label} to its default`}>
            <IconArrowBackUp size={15} />
          </ActionIcon>
        </Tooltip>
      ) : null}
    </div>
  );
}

/** "Reset 3 changed options" for a whole option set; hidden when everything is at its default. */
export function ResetToDefaults({ fields, values, onReset, size = "xs" }: { fields: Field[]; values: Values; onReset: () => void; size?: "xs" | "compact-xs" }) {
  const changed = changedFields(fields, values);
  if (!changed.length) return null;
  return (
    <Tooltip label={`Changed: ${changed.map((field) => field.label).join(", ")}`} multiline maw={320}>
      <Button variant="subtle" size={size} leftSection={<IconRestore size={14} />} onClick={onReset} style={{ flexShrink: 0 }}>
        Reset {changed.length} changed option{changed.length === 1 ? "" : "s"}
      </Button>
    </Tooltip>
  );
}

function withUnit(field: Field): string {
  return field.unit ? `${field.label} (${field.unit})` : field.label;
}

export function ParamInput({
  field,
  value,
  values,
  onChange,
  error,
  sweep,
}: {
  field: Field;
  value: unknown;
  values: Values;
  onChange: (name: string, value: unknown) => void;
  error?: string;
  sweep: boolean;
}) {
  const set = (next: unknown) => onChange(field.name, next);

  if (sweep && field.sweepable && (isNumericKind(field) || field.kind === "choice" || field.kind === "cnf")) {
    return <SweepInput field={field} value={value} onChange={set} error={error} />;
  }

  switch (field.kind) {
    case "choice":
      return <ChoiceInput field={field} value={value} onChange={set} error={error} />;
    case "bool":
      return <Switch label={field.label} description={field.help} checked={Boolean(value)} onChange={(event) => set(event.currentTarget.checked)} />;
    case "int":
    case "float":
      if (field.choices.length) return <ChoiceInput field={field} value={value} onChange={(next) => set(Number(next))} error={error} />;
      return (
        <NumberInput
          label={withUnit(field)}
          description={field.help}
          value={value as number | string}
          onChange={set}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step={field.step ?? (field.kind === "int" ? 1 : 0.1)}
          allowDecimal={field.kind === "float"}
          placeholder={field.placeholder}
          error={error}
          thousandSeparator=","
        />
      );
    case "seed":
      return (
        <NumberInput
          label={field.label}
          description={field.help}
          value={(value ?? "") as number | string}
          onChange={(next) => set(next === "" ? null : next)}
          min={0}
          allowDecimal={false}
          allowNegative={false}
          placeholder={field.placeholder || "random"}
          error={error}
          rightSection={
            <Tooltip label="Random seed">
              <ActionIcon variant="subtle" aria-label="Pick a random seed" onClick={() => set(Math.floor(Math.random() * 100000))}>
                <IconDice5 size={16} />
              </ActionIcon>
            </Tooltip>
          }
        />
      );
    case "text":
      return <Textarea label={field.label} description={field.help} value={String(value ?? "")} onChange={(event) => set(event.currentTarget.value)} autosize minRows={2} error={error} />;
    case "edges":
      return <EdgesInput field={field} value={value} onChange={set} error={error} />;
    case "sudoku_grid":
      return <SudokuGridInput field={field} value={value} size={sudokuSize(values.size)} onChange={set} error={error} />;
    case "cnf":
      return <CnfInput field={field} value={value} onChange={set} error={error} />;
  }
}

function ChoiceInput({ field, value, onChange, error }: { field: Field; value: unknown; onChange: (value: unknown) => void; error?: string }) {
  const current = field.choices.find((choice) => choice.value === String(value));
  const labelLength = field.choices.reduce((sum, choice) => sum + choice.label.length, 0);
  if (field.choices.length <= 4 && labelLength <= 36) {
    return (
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          {field.label}
        </Text>
        <SegmentedControl
          fullWidth
          value={String(value)}
          onChange={onChange}
          data={field.choices.map((choice) => ({ value: choice.value, label: choice.label }))}
          aria-label={field.label}
        />
        {current?.help || field.help ? (
          <Text size="xs" c="dimmed">
            {current?.help || field.help}
          </Text>
        ) : null}
        {error ? (
          <Text size="xs" c="red">
            {error}
          </Text>
        ) : null}
      </Stack>
    );
  }
  return (
    <Select
      label={field.label}
      description={current?.help || field.help}
      data={field.choices.map((choice) => ({ value: choice.value, label: choice.label }))}
      value={String(value)}
      onChange={(next) => next !== null && onChange(next)}
      allowDeselect={false}
      error={error}
    />
  );
}

function EdgesInput({ field, value, onChange, error }: { field: Field; value: unknown; onChange: (value: unknown) => void; error?: string }) {
  const text = edgesAsText(value);
  const parsed = parseEdges(text);
  return (
    <Textarea
      label={field.label}
      description={field.help}
      value={text}
      onChange={(event) => onChange(event.currentTarget.value)}
      autosize
      minRows={2}
      maxRows={8}
      styles={{ input: { fontFamily: "var(--mantine-font-family-monospace)" } }}
      error={error || parsed.errors[0]}
      rightSectionWidth={80}
      rightSection={
        <Badge variant="light" size="sm">
          {parsed.edges.length} edges
        </Badge>
      }
    />
  );
}

function SudokuGridInput({
  field,
  value,
  size,
  onChange,
  error,
}: {
  field: Field;
  value: unknown;
  size: number;
  onChange: (value: unknown) => void;
  error?: string;
}) {
  const grid = asGrid(value, size);
  const [pasteText, setPasteText] = useState("");
  const loadText = (text: string) => {
    const puzzle = parsePuzzle(text);
    if (puzzle && puzzle.length === size) {
      onChange(puzzle);
      return true;
    }
    return false;
  };
  return (
    <Stack gap={6}>
      <Group justify="space-between">
        <Text size="sm" fw={500}>
          {field.label}
        </Text>
        <Button variant="subtle" size="compact-xs" leftSection={<IconTrash size={12} />} onClick={() => onChange(emptyGrid(size))}>
          Clear
        </Button>
      </Group>
      <SudokuEditor value={grid} onChange={onChange} onPastePuzzle={loadText} />
      {size <= 9 ? (
        <TextInput
          size="xs"
          placeholder={`Paste ${size * size} digits (0 or . for empty) and press Enter`}
          value={pasteText}
          onChange={(event) => setPasteText(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && loadText(pasteText)) setPasteText("");
          }}
          aria-label="Paste a puzzle"
        />
      ) : null}
      <Text size="xs" c={error ? "red" : "dimmed"}>
        {error || field.help}
      </Text>
    </Stack>
  );
}

interface CnfValue {
  name: string;
  text: string;
}

function asCnf(value: unknown): CnfValue {
  if (typeof value === "string") return { name: "", text: value };
  if (value && typeof value === "object" && "text" in value) return value as CnfValue;
  return { name: "", text: "" };
}

function readFiles(files: File[], onLoad: (items: CnfValue[]) => void) {
  Promise.all(files.map((file) => file.text().then((text) => ({ name: file.name, text })))).then(onLoad);
}

function CnfInput({ field, value, onChange, error }: { field: Field; value: unknown; onChange: (value: unknown) => void; error?: string }) {
  const cnf = asCnf(value);
  const lines = cnf.text.split("\n").length;
  return (
    <Stack gap={6}>
      <Group justify="space-between">
        <Text size="sm" fw={500}>
          {field.label}
          {cnf.name ? (
            <Badge ml="xs" variant="light" size="sm">
              {cnf.name}
            </Badge>
          ) : null}
        </Text>
        <FileButton onChange={(file) => file && readFiles([file], ([item]) => onChange(item))} accept=".cnf,.dimacs,.txt">
          {(props) => (
            <Button {...props} variant="light" size="compact-sm" leftSection={<IconFileUpload size={14} />}>
              Open .cnf file
            </Button>
          )}
        </FileButton>
      </Group>
      <Textarea
        value={cnf.text.length > 200_000 ? `${cnf.text.slice(0, 2000)}\n... (${formatCount(lines)} lines, loaded from file)` : cnf.text}
        readOnly={cnf.text.length > 200_000}
        onChange={(event) => onChange({ name: cnf.name, text: event.currentTarget.value })}
        autosize
        minRows={6}
        maxRows={16}
        styles={{ input: { fontFamily: "var(--mantine-font-family-monospace)", fontSize: 12 } }}
        error={error}
        aria-label="DIMACS text"
      />
      <Text size="xs" c="dimmed">
        {field.help}
      </Text>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Benchmark (sweep) inputs
// ---------------------------------------------------------------------------

function SweepInput({ field, value, onChange, error }: { field: Field; value: unknown; onChange: (value: unknown) => void; error?: string }) {
  if (field.kind === "choice" || (isNumericKind(field) && field.choices.length)) {
    const selected = Array.isArray(value) ? (value as unknown[]).map(String) : String(value ?? "").split(",").map((item) => item.trim()).filter(Boolean);
    return (
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          {field.label}
        </Text>
        <Chip.Group
          multiple
          value={selected}
          onChange={(next) => {
            const ordered = field.choices.map((choice) => choice.value).filter((item) => next.includes(item));
            onChange(field.kind === "choice" ? ordered : ordered.join(", "));
          }}
        >
          <Group gap={6}>
            {field.choices.map((choice) => (
              <Chip key={choice.value} value={choice.value} size="sm" variant="light">
                {choice.label}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
        <Text size="xs" c={error ? "red" : "dimmed"}>
          {error || (selected.length > 1 ? `${selected.length} values, one case each` : field.help)}
        </Text>
      </Stack>
    );
  }

  if (field.kind === "cnf") {
    const items = (Array.isArray(value) ? value : [value]).map(asCnf).filter((item) => item.text);
    return (
      <Stack gap={6}>
        <Group justify="space-between">
          <Text size="sm" fw={500}>
            CNF files ({items.length})
          </Text>
          <FileButton multiple onChange={(files) => readFiles(files, (loaded) => onChange([...items, ...loaded]))} accept=".cnf,.dimacs,.txt">
            {(props) => (
              <Button {...props} variant="light" size="compact-sm" leftSection={<IconFileUpload size={14} />}>
                Add files
              </Button>
            )}
          </FileButton>
        </Group>
        {items.map((item, index) => (
          <Group key={`${item.name}-${index}`} justify="space-between" gap="xs">
            <Text size="sm" className="wz-mono" truncate>
              {item.name || `formula ${index + 1}`}
            </Text>
            <Group gap={6}>
              <Text size="xs" c="dimmed">
                {formatCount(item.text.split("\n").length)} lines
              </Text>
              <ActionIcon variant="subtle" color="red" size="sm" aria-label={`Remove ${item.name}`} onClick={() => onChange(items.filter((_, i) => i !== index))}>
                <IconTrash size={14} />
              </ActionIcon>
            </Group>
          </Group>
        ))}
        <Text size="xs" c={error ? "red" : "dimmed"}>
          {error || "Each file is one benchmark case."}
        </Text>
      </Stack>
    );
  }

  const text = value === null || value === undefined ? "" : String(value);
  const parsed = text.trim() ? parseNumberList(text, field.kind !== "float") : [];
  const preview =
    typeof parsed === "string"
      ? parsed
      : parsed.length === 0
        ? field.kind === "seed"
          ? "blank: uses the benchmark seed"
          : "enter a value"
        : parsed.length === 1
          ? "1 value"
          : `${parsed.length} values: ${parsed.slice(0, 6).join(", ")}${parsed.length > 6 ? ", ..." : ""}`;
  return (
    <TextInput
      label={withUnit(field)}
      value={text}
      onChange={(event) => onChange(event.currentTarget.value)}
      placeholder={field.kind === "seed" ? "e.g. 1..10" : "e.g. 10, 20, 30 or 1..20"}
      error={error || (typeof parsed === "string" ? parsed : undefined)}
      description={typeof parsed === "string" ? undefined : preview}
      styles={{ input: { fontFamily: "var(--mantine-font-family-monospace)" } }}
    />
  );
}

/** Initial benchmark-form value for a field: numbers become editable text. */
export function sweepDefault(field: Field): unknown {
  if (field.kind === "choice") return field.sweepable ? [String(field.default)] : field.default;
  if (field.kind === "cnf") return field.sweepable ? [field.default] : field.default;
  if (isNumericKind(field) && field.sweepable) return field.default === null || field.default === undefined ? "" : String(field.default);
  return field.default;
}
