import { createContext } from "react";
import type { Depth, InvestigationTab, Overlay, RegionName } from "../components/terrain/types";

export interface TerrainDisplayValue {
  focusedRegion: RegionName | null;
  regionDepths: Record<RegionName, Depth>;
  activeOverlay: Overlay;
  investigationTab: InvestigationTab;
}

export interface TerrainActionValue {
  focusRegion: (region: RegionName | null) => void;
  setRegionDepth: (region: RegionName, depth: Depth) => void;
  cycleDepth: (region: RegionName) => void;
  setOverlay: (overlay: Overlay) => void;
  setInvestigationTab: (tab: InvestigationTab) => void;
}

export const DisplayCtx = createContext<TerrainDisplayValue | null>(null);
export const ActionCtx = createContext<TerrainActionValue | null>(null);
