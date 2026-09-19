import { useCallback, useState } from 'react';
import { BrainMap } from '@/components/BrainMap';
import { CortexStage } from '@/components/CortexStage';
import { WorkspacePanel } from '@/components/WorkspacePanel';
import { MemoryRail } from '@/components/MemoryRail';
import { ScanControls } from '@/components/ScanControls';
import { SwiftGuidePanel } from '@/components/SwiftGuidePanel';
import { SuggestionsPanel } from '@/components/SuggestionsPanel';
import { AgentLayersPanel } from '@/components/AgentLayersPanel';
import { useMeshSocket } from '@/hooks/useMeshSocket';
import { useMeshStore } from '@/store/meshStore';

export default function App() {
  const {
    startScan,
    stopScan,
    focusNode,
    openWorkspace,
    openConcept,
    guideStart,
    guideNext,
    guidePrev,
    runAgentCycle,
    startIssueLoop,
    stopIssueLoop,
  } = useMeshSocket();
  const scanning = useMeshStore((s) => s.scanning);
  const cycleCount = useMeshStore((s) => s.cycleCount);
  const lastCycleAt = useMeshStore((s) => s.lastCycleAt);
  const connected = useMeshStore((s) => s.connected);
  const [flatMap, setFlatMap] = useState(false);

  const onFocusArea = useCallback(
    (areaId: string) => {
      // Prefer matching mesh nodes by label/id substring when present
      const nodes = useMeshStore.getState().nodes;
      const hit =
        nodes.find((n) => n.id.includes(areaId.replace('area.', ''))) ||
        nodes.find((n) => n.label.toLowerCase().includes(areaId.replace('area.', '')));
      if (hit) focusNode(hit.id);
    },
    [focusNode],
  );

  return (
    <div className="app-atmosphere">
      <header className="hero hero-cortex">
        <div className="hero-overlay">
          <p className="brand">Cam</p>
          <p className="lede hero-lede">
            Glass cortex · live agents · continuous system health
          </p>
          <div className="hero-cta">
            <ScanControls
              scanning={scanning}
              cycleCount={cycleCount}
              lastCycleAt={lastCycleAt}
              connected={connected}
              onStart={() => startScan()}
              onStop={() => stopScan()}
            />
            <button type="button" className="btn" onClick={() => guideStart()}>
              Swift Guide tour
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => runAgentCycle()}>
              Agent cycle
            </button>
            <button
              type="button"
              className={`btn btn-ghost${flatMap ? ' active' : ''}`}
              onClick={() => setFlatMap((v) => !v)}
              aria-pressed={flatMap}
            >
              {flatMap ? '3D cortex' : '2D map'}
            </button>
            <span
              className={`connection-dot${connected ? ' online' : ''}`}
              title={connected ? 'Connected' : 'Reconnecting'}
              aria-hidden
            />
            <span className="connection-label">
              {connected ? 'Live mesh' : 'Connecting…'}
            </span>
          </div>
        </div>

        {flatMap ? (
          <BrainMap onFocusNode={(id) => focusNode(id)} />
        ) : (
          <CortexStage onFocusArea={onFocusArea} />
        )}
      </header>

      <div className="detail-grid three">
        <WorkspacePanel onOpenWorkspace={(id) => openWorkspace(id)} />
        <SwiftGuidePanel
          onOpenConcept={(id) => openConcept(id)}
          onGuideStart={() => guideStart()}
          onGuideNext={() => guideNext()}
          onGuidePrev={() => guidePrev()}
          onOpenWorkspace={(id) => openWorkspace(id)}
        />
        <AgentLayersPanel
          onFocusNode={(id) => focusNode(id)}
          onRunAgentCycle={() => runAgentCycle()}
          onStartIssueLoop={() => startIssueLoop()}
          onStopIssueLoop={() => stopIssueLoop()}
        />
      </div>

      <div className="detail-grid">
        <SuggestionsPanel
          onOpenWorkspace={(id) => openWorkspace(id)}
          onOpenConcept={(id) => openConcept(id)}
        />
        <MemoryRail />
      </div>
    </div>
  );
}
