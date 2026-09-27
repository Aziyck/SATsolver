import { Group, Text } from "@mantine/core";
import { useRef } from "react";
import { boxSize, conflictCells, type Grid } from "../../lib/sudoku";

function cellSizeFor(size: number): number {
  if (size <= 4) return 52;
  if (size <= 9) return 40;
  if (size <= 16) return 28;
  return 22;
}

function cellFlags(size: number, r: number, c: number) {
  const box = boxSize(size);
  return {
    "data-box-right": c % box === box - 1 && c !== size - 1 ? "true" : undefined,
    "data-box-bottom": r % box === box - 1 && r !== size - 1 ? "true" : undefined,
    "data-alt": (Math.floor(r / box) + Math.floor(c / box)) % 2 === 1 ? "true" : undefined,
  };
}

/** Read-only board: givens in ink, solved cells in the accent colour. */
export function SudokuBoard({ givens, solution }: { givens: Grid; solution?: Grid | null }) {
  const size = givens.length;
  const cell = cellSizeFor(size);
  const conflicts = conflictCells(givens);
  return (
    <div>
      <div className="wz-sudoku" style={{ gridTemplateColumns: `repeat(${size}, ${cell}px)` }} role="grid" aria-label="Sudoku board">
        {givens.map((row, r) =>
          row.map((given, c) => {
            const value = given || solution?.[r]?.[c] || 0;
            return (
              <div
                key={`${r}-${c}`}
                role="gridcell"
                className="wz-sudoku-cell"
                style={{ height: cell, fontSize: cell * 0.46 }}
                data-solved={!given && value ? "true" : undefined}
                data-conflict={conflicts.has(`${r},${c}`) ? "true" : undefined}
                {...cellFlags(size, r, c)}
              >
                {value || ""}
              </div>
            );
          }),
        )}
      </div>
      {solution ? (
        <Group gap="md" mt="xs">
          <Text size="xs" c="dimmed">
            <b>Bold</b>: givens
          </Text>
          <Text size="xs" style={{ color: "var(--wz-solved)" }}>
            Coloured: found by the solver
          </Text>
        </Group>
      ) : null}
    </div>
  );
}

/** Editable grid with arrow-key navigation. Pasting a 4x4 or 9x9 puzzle string fills the whole grid. */
export function SudokuEditor({
  value,
  onChange,
  onPastePuzzle,
}: {
  value: Grid;
  onChange: (grid: Grid) => void;
  onPastePuzzle?: (text: string) => boolean;
}) {
  const size = value.length;
  const cell = cellSizeFor(size);
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const conflicts = conflictCells(value);

  const focusCell = (r: number, c: number) => {
    const target = refs.current[((r + size) % size) * size + ((c + size) % size)];
    target?.focus();
    target?.select();
  };

  const setCell = (r: number, c: number, raw: string) => {
    const digits = raw.replace(/\D/g, "");
    let number = digits ? Number(digits) : 0;
    if (number > size) number = Number(digits.slice(-1));
    if (number > size) number = 0;
    const next = value.map((row) => [...row]);
    next[r][c] = number;
    onChange(next);
    if (number && (size <= 9 || digits.length >= 2 || number * 10 > size)) focusCell(r, c + 1);
  };

  return (
    <div
      className="wz-sudoku"
      style={{ gridTemplateColumns: `repeat(${size}, ${cell}px)` }}
      onPaste={(event) => {
        const text = event.clipboardData.getData("text");
        if (onPastePuzzle && text.replace(/\s/g, "").length > 2 && onPastePuzzle(text)) event.preventDefault();
      }}
    >
      {value.map((row, r) =>
        row.map((given, c) => (
          <div
            key={`${r}-${c}`}
            className="wz-sudoku-cell"
            style={{ height: cell, fontSize: cell * 0.46 }}
            data-conflict={conflicts.has(`${r},${c}`) ? "true" : undefined}
            {...cellFlags(size, r, c)}
          >
            <input
              ref={(element) => {
                refs.current[r * size + c] = element;
              }}
              className="wz-sudoku-input"
              aria-label={`Row ${r + 1}, column ${c + 1}`}
              inputMode="numeric"
              value={given ? String(given) : ""}
              onChange={(event) => setCell(r, c, event.currentTarget.value)}
              onFocus={(event) => event.currentTarget.select()}
              onKeyDown={(event) => {
                const moves: Record<string, [number, number]> = {
                  ArrowUp: [-1, 0],
                  ArrowDown: [1, 0],
                  ArrowLeft: [0, -1],
                  ArrowRight: [0, 1],
                };
                const move = moves[event.key];
                if (move) {
                  event.preventDefault();
                  focusCell(r + move[0], c + move[1]);
                } else if (event.key === "Backspace" || event.key === "Delete" || event.key === "0" || event.key === ".") {
                  event.preventDefault();
                  setCell(r, c, "");
                }
              }}
            />
          </div>
        )),
      )}
    </div>
  );
}
