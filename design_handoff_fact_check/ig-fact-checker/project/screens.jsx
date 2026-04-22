// screens.jsx — Fact Check screens across 3 aesthetic directions × light/dark
// Directions: A=Lab (mono), B=Editorial (serif), C=Calm (iOS system)
// States: processing | verdict (false/mostly_false/mostly_accurate/accurate/unverified) | error

// ─── Shared content fixtures ───────────────────────────────────────────
const SAMPLE = {
  false: {
    verdict: 'FALSE',
    verdictWord: 'False',
    tone: 'false',
    confidence: 94,
    claim: 'Drinking celery juice on an empty stomach cures autoimmune diseases by flushing "viral toxins" from the liver.',
    author: '@wellness.daily',
    kind: 'Reel · 28 sec',
    transcript: '"...and within two weeks of sixteen ounces of celery juice every single morning, my Hashimoto\'s was completely gone. Doctors don\'t want you to know this."',
    tldr: 'No peer-reviewed evidence supports celery juice curing any autoimmune condition. The "viral toxins" framing originates from a single non-medical author and is rejected by rheumatology and hepatology bodies.',
    sources: [
      { title: 'Celery Juice: What the Evidence Says', domain: 'mayoclinic.org' },
      { title: 'Detox Diets: Do They Work?', domain: 'nih.gov' },
      { title: 'Autoimmune Disease Management Guidelines', domain: 'rheumatology.org' },
      { title: 'Fact Check: Celery Juice Miracle Claims', domain: 'healthfeedback.org' },
      { title: 'The Medical Medium Phenomenon', domain: 'theatlantic.com' },
    ],
  },
  mostly_false: {
    verdict: 'MOSTLY FALSE',
    verdictWord: 'Mostly false',
    tone: 'mostly_false',
    confidence: 81,
    claim: 'Einstein failed math as a student before becoming a physicist.',
    author: '@big.brain.energy',
    kind: 'Reel · 18 sec',
    transcript: '"Einstein literally failed math class — so next time someone tells you you\'re bad at math, remember that."',
    tldr: 'Largely false. Einstein mastered calculus by age 15 and consistently excelled in mathematics. The myth stems from a misread Swiss grading scale where 6, not 1, was the highest mark. He did fail a single entrance exam in non-math subjects.',
    sources: [
      { title: 'Einstein Myths: Did He Fail Math?', domain: 'snopes.com' },
      { title: 'Einstein Archives — Academic Record', domain: 'albert-einstein.org' },
      { title: 'The Grading Scale Confusion', domain: 'scientificamerican.com' },
      { title: 'Einstein: His Life and Universe', domain: 'princeton.edu' },
    ],
  },
  mostly_accurate: {
    verdict: 'MOSTLY ACCURATE',
    verdictWord: 'Mostly accurate',
    tone: 'mostly_accurate',
    confidence: 88,
    claim: 'The Great Wall of China is visible from space.',
    author: '@history.unfiltered',
    kind: 'Post · Image',
    transcript: null,
    tldr: 'Mostly true with caveats. From low-Earth orbit the Wall is faintly visible under ideal lighting, alongside highways and cities. From the Moon, no man-made structure is visible — the common "only" framing is the part that doesn\'t hold.',
    sources: [
      { title: 'Is the Great Wall Visible from Space?', domain: 'nasa.gov' },
      { title: 'Chinese Astronaut Yang Liwei Comments', domain: 'scientificamerican.com' },
      { title: 'Myths About Space Observation', domain: 'esa.int' },
    ],
  },
  accurate: {
    verdict: 'ACCURATE',
    verdictWord: 'Accurate',
    tone: 'accurate',
    confidence: 97,
    claim: 'Octopuses have three hearts and blue, copper-based blood.',
    author: '@deep.sea.daily',
    kind: 'Reel · 14 sec',
    transcript: '"Octopuses have three hearts — two pump blood through the gills, one pumps it through the rest of the body. Their blood is blue because it uses copper instead of iron."',
    tldr: 'Confirmed. Octopuses possess two branchial hearts and one systemic heart, and their blood contains hemocyanin — a copper-based respiratory pigment that appears blue when oxygenated.',
    sources: [
      { title: 'Cephalopod Circulatory Biology', domain: 'nationalgeographic.com' },
      { title: 'Hemocyanin in Marine Invertebrates', domain: 'nih.gov' },
      { title: 'Octopus Physiology Overview', domain: 'mbari.org' },
    ],
  },
  unverified: {
    verdict: "CAN'T VERIFY",
    verdictWord: "Can't verify",
    tone: 'unverified',
    confidence: null,
    claim: 'A specific personal health outcome attributed to an unnamed supplement regimen.',
    author: '@morning.rituals',
    kind: 'Reel · 45 sec',
    transcript: '"I started taking these three things every morning and I\'ve never felt better in my life, honestly you guys have to try it."',
    tldr: 'No specific, testable claim was made. The reel describes a subjective personal experience without naming products, dosages, or measurable outcomes.',
    sources: [],
  },
};

// ─── Step list for processing ─────────────────────────────────────────
const STEPS_REEL = [
  'Fetching post data',
  'Extracting frames',
  'Transcribing audio',
  'Searching the web',
  'Cross-referencing sources',
  'Writing verdict',
];

// ─── Tone color tokens per direction ──────────────────────────────────
const TONES = {
  A: { // Clinical Lab — desaturated
    light: {
      false:           { fg: '#8a1a1a', bg: '#fbe9e9', ink: '#3a0a0a', rule: '#c94444' },
      mostly_false:    { fg: '#8a3a16', bg: '#fbe5da', ink: '#3a1708', rule: '#d36a3a' },
      mostly_accurate: { fg: '#4a6a1f', bg: '#eff4df', ink: '#1f2c0b', rule: '#8ab03a' },
      accurate:        { fg: '#1f5d33', bg: '#e4f1e8', ink: '#0c2a15', rule: '#3d8a5a' },
      unverified:      { fg: '#3d4450', bg: '#ececee', ink: '#15181d', rule: '#6b7280' },
    },
    dark: {
      false:           { fg: '#ff7a7a', bg: '#2a1313', ink: '#ffd7d7', rule: '#d94848' },
      mostly_false:    { fg: '#ff9168', bg: '#2a1810', ink: '#fbdbc6', rule: '#d8683c' },
      mostly_accurate: { fg: '#c6e27a', bg: '#1a2010', ink: '#e2efc2', rule: '#92b64a' },
      accurate:        { fg: '#7fd79a', bg: '#112618', ink: '#cfeedb', rule: '#4ba76b' },
      unverified:      { fg: '#9aa3b2', bg: '#181a1f', ink: '#c8cdd6', rule: '#5b6170' },
    },
  },
  B: { // Editorial — rich, classical
    light: {
      false:           { fg: '#8c1111', bg: '#f5e4de', ink: '#2a0707', rule: '#8c1111' },
      mostly_false:    { fg: '#9b3b12', bg: '#f4ddce', ink: '#2d1105', rule: '#9b3b12' },
      mostly_accurate: { fg: '#5a7118', bg: '#eaefd6', ink: '#1f280a', rule: '#5a7118' },
      accurate:        { fg: '#1d4f2a', bg: '#dfe9d9', ink: '#0f2210', rule: '#1d4f2a' },
      unverified:      { fg: '#3d3a36', bg: '#ebe7de', ink: '#1a1814', rule: '#3d3a36' },
    },
    dark: {
      false:           { fg: '#e47b6a', bg: '#231512', ink: '#f3d6cb', rule: '#e47b6a' },
      mostly_false:    { fg: '#e49670', bg: '#251810', ink: '#f0dacb', rule: '#e49670' },
      mostly_accurate: { fg: '#bccf7a', bg: '#1b1f12', ink: '#e0e8c8', rule: '#bccf7a' },
      accurate:        { fg: '#92c28a', bg: '#131f15', ink: '#d6e6cf', rule: '#92c28a' },
      unverified:      { fg: '#b0a89c', bg: '#1a1814', ink: '#ddd5c6', rule: '#b0a89c' },
    },
  },
  C: { // Calm System — iOS-like
    light: {
      false:           { fg: '#ffffff', bg: '#FF3B30', ink: '#1c1c1e', accent: '#FF3B30' },
      mostly_false:    { fg: '#ffffff', bg: '#FF6B35', ink: '#1c1c1e', accent: '#FF6B35' },
      mostly_accurate: { fg: '#ffffff', bg: '#8FC13E', ink: '#1c1c1e', accent: '#6FA524' },
      accurate:        { fg: '#ffffff', bg: '#34C759', ink: '#1c1c1e', accent: '#34C759' },
      unverified:      { fg: '#ffffff', bg: '#8E8E93', ink: '#1c1c1e', accent: '#8E8E93' },
    },
    dark: {
      false:           { fg: '#ffffff', bg: '#FF453A', ink: '#ffffff', accent: '#FF453A' },
      mostly_false:    { fg: '#ffffff', bg: '#FF7A45', ink: '#ffffff', accent: '#FF7A45' },
      mostly_accurate: { fg: '#ffffff', bg: '#9FCE4E', ink: '#ffffff', accent: '#9FCE4E' },
      accurate:        { fg: '#ffffff', bg: '#30D158', ink: '#ffffff', accent: '#30D158' },
      unverified:      { fg: '#ffffff', bg: '#98989F', ink: '#ffffff', accent: '#98989F' },
    },
  },
};

// Page-level background / ink colors per direction
const PAGE = {
  A: {
    light: { bg: '#f6f5f2', ink: '#111418', muted: '#6c717a', line: '#d9d7d1', card: '#ffffff', cardLine: '#e6e3dc' },
    dark:  { bg: '#0d0e10', ink: '#e9ebef', muted: '#8a8f99', line: '#23252a', card: '#14161a', cardLine: '#23252a' },
  },
  B: {
    light: { bg: '#f3ece1', ink: '#1a1510', muted: '#6d6356', line: '#c9bfae', card: '#faf5ea', cardLine: '#d8cdb9' },
    dark:  { bg: '#13110d', ink: '#ede4d1', muted: '#9c9280', line: '#2c2822', card: '#1a1712', cardLine: '#2c2822' },
  },
  C: {
    light: { bg: '#f2f2f7', ink: '#1c1c1e', muted: '#8e8e93', line: 'rgba(60,60,67,0.12)', card: '#ffffff', cardLine: 'rgba(60,60,67,0.10)' },
    dark:  { bg: '#000000', ink: '#ffffff', muted: '#8e8e93', line: 'rgba(84,84,88,0.35)', card: '#1c1c1e', cardLine: 'rgba(84,84,88,0.30)' },
  },
};

// ─── small helpers ────────────────────────────────────────────────────
const clsx = (...a) => a.filter(Boolean).join(' ');

// Done button — top right
function DoneButton({ dir, theme }) {
  const p = PAGE[dir][theme];
  if (dir === 'B') {
    return (
      <div style={{
        position: 'absolute', top: 60, right: 20, zIndex: 5,
        fontFamily: '"Instrument Serif", "Georgia", serif',
        fontSize: 19, color: p.ink, letterSpacing: 0.2,
        fontStyle: 'italic',
      }}>Done</div>
    );
  }
  if (dir === 'A') {
    return (
      <div style={{
        position: 'absolute', top: 62, right: 20, zIndex: 5,
        fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
        fontSize: 12, color: p.ink, letterSpacing: 1.5,
        textTransform: 'uppercase', fontWeight: 500,
      }}>Done</div>
    );
  }
  // C
  return (
    <div style={{
      position: 'absolute', top: 60, right: 20, zIndex: 5,
      fontFamily: '-apple-system, "SF Pro Text", system-ui',
      fontSize: 17, color: '#007AFF', fontWeight: 600,
    }}>Done</div>
  );
}

// Header bar title (Quick Look header feel)
function HeaderTitle({ dir, theme, title = 'Fact Check' }) {
  const p = PAGE[dir][theme];
  const base = { position: 'absolute', top: 58, left: 0, right: 0, textAlign: 'center', zIndex: 4, color: p.ink };
  if (dir === 'A') return (
    <div style={{ ...base, fontFamily: '"IBM Plex Mono", ui-monospace, monospace', fontSize: 11, letterSpacing: 2.4, textTransform: 'uppercase', fontWeight: 500, top: 63 }}>
      FACT · CHECK
    </div>
  );
  if (dir === 'B') return (
    <div style={{ ...base, fontFamily: '"Instrument Serif", Georgia, serif', fontSize: 22, letterSpacing: 0.2, fontStyle: 'italic', top: 56 }}>
      Fact Check
    </div>
  );
  return (
    <div style={{ ...base, fontFamily: '-apple-system, "SF Pro Text", system-ui', fontSize: 17, fontWeight: 600, top: 60 }}>
      Fact Check
    </div>
  );
}

Object.assign(window, { SAMPLE, STEPS_REEL, TONES, PAGE, DoneButton, HeaderTitle, clsx });
