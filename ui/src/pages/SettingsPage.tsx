import { PlaceholderPage } from "./PlaceholderPage";
import type { Project } from "../api/client";

type SettingsPageProps = {
  currentProject: Project | null;
};

export function SettingsPage({ currentProject }: SettingsPageProps) {
  return (
    <PlaceholderPage
      eyebrow="Settings"
      title="Settings"
      body={
        currentProject
          ? `Project defaults and runtime adapter settings for ${currentProject.name} will be configured here later.`
          : "Select a project to configure project defaults. Runtime adapter settings will be configured here later."
      }
      emptyMessage={currentProject ? undefined : "No project selected."}
    />
  );
}
