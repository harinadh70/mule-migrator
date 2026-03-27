import { create } from "zustand";
import type { BuildJob, BuildLogLine } from "@/types/build";

interface BuildState {
  currentBuild: BuildJob | null;
  builds: BuildJob[];
  logLines: BuildLogLine[];
  isBuilding: boolean;
  error: string | null;

  setCurrentBuild: (build: BuildJob | null) => void;
  setBuilds: (builds: BuildJob[]) => void;
  addLogLine: (line: BuildLogLine) => void;
  setLogLines: (lines: BuildLogLine[]) => void;
  clearLogLines: () => void;
  setBuilding: (building: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useBuildStore = create<BuildState>((set) => ({
  currentBuild: null,
  builds: [],
  logLines: [],
  isBuilding: false,
  error: null,

  setCurrentBuild: (build) => set({ currentBuild: build, error: null }),
  setBuilds: (builds) => set({ builds }),

  addLogLine: (line) =>
    set((state) => ({ logLines: [...state.logLines, line] })),

  setLogLines: (logLines) => set({ logLines }),
  clearLogLines: () => set({ logLines: [] }),
  setBuilding: (isBuilding) => set({ isBuilding }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      currentBuild: null,
      builds: [],
      logLines: [],
      isBuilding: false,
      error: null,
    }),
}));
