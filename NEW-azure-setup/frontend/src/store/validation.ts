import { create } from "zustand";

interface ValidationState {
  activeValidationId: string | null;
  setActiveValidationId: (id: string | null) => void;
  reset: () => void;
}

export const useValidationStore = create<ValidationState>((set) => ({
  activeValidationId: null,
  setActiveValidationId: (id) => set({ activeValidationId: id }),
  reset: () => set({ activeValidationId: null }),
}));
