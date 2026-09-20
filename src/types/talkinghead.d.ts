declare module '@met4citizen/talkinghead' {
  export class TalkingHead {
    constructor(node: HTMLElement, opt?: Record<string, unknown>);
    lipsync: Record<string, unknown>;
    audioCtx: AudioContext;
    showAvatar(
      avatar: Record<string, unknown>,
      onprogress?: (ev: ProgressEvent) => void,
    ): Promise<void>;
    speakAudio(
      audio: {
        audio?: AudioBuffer | Int16Array[];
        words?: string[];
        wtimes?: number[];
        wdurations?: number[];
        visemes?: string[];
        vtimes?: number[];
        vdurations?: number[];
      },
      opt?: Record<string, unknown>,
      onsubtitles?: (s: string) => void,
    ): void;
    speakText(
      text: string,
      opt?: Record<string, unknown>,
      onsubtitles?: (s: string) => void,
    ): void;
    setMood(mood: string): void;
    stopSpeaking(): void;
    stop(): void;
  }
}

declare module '@met4citizen/talkinghead/modules/lipsync-en.mjs' {
  export class LipsyncEn {
    preProcessText(s: string): string;
    wordsToVisemes(word: string): {
      visemes: string[];
      times: number[];
      durations: number[];
    };
  }
}
