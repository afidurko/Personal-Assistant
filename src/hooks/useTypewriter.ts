import { useEffect, useState } from 'react';

/** Type out text; optional sync to speech duration. */
export function useTypewriter(text: string, active: boolean, cps = 38) {
  const [shown, setShown] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
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
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) {
        window.clearInterval(id);
        setDone(true);
      }
    }, Math.max(12, 1000 / cps));
    return () => window.clearInterval(id);
  }, [text, active, cps]);

  return { shown, done };
}
