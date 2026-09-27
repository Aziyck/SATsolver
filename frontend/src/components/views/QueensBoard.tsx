import { Text } from "@mantine/core";
import { IconChessQueenFilled } from "@tabler/icons-react";

const MAX_DRAWN = 64;

export function QueensBoard({ size, queens }: { size: number; queens?: [number, number][] | null }) {
  if (size > MAX_DRAWN) {
    return (
      <Text size="sm" c="dimmed">
        The board is {size}x{size}; boards above {MAX_DRAWN}x{MAX_DRAWN} are not drawn.
        {queens ? ` Queens by row: ${queens.map(([, c]) => c).join(", ")}` : ""}
      </Text>
    );
  }
  const cell = Math.max(10, Math.min(44, Math.floor(480 / size)));
  const occupied = new Set((queens ?? []).map(([r, c]) => `${r},${c}`));
  const cells = [];
  for (let r = 1; r <= size; r += 1) {
    for (let c = 1; c <= size; c += 1) {
      const queen = occupied.has(`${r},${c}`);
      cells.push(
        <div
          key={`${r}-${c}`}
          className="wz-board-cell"
          data-dark={(r + c) % 2 === 1 ? "true" : undefined}
          style={{ width: cell, height: cell }}
          aria-label={queen ? `Queen at row ${r}, column ${c}` : undefined}
        >
          {queen ? <IconChessQueenFilled size={cell * 0.72} /> : null}
        </div>,
      );
    }
  }
  return (
    <div className="wz-board" style={{ gridTemplateColumns: `repeat(${size}, ${cell}px)` }} role="img" aria-label={`${size} by ${size} board`}>
      {cells}
    </div>
  );
}
