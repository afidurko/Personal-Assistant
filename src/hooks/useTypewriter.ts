import { useEffect, useLayoutEffect, useState } from 'react';

/** Type out text; done flips false→true only after a full pass. */
export function useTypewriter(text: string, active: boolean, cps = 38) {
  const [shown, setShown] = useState('');
  const [done, setDone] = useState(true);

  // Sync reset before paint so the UI never flashes the full prior reply
  useLayoutEffect(() => {
    if (!active) {
      setShown(text);
      setDone(true);
      return;
    }
    if (!text) {
      setShown('');
      setDone(true);
      return;
    }
    setShown('');
    setDone(false);
  }, [text, active]);

  useEffect(() => {
    if (!active || !text) return;
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) {
        window.clearInterval(id);
        setDone(true);
      }
    }, Math.max(16, 1000 / cps));
    return () => window.clearInterval(id);
  }, [text, active, cps]);

  return { shown, done };
}
