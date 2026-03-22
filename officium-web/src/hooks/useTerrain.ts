import { useContext } from "react";
import { DisplayCtx, ActionCtx } from "../contexts/TerrainContextDefs";
import type { TerrainDisplayValue, TerrainActionValue } from "../contexts/TerrainContextDefs";

export type { TerrainDisplayValue, TerrainActionValue };

export function useTerrainDisplay(): TerrainDisplayValue {
  const ctx = useContext(DisplayCtx);
  if (!ctx) throw new Error("useTerrainDisplay must be used within TerrainProvider");
  return ctx;
}

export function useTerrainActions(): TerrainActionValue {
  const ctx = useContext(ActionCtx);
  if (!ctx) throw new Error("useTerrainActions must be used within TerrainProvider");
  return ctx;
}

export function useTerrain(): TerrainDisplayValue & TerrainActionValue {
  return { ...useTerrainDisplay(), ...useTerrainActions() };
}
