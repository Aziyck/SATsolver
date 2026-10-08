import {
  ActionIcon,
  AppShell,
  Badge,
  Burger,
  Center,
  Group,
  Image,
  Indicator,
  Loader,
  NavLink,
  Stack,
  Text,
  Title,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChartLine, IconListDetails, IconMoon, IconSchool, IconSun, IconWand } from "@tabler/icons-react";
import { lazy, Suspense, useMemo } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useCatalog } from "./api/queries";
import { useLive } from "./api/live";
import { JobsDrawer } from "./components/JobsDrawer";
import { isActive } from "./lib/status";

const SolvePage = lazy(() => import("./pages/SolvePage"));
const BenchmarksPage = lazy(() => import("./pages/BenchmarksPage"));
const BenchmarkBuilder = lazy(() => import("./pages/BenchmarkBuilder"));
const BenchmarkResults = lazy(() => import("./pages/BenchmarkResults"));
const JobsPage = lazy(() => import("./pages/JobsPage"));
const JobPage = lazy(() => import("./pages/JobPage"));
const LearnPage = lazy(() => import("./pages/LearnPage"));

const NAV = [
  { to: "/solve", label: "Solve", icon: IconWand, description: "Encode a problem and solve it" },
  { to: "/benchmarks", label: "Benchmarks", icon: IconChartLine, description: "Sweep parameters, compare solvers" },
  { to: "/jobs", label: "Jobs", icon: IconListDetails, description: "Everything that ran" },
  { to: "/learn", label: "Learn", icon: IconSchool, description: "How the solvers work" },
];

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme("light");
  return (
    <Tooltip label={scheme === "dark" ? "Light theme" : "Dark theme"}>
      <ActionIcon
        variant="default"
        size="lg"
        aria-label="Toggle colour theme"
        onClick={() => setColorScheme(scheme === "dark" ? "light" : "dark")}
      >
        {scheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}

function ConnectionDot() {
  const connected = useLive((state) => state.connected);
  return (
    <Tooltip label={connected ? "Live updates connected" : "Reconnecting to the server..."}>
      <Group gap={6} wrap="nowrap">
        <Indicator color={connected ? "green" : "red"} processing={!connected} size={8} position="middle-center">
          <span />
        </Indicator>
        <Text size="xs" c="dimmed" visibleFrom="sm">
          {connected ? "Live" : "Offline"}
        </Text>
      </Group>
    </Tooltip>
  );
}

export default function App() {
  const [navOpened, { toggle: toggleNav, close: closeNav }] = useDisclosure(false);
  const location = useLocation();
  const catalog = useCatalog();
  const jobs = useLive((state) => state.jobs);
  const activeCount = useMemo(() => Object.values(jobs).filter((job) => isActive(job.status)).length, [jobs]);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 230, breakpoint: "sm", collapsed: { mobile: !navOpened } }}
      padding="lg"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={navOpened} onClick={toggleNav} hiddenFrom="sm" size="sm" aria-label="Open navigation" />
            <Link to="/solve" style={{ textDecoration: "none", color: "inherit" }}>
              <Group gap={8} wrap="nowrap">
                <Image src="/media/logo.png" alt="" w={36} h={36} fit="contain" />
                <div>
                  <Title order={4} lh={1}>
                    WizSAT
                  </Title>
                  <Text size="xs" c="dimmed" lh={1.2} visibleFrom="xs">
                    SAT solving workbench
                  </Text>
                </div>
              </Group>
            </Link>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <ConnectionDot />
            <JobsDrawer activeCount={activeCount} />
            <ThemeToggle />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <Stack gap={4} style={{ flex: 1 }}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              component={Link}
              to={item.to}
              label={item.label}
              description={item.description}
              leftSection={<item.icon size={20} stroke={1.6} />}
              rightSection={
                item.to === "/jobs" && activeCount > 0 ? (
                  <Badge size="sm" variant="filled" circle>
                    {activeCount}
                  </Badge>
                ) : null
              }
              active={location.pathname.startsWith(item.to)}
              onClick={closeNav}
              styles={{ root: { borderRadius: "var(--mantine-radius-md)" } }}
            />
          ))}
        </Stack>
        <Text size="xs" c="dimmed" px="sm">
          WizSAT {catalog.data?.version ?? ""} - runs locally
        </Text>
      </AppShell.Navbar>

      <AppShell.Main>
        {catalog.isError ? (
          <Center h="60vh">
            <Stack align="center" gap="xs">
              <Title order={3}>Cannot reach the WizSAT server</Title>
              <Text c="dimmed">Start it with python -m sat_web and reload this page.</Text>
            </Stack>
          </Center>
        ) : !catalog.data ? (
          <Center h="60vh">
            <Loader />
          </Center>
        ) : (
          <Suspense
            fallback={
              <Center h="60vh">
                <Loader />
              </Center>
            }
          >
            <Routes>
              <Route path="/" element={<Navigate to="/solve" replace />} />
              <Route path="/solve" element={<SolvePage />} />
              <Route path="/solve/:problem" element={<SolvePage />} />
              <Route path="/benchmarks" element={<BenchmarksPage />} />
              <Route path="/benchmarks/new" element={<BenchmarkBuilder />} />
              <Route path="/benchmarks/:id" element={<BenchmarkResults />} />
              <Route path="/jobs" element={<JobsPage />} />
              <Route path="/jobs/:id" element={<JobPage />} />
              <Route path="/learn" element={<LearnPage />} />
              <Route path="/learn/:topic" element={<LearnPage />} />
              <Route
                path="*"
                element={
                  <Center h="50vh">
                    <Stack align="center">
                      <Title order={3}>Page not found</Title>
                      <Text component={Link} to="/solve" c="wizard">
                        Back to Solve
                      </Text>
                    </Stack>
                  </Center>
                }
              />
            </Routes>
          </Suspense>
        )}
      </AppShell.Main>
    </AppShell>
  );
}
