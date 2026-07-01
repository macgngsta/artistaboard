// Vestaboard character-code map, mirrored verbatim from the backend so the
// canvas renders exactly what src/artistaboard/codes.py + preview.py produce.
// The backend's /preview endpoint is the ONLY renderer of scene documents; this
// map is used solely to turn its `characters: number[][]` output into glyphs.

export const MIN_CODE = 0;
export const MAX_CODE = 71;

// 0 = blank; 1-26 = A-Z; 27-35 = 1-9; 36 = 0; punctuation per the backend table.
export const CODE_TO_CHAR: Record<number, string> = (() => {
  const m: Record<number, string> = { 0: " " };
  for (let i = 1; i <= 26; i++) m[i] = String.fromCharCode(64 + i); // A-Z
  for (let i = 27; i <= 35; i++) m[i] = String(i - 26); // 1-9
  m[36] = "0";
  const punctuation: Record<number, string> = {
    37: "!", 38: "@", 39: "#", 40: "$", 41: "(", 42: ")",
    44: "-", 46: "+", 47: "&", 48: "=", 49: ";", 50: ":",
    52: "'", 53: '"', 54: "%", 55: ",", 56: ".", 59: "/",
    60: "?", 62: "°",
  };
  Object.assign(m, punctuation);
  // 43, 45, 51, 57, 58, 61 are unmapped -> rendered as blank.
  return m;
})();

// Color chips 63-71. Hex are the xterm-256 equivalents of the backend's ANSI
// indices (preview.py); FILLED renders like white.
export const COLOR_CODES: Record<number, { name: string; hex: string }> = {
  63: { name: "red", hex: "#ff0000" },
  64: { name: "orange", hex: "#ff8700" },
  65: { name: "yellow", hex: "#ffff00" },
  66: { name: "green", hex: "#00ff00" },
  67: { name: "blue", hex: "#0000ff" },
  68: { name: "violet", hex: "#8700ff" },
  69: { name: "white", hex: "#ffffff" },
  70: { name: "black", hex: "#000000" },
  71: { name: "filled", hex: "#ffffff" },
};

// Named colors accepted by the backend for a render[REGION].color literal.
export const COLOR_NAME_TO_CODE: Record<string, number> = {
  blank: 0, red: 63, orange: 64, yellow: 65, green: 66,
  blue: 67, violet: 68, purple: 68, white: 69, black: 70, filled: 71,
};

export function isColorCode(code: number): boolean {
  return code >= 63 && code <= 71;
}

export function charForCode(code: number): string {
  return CODE_TO_CHAR[code] ?? " ";
}

export function colorForCode(code: number): string | null {
  return COLOR_CODES[code]?.hex ?? null;
}
