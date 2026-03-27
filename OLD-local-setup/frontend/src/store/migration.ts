import { create } from "zustand";
import type { MigrationJob, MigrationStats } from "@/types/migration";
import type { AgentTrace, PipelineStatus } from "@/types/agent";

interface MigrationState {
  currentMigration: MigrationJob | null;
  migrations: MigrationJob[];
  stats: MigrationStats | null;
  agentTraces: AgentTrace[];
  pipelineStatus: PipelineStatus | null;
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;

  setCurrentMigration: (migration: MigrationJob | null) => void;
  setMigrations: (migrations: MigrationJob[]) => void;
  setStats: (stats: MigrationStats) => void;
  setAgentTraces: (traces: AgentTrace[]) => void;
  updateAgentTrace: (trace: AgentTrace) => void;
  setPipelineStatus: (status: PipelineStatus | null) => void;
  updatePipelineAgent: (
    agentType: string,
    update: Partial<AgentTrace>
  ) => void;
  setLoading: (loading: boolean) => void;
  setCreating: (creating: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  currentMigration: null,
  migrations: [],
  stats: null,
  agentTraces: [],
  pipelineStatus: null,
  isLoading: false,
  isCreating: false,
  error: null,
};

export const useMigrationStore = create<MigrationState>((set) => ({
  ...initialState,

  setCurrentMigration: (migration) =>
    set({ currentMigration: migration, error: null }),

  setMigrations: (migrations) => set({ migrations }),

  setStats: (stats) => set({ stats }),

  setAgentTraces: (traces) => set({ agentTraces: traces }),

  updateAgentTrace: (trace) =>
    set((state) => {
      const existing = state.agentTraces.findIndex(
        (t) => t.agentType === trace.agentType
      );
      if (existing >= 0) {
        const updated = [...state.agentTraces];
        updated[existing] = trace;
        return { agentTraces: updated };
      }
      return { agentTraces: [...state.agentTraces, trace] };
    }),

  setPipelineStatus: (status) => set({ pipelineStatus: status }),

  updatePipelineAgent: (agentType, update) =>
    set((state) => {
      if (!state.pipelineStatus) return {};
      const agents = state.pipelineStatus.agents.map((a) =>
        a.agentType === agentType ? { ...a, ...update } : a
      );
      return {
        pipelineStatus: { ...state.pipelineStatus, agents },
      };
    }),

  setLoading: (isLoading) => set({ isLoading }),
  setCreating: (isCreating) => set({ isCreating }),
  setError: (error) => set({ error }),
  reset: () => set(initialState),
}));
