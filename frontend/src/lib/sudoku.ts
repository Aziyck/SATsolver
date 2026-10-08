export type Grid = number[][];

export function emptyGrid(size: number): Grid {
  return Array.from({ length: size }, () => Array.from({ length: size }, () => 0));
}

/** Board sizes the Sudoku problem accepts (SUDOKU_SIZES in problems/sudoku.py). */
export const SUDOKU_SIZES = [4, 9, 16, 25];

/**
 * The board size for a form's "size" value: a number, "9", a swept "4, 9" or
 * a list. The first valid size wins; anything else (blank, a size being typed,
 * a stale saved draft) gives 9, so the editor never draws an impossible board.
 */
export function sudokuSize(value: unknown): number {
  const items = Array.isArray(value) ? value : String(value ?? "").split(/[\s,]+/);
  for (const item of items) {
    const size = Number(item);
    if (SUDOKU_SIZES.includes(size)) return size;
  }
  return 9;
}

export function boxSize(size: number): number {
  return Math.round(Math.sqrt(size));
}

export function asGrid(value: unknown, size: number): Grid {
  if (Array.isArray(value) && value.length === size && value.every((row) => Array.isArray(row) && row.length === size)) {
    return (value as unknown[][]).map((row) => row.map((cell) => Number(cell) || 0));
  }
  return emptyGrid(size);
}

/** Read a pasted puzzle: digits, 0/./_ for empty; other separators are ignored. Sizes 4 and 9 only. */
export function parsePuzzle(text: string): Grid | null {
  const cells = [...text].filter((char) => /[0-9._]/.test(char));
  const size = Math.round(Math.sqrt(cells.length));
  if (size * size !== cells.length || (size !== 4 && size !== 9)) return null;
  const grid = emptyGrid(size);
  cells.forEach((char, index) => {
    grid[Math.floor(index / size)][index % size] = /[1-9]/.test(char) ? Number(char) : 0;
  });
  return grid;
}

export function puzzleToText(grid: Grid): string {
  return grid.map((row) => row.map((cell) => (cell ? String(cell) : ".")).join(grid.length > 9 ? " " : "")).join("\n");
}

export function countGivens(grid: Grid): number {
  return grid.reduce((sum, row) => sum + row.filter(Boolean).length, 0);
}

/** Cells (row, col) whose value repeats in a row, column or box. */
export function conflictCells(grid: Grid): Set<string> {
  const size = grid.length;
  const box = boxSize(size);
  const conflicts = new Set<string>();
  const check = (cells: [number, number][]) => {
    const seen = new Map<number, [number, number][]>();
    for (const [r, c] of cells) {
      const value = grid[r]?.[c];
      if (!value) continue;
      seen.set(value, [...(seen.get(value) ?? []), [r, c]]);
    }
    for (const positions of seen.values()) {
      if (positions.length > 1) positions.forEach(([r, c]) => conflicts.add(`${r},${c}`));
    }
  };
  for (let i = 0; i < size; i += 1) {
    check(Array.from({ length: size }, (_, c) => [i, c] as [number, number]));
    check(Array.from({ length: size }, (_, r) => [r, i] as [number, number]));
    // Boxes only exist when the size is a square (4, 9, 16, 25).
    if (box * box !== size) continue;
    const top = Math.floor(i / box) * box;
    const left = (i % box) * box;
    check(Array.from({ length: size }, (_, k) => [top + Math.floor(k / box), left + (k % box)] as [number, number]));
  }
  return conflicts;
}
