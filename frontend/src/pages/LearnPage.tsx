import { Anchor, Button, Card, Grid, Group, NavLink, Stack, Text, Title, Typography } from "@mantine/core";
import { IconExternalLink } from "@tabler/icons-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useParams } from "react-router-dom";

// The algorithm notes live in docs/algorithms and are bundled at build time.
const documents = import.meta.glob("../../../docs/algorithms/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

const ORDER = ["dpll", "cdcl", "walksat", "encodings"];
const TITLES: Record<string, string> = { dpll: "DPLL", cdcl: "CDCL", walksat: "WalkSAT & ProbSAT", encodings: "Problem encodings" };

const VISUALISATIONS = [
  { key: "dpll", title: "DPLL, step by step", description: "Unit propagation, branching and backtracking on a small formula." },
  { key: "cdcl", title: "CDCL, step by step", description: "The implication graph, conflict analysis and backjumping." },
  { key: "walksat", title: "WalkSAT, step by step", description: "Local search: random and greedy flips on a full assignment." },
];

const rank = (key: string) => (ORDER.includes(key) ? ORDER.indexOf(key) : ORDER.length);
const topics = Object.entries(documents)
  .map(([path, text]) => ({ key: path.split("/").pop()!.replace(/\.md$/, ""), text }))
  .sort((a, b) => rank(a.key) - rank(b.key) || a.key.localeCompare(b.key));

export default function LearnPage() {
  const { topic } = useParams();
  const current = topics.find((item) => item.key === topic);
  const visualisation = VISUALISATIONS.find((item) => `vis-${item.key}` === topic);

  return (
    <Grid gutter="lg">
      <Grid.Col span={{ base: 12, md: 3 }}>
        <Stack gap={4} className="wz-sticky">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="sm">
            Interactive
          </Text>
          {VISUALISATIONS.map((item) => (
            <NavLink key={item.key} component={Link} to={`/learn/vis-${item.key}`} label={item.title} active={topic === `vis-${item.key}`} />
          ))}
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="sm" mt="md">
            Notes
          </Text>
          {topics.map((item) => (
            <NavLink key={item.key} component={Link} to={`/learn/${item.key}`} label={TITLES[item.key] ?? item.key} active={topic === item.key} />
          ))}
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 9 }}>
        {visualisation ? (
          <Stack gap="sm">
            <Group justify="space-between">
              <div>
                <Title order={2}>{visualisation.title}</Title>
                <Text c="dimmed">{visualisation.description}</Text>
              </div>
              <Button component="a" href={`/visualisations/${visualisation.key}/`} target="_blank" variant="default" rightSection={<IconExternalLink size={14} />}>
                Open full screen
              </Button>
            </Group>
            <Card padding={0} style={{ overflow: "hidden" }}>
              <iframe title={visualisation.title} src={`/visualisations/${visualisation.key}/`} style={{ width: "100%", height: "78vh", border: 0, background: "white" }} />
            </Card>
          </Stack>
        ) : current ? (
          <Card>
            <Typography>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children }) =>
                    href && href.endsWith(".md") && !href.startsWith("http") ? (
                      <Anchor component={Link} to={`/learn/${href.split("/").pop()!.replace(/\.md$/, "")}`}>
                        {children}
                      </Anchor>
                    ) : (
                      <Anchor href={href} target="_blank" rel="noreferrer">
                        {children}
                      </Anchor>
                    ),
                }}
              >
                {current.text}
              </ReactMarkdown>
            </Typography>
          </Card>
        ) : (
          <Stack gap="md">
            <div>
              <Title order={2}>How the solvers work</Title>
              <Text c="dimmed">Step-by-step animations and notes on the algorithms behind WizSAT.</Text>
            </div>
            <Grid>
              {VISUALISATIONS.map((item) => (
                <Grid.Col key={item.key} span={{ base: 12, sm: 4 }}>
                  <Card component={Link} to={`/learn/vis-${item.key}`} className="wz-problem-card">
                    <Text fw={650}>{item.title}</Text>
                    <Text size="sm" c="dimmed" mt={4}>
                      {item.description}
                    </Text>
                  </Card>
                </Grid.Col>
              ))}
              {topics.map((item) => (
                <Grid.Col key={item.key} span={{ base: 12, sm: 4 }}>
                  <Card component={Link} to={`/learn/${item.key}`} className="wz-problem-card">
                    <Text fw={650}>{TITLES[item.key] ?? item.key}</Text>
                    <Text size="sm" c="dimmed" mt={4} lineClamp={3}>
                      {firstParagraph(item.text)}
                    </Text>
                  </Card>
                </Grid.Col>
              ))}
            </Grid>
          </Stack>
        )}
      </Grid.Col>
    </Grid>
  );
}

function firstParagraph(markdown: string): string {
  const paragraph = markdown
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .find((block) => block && !block.startsWith("#") && !block.startsWith("```"));
  return (paragraph ?? "").replace(/\s+/g, " ").replace(/[`*_]/g, "");
}
