import { useMeshStore } from '@/store/meshStore';

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function MemoryRail() {
  const memory = useMeshStore((s) => s.memory);

  return (
    <section className="panel" aria-labelledby="memory-heading">
      <div className="panel-header">
        <h2 id="memory-heading">Memory</h2>
        <span className="panel-meta">{memory.length} traces</span>
      </div>

      <div className="memory-rail">
        {memory.length === 0 ? (
          <p className="empty-note">Scan traces will appear here as cycles complete.</p>
        ) : (
          <ul className="memory-list">
            {memory.slice(0, 40).map((trace) => (
              <li key={trace.id} className="memory-item">
                <div>
                  <span className="memory-time">{formatTime(trace.createdAt)}</span>
                  <span className="memory-kind">{trace.kind}</span>
                </div>
                <div className="memory-content">{trace.content}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
