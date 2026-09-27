import { ActionIcon, Badge, Card, Group, Image, Modal, SimpleGrid, Stack, Text, ThemeIcon, Title, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconBraces, IconInfoCircle } from "@tabler/icons-react";
import { urls } from "../api/client";
import type { ProblemSpec } from "../api/types";

const CATEGORY_LABELS: Record<string, string> = { puzzle: "Puzzle", graph: "Graph", logic: "Logic", cnf: "Raw CNF" };

export function ProblemCards({ problems, selected, onSelect }: { problems: ProblemSpec[]; selected?: string; onSelect: (key: string) => void }) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="md">
      {problems.map((problem) => (
        <Card
          key={problem.key}
          className="wz-problem-card"
          data-selected={problem.key === selected}
          onClick={() => onSelect(problem.key)}
          padding="md"
          role="button"
          aria-label={`Choose ${problem.title}`}
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") onSelect(problem.key);
          }}
        >
          <Card.Section>
            {problem.image ? (
              <Image src={urls.media(problem.image)} alt="" className="wz-problem-image" />
            ) : (
              <Group className="wz-problem-image" justify="center" bg="var(--mantine-color-wizard-light)">
                <ThemeIcon size={56} radius="xl" variant="light">
                  <IconBraces size={32} />
                </ThemeIcon>
              </Group>
            )}
          </Card.Section>
          <Group justify="space-between" mt="sm" gap="xs" wrap="nowrap">
            <Text fw={650}>{problem.title}</Text>
            <Badge variant="light" color="gray" size="sm">
              {CATEGORY_LABELS[problem.category] ?? problem.category}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed" mt={4} lineClamp={3}>
            {problem.summary}
          </Text>
        </Card>
      ))}
    </SimpleGrid>
  );
}

/** "How is this encoded?" dialog with the problem's illustration and encoding notes. */
export function ProblemInfo({ problem }: { problem: ProblemSpec }) {
  const [opened, { open, close }] = useDisclosure(false);
  return (
    <>
      <Tooltip label="How this problem becomes SAT">
        <ActionIcon variant="subtle" onClick={open} aria-label={`About ${problem.title}`}>
          <IconInfoCircle size={18} />
        </ActionIcon>
      </Tooltip>
      <Modal opened={opened} onClose={close} title={<Title order={4}>{problem.title}</Title>} size="lg">
        <Stack>
          <Text>{problem.summary}</Text>
          <div>
            <Text fw={600} size="sm">
              SAT encoding
            </Text>
            <Text size="sm">{problem.description}</Text>
          </div>
          {problem.image ? (
            <>
              <Image src={urls.media(problem.image)} alt={`${problem.title} illustration`} radius="md" />
              <Text size="xs" c="dimmed">
                Illustration from the original project report (labels in Romanian).
              </Text>
            </>
          ) : null}
        </Stack>
      </Modal>
    </>
  );
}
