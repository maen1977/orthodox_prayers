import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

const TEAM_AR = {
  Spain: 'إسبانيا',
  France: 'فرنسا',
  Argentina: 'الأرجنتين',
  England: 'إنجلترا',
};

const OFFICIAL_FIXTURES = {
  M101: { team1: 'Spain', team2: 'France', score: [2, 0], stage: 'Semi-finals' },
  M102: { team1: 'Argentina', team2: 'England', score: [2, 1], stage: 'Semi-finals' },
  M103: { team1: 'France', team2: 'England', score: null, stage: 'Third-place play-off' },
  M104: { team1: 'Spain', team2: 'Argentina', score: null, stage: 'Final' },
};

const TARGET_FILES = [
  { relative: 'public/worldcup-2026/matches.json', required: true },
  { relative: 'public/worldcup-2026/bracket.json', required: true },
  { relative: 'public/worldcup-2026/knockout-live.json', required: false },
];

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function hasMatchShape(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  return [
    'team1', 'team2', 'team1_ar', 'team2_ar',
    'home_team', 'away_team', 'homeTeam', 'awayTeam',
    'home_score', 'away_score', 'stage', 'round', 'kickoff_utc',
  ].some((key) => Object.hasOwn(value, key));
}

function getMatchId(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  for (const key of ['id', 'match_id', 'matchId', 'match']) {
    const candidate = value[key];
    if (typeof candidate === 'string' && /^M\d{3}$/.test(candidate)) {
      if (key !== 'match' || hasMatchShape(value)) return candidate;
    }
  }
  return null;
}

function setExistingOrStandard(record, key, value, always = false) {
  if (always || Object.hasOwn(record, key)) record[key] = value;
}

function setTeamObject(target, english, arabic) {
  if (!target || typeof target !== 'object' || Array.isArray(target)) return;
  for (const key of ['name', 'team', 'displayName', 'display_name', 'shortName', 'short_name']) {
    if (Object.hasOwn(target, key)) target[key] = english;
  }
  for (const key of ['name_ar', 'team_ar', 'displayNameAr', 'display_name_ar']) {
    if (Object.hasOwn(target, key)) target[key] = arabic;
  }
}

function clearFutureScore(record) {
  for (const key of [
    'home_score', 'away_score', 'team1_score', 'team2_score',
    'score1', 'score2', 'homeScore', 'awayScore',
  ]) {
    if (Object.hasOwn(record, key)) record[key] = null;
  }

  if (Object.hasOwn(record, 'result')) record.result = null;
  if (Object.hasOwn(record, 'winner')) record.winner = null;
  if (Object.hasOwn(record, 'winner_team')) record.winner_team = null;
  if (Object.hasOwn(record, 'winnerTeam')) record.winnerTeam = null;

  if (record.score && typeof record.score === 'object' && !Array.isArray(record.score)) {
    for (const key of ['current', 'ft', 'full_time', 'fullTime']) {
      if (Object.hasOwn(record.score, key)) record.score[key] = null;
    }
    for (const key of ['home', 'away', 'home_score', 'away_score']) {
      if (Object.hasOwn(record.score, key)) record.score[key] = null;
    }
  }
}

function applyFinishedScore(record, home, away, winner) {
  setExistingOrStandard(record, 'home_score', home, true);
  setExistingOrStandard(record, 'away_score', away, true);
  setExistingOrStandard(record, 'team1_score', home);
  setExistingOrStandard(record, 'team2_score', away);
  setExistingOrStandard(record, 'score1', home);
  setExistingOrStandard(record, 'score2', away);
  setExistingOrStandard(record, 'homeScore', home);
  setExistingOrStandard(record, 'awayScore', away);

  if (Object.hasOwn(record, 'result')) record.result = [home, away];
  if (Object.hasOwn(record, 'winner')) record.winner = winner;
  if (Object.hasOwn(record, 'winner_team')) record.winner_team = winner;
  if (Object.hasOwn(record, 'winnerTeam')) record.winnerTeam = winner;

  if (!record.score || typeof record.score !== 'object' || Array.isArray(record.score)) {
    record.score = {};
  }
  record.score.current = [home, away];
  record.score.ft = [home, away];
  record.score.source = 'manual-official-final-four-fix';
  record.score.status_detail = 'STATUS_FULL_TIME';
  record.score.checked_at = new Date().toISOString();

  record.status = 'finished';
  record.score_source = 'manual-official-final-four-fix';
  record.live_status_detail = 'STATUS_FULL_TIME';
}

function applyFixture(record, id, fixture) {
  const team1Ar = TEAM_AR[fixture.team1];
  const team2Ar = TEAM_AR[fixture.team2];

  record.team1 = fixture.team1;
  record.team2 = fixture.team2;
  record.team1_ar = team1Ar;
  record.team2_ar = team2Ar;

  setExistingOrStandard(record, 'home_team', fixture.team1);
  setExistingOrStandard(record, 'away_team', fixture.team2);
  setExistingOrStandard(record, 'home_team_ar', team1Ar);
  setExistingOrStandard(record, 'away_team_ar', team2Ar);
  setExistingOrStandard(record, 'homeTeam', fixture.team1);
  setExistingOrStandard(record, 'awayTeam', fixture.team2);
  setExistingOrStandard(record, 'homeTeamAr', team1Ar);
  setExistingOrStandard(record, 'awayTeamAr', team2Ar);

  setTeamObject(record.home, fixture.team1, team1Ar);
  setTeamObject(record.away, fixture.team2, team2Ar);

  if (fixture.score) {
    applyFinishedScore(record, fixture.score[0], fixture.score[1], fixture.team1);
  } else {
    clearFutureScore(record);
    record.status = 'scheduled';
    if (Object.hasOwn(record, 'live_status_detail')) record.live_status_detail = 'STATUS_SCHEDULED';
  }

  record.manual_override = true;
  record.manual_override_key = `official-final-four-${id}`;
  record.manual_override_at = new Date().toISOString();

  if (typeof record.search_text === 'string') {
    const prefix = `${fixture.team1} ${fixture.team2} ${team1Ar} ${team2Ar}`;
    record.search_text = `${prefix} ${record.search_text}`.replace(/\s+/g, ' ').trim();
  }
}

function walk(value, visitor) {
  if (Array.isArray(value)) {
    for (const item of value) walk(item, visitor);
    return;
  }
  if (!value || typeof value !== 'object') return;
  visitor(value);
  for (const child of Object.values(value)) walk(child, visitor);
}

function patchDocument(document, relativePath) {
  const counts = Object.fromEntries(Object.keys(OFFICIAL_FIXTURES).map((id) => [id, 0]));

  walk(document, (record) => {
    const id = getMatchId(record);
    if (!id || !OFFICIAL_FIXTURES[id]) return;
    applyFixture(record, id, OFFICIAL_FIXTURES[id]);
    counts[id] += 1;
  });

  if (document.metadata && typeof document.metadata === 'object' && !Array.isArray(document.metadata)) {
    document.metadata.final_four_official_fix = {
      enabled: true,
      applied_at: new Date().toISOString(),
      source: 'manual verified correction',
      fixtures: OFFICIAL_FIXTURES,
    };
  }

  return { relativePath, counts, total: Object.values(counts).reduce((sum, n) => sum + n, 0) };
}

const results = [];
for (const target of TARGET_FILES) {
  const filePath = path.join(repoRoot, target.relative);
  if (!fs.existsSync(filePath)) {
    if (target.required) throw new Error(`Required file not found: ${target.relative}`);
    results.push({ relativePath: target.relative, skipped: true, reason: 'file-not-found' });
    continue;
  }

  const document = readJson(filePath);
  const result = patchDocument(document, target.relative);

  if (target.required) {
    const missing = Object.entries(result.counts).filter(([, count]) => count === 0).map(([id]) => id);
    if (missing.length) {
      throw new Error(`${target.relative}: missing match records ${missing.join(', ')}`);
    }
  }

  writeJson(filePath, document);
  results.push(result);
}

const statusPath = path.join(repoRoot, 'public/worldcup-2026/final-four-correction-status.json');
writeJson(statusPath, {
  ok: true,
  corrected_at: new Date().toISOString(),
  timezone: 'Asia/Amman',
  fixtures: OFFICIAL_FIXTURES,
  files: results,
  note_ar: 'تثبيت نصف النهائي: إسبانيا 2-0 فرنسا، الأرجنتين 2-1 إنجلترا؛ المركز الثالث فرنسا ضد إنجلترا؛ النهائي إسبانيا ضد الأرجنتين.',
});

console.log(JSON.stringify({ ok: true, results }, null, 2));
