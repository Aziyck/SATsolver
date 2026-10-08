import { Alert, Button, Code, Group, Stack, Text } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

/** Keys this app keeps in localStorage (form drafts and preferences). */
function clearSavedForms() {
  try {
    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith("wizsat.")) window.localStorage.removeItem(key);
    }
  } catch {
    // storage unavailable: nothing to clear
  }
}

/**
 * Catches a render error in one page so the rest of the app (navigation, jobs
 * drawer) keeps working. A saved form draft from an older version is the usual
 * cause, hence the button that clears them. A new `resetKey` (the path)
 * clears the error, so navigating away works without remounting healthy pages.
 */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidUpdate(previous: { resetKey: string }) {
    if (this.state.error && previous.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Page crashed:", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <Alert color="red" title="This page hit an error" icon={<IconAlertTriangle />} maw={720}>
        <Stack gap="sm">
          <Code block>{error.message}</Code>
          <Text size="sm">
            If it happens every time, a form saved in this browser may no longer fit the app. Clearing the saved forms keeps your jobs and
            benchmarks; only unsent form values are lost.
          </Text>
          <Group gap="xs">
            <Button variant="default" onClick={() => window.location.reload()}>
              Reload
            </Button>
            <Button
              color="red"
              variant="light"
              onClick={() => {
                clearSavedForms();
                window.location.reload();
              }}
            >
              Clear saved forms and reload
            </Button>
          </Group>
        </Stack>
      </Alert>
    );
  }
}
