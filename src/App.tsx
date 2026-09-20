import { useCallback, useState } from 'react';
import { BrainMap } from '@/components/BrainMap';
import { CortexStage } from '@/components/CortexStage';
import { CamStage } from '@/components/CamStage';
import { WorkspacePanel } from '@/components/WorkspacePanel';
import { MemoryRail } from '@/components/MemoryRail';
import { ScanControls } from '@/components/ScanControls';
import { SwiftGuidePanel } from '@/components/SwiftGuidePanel';
import { SuggestionsPanel } from '@/components/SuggestionsPanel';
import { NeedsAttentionPanel } from '@/components/NeedsAttentionPanel';
import { AgentSpawnBay } from '@/components/AgentSpawnBay';
import { SystemPulse } from '@/components/SystemPulse';
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
  const [listening, setListening] = useState(false);
  const [flatMap, setFlatMap] = useState(false);
  const [meshOpen, setMeshOpen] = useState(false);
  const onListeningChange = useCallback((v: boolean) => setListening(v), []);

  const onFocusArea = useCallback(
    (areaId: string) => {
      const nodes = useMeshStore.getState().nodes;
      const key = areaId.replace('area.', '');
      const hit =
        nodes.find((n) => n.id.includes(key)) ||
        nodes.find((n) => n.label.toLowerCase().includes(key));
      if (hit) focusNode(hit.id);
    },
    [focusNode],
  );

  return (
    <div className="app-atmosphere cam-home">
      <header className="hero cam-hero cam-hero-presence">
        <div className="hero-brand-row">
          <p className="brand">Cam</p>
          <span
            className={`connection-dot${connected ? ' online' : ''}`}
            title={connected ? 'Connected' : 'Reconnecting'}
            aria-hidden
          />
          <span className="connection-label sr-only">
            {connected ? 'Live mesh' : 'Connecting…'}
          </span>
          <span className={`hero-live${connected ? ' on' : ''}`} aria-hidden>
            {connected ? 'with you' : 'waking…'}
          </span>
        </div>
        <h1 className="headline">She listens when you open the mic.</h1>
        <p className="lede">
          Soft airy English. Aaron only. Watch the cortex run, then Cam types and speaks back.
        </p>

        <CamStage onListeningChange={onListeningChange} />
      </header>

      <section className="mesh-ops" aria-label="Mesh and agents">
        <button
          type="button"
          className={`mesh-ops-toggle${meshOpen ? ' open' : ''}`}
          aria-expanded={meshOpen}
          onClick={() => setMeshOpen((v) => !v)}
        >
          <span className="mesh-ops-label">{meshOpen ? 'Hide the mesh' : 'Open the mesh'}</span>
          <span className="mesh-ops-hint">
            3D cortex · agents · needs attention · system pulse · workspaces · guide · memory
          </span>
        </button>

        {meshOpen ? (
          <div className="mesh-ops-body">
            <div className="mesh-ops-toolbar">
              <ScanControls
                scanning={scanning}
                cycleCount={cycleCount}
                lastCycleAt={lastCycleAt}
                connected={connected}
                onStart={() => startScan()}
                onStop={() => stopScan()}
              />
              <button type="button" className="btn btn-ghost" onClick={() => guideStart()}>
                Swift Guide tour
              </button>
              <button
                type="button"
                className={`btn btn-ghost${flatMap ? ' active' : ''}`}
                onClick={() => setFlatMap((v) => !v)}
                aria-pressed={flatMap}
              >
                {flatMap ? '3D cortex' : '2D map'}
              </button>
            </div>

            <div className={`mesh-cortex-embed${listening ? ' listening' : ''}`}>
              {flatMap ? (
                <BrainMap onFocusNode={(id) => focusNode(id)} />
              ) : (
                <CortexStage listening={listening} onFocusArea={onFocusArea} />
              )}
            </div>

            <AgentSpawnBay
              onFocusNode={(id) => focusNode(id)}
              onRunAgentCycle={() => runAgentCycle()}
              onStartIssueLoop={() => startIssueLoop()}
              onStopIssueLoop={() => stopIssueLoop()}
            />

            <div className="detail-grid">
              <NeedsAttentionPanel
                onOpenWorkspace={(id) => openWorkspace(id)}
                onFocusNode={(id) => focusNode(id)}
                onRunAgentCycle={() => runAgentCycle()}
              />
            </div>

            <SystemPulse />

            <div className="detail-grid three">
              <WorkspacePanel onOpenWorkspace={(id) => openWorkspace(id)} />
              <SwiftGuidePanel
                onOpenConcept={(id) => openConcept(id)}
                onGuideStart={() => guideStart()}
                onGuideNext={() => guideNext()}
                onGuidePrev={() => guidePrev()}
                onOpenWorkspace={(id) => openWorkspace(id)}
              />
              <SuggestionsPanel
                onOpenWorkspace={(id) => openWorkspace(id)}
                onOpenConcept={(id) => openConcept(id)}
              />
            </div>

            <div className="detail-grid">
              <MemoryRail />
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
