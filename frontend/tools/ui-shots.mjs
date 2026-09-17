/**
 * Visual harness for the ported UI.
 *
 * The screens were rebuilt against the stylesheets the Jinja app ships
 * (`src/styles/legacy/`), and the only way to know a port landed is to look at
 * it. This serves the built app, answers every API call from a fixture, and
 * writes one screenshot per route.
 *
 *   npm run build && node tools/ui-shots.mjs [route ...]
 *
 * Shots land in `.ui-shots/`. It is a local tool, not a CI gate: it asserts
 * nothing, it just makes the pages visible.
 */
import { chromium } from "playwright";
import { existsSync, mkdirSync } from "node:fs";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = join(ROOT, "dist");
const OUT = join(ROOT, ".ui-shots");
const PORT = Number(process.env.UI_SHOTS_PORT ?? 4319);
const localChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const executablePath = process.env.PLAYWRIGHT_CHROME_PATH ?? (existsSync(localChrome) ? localChrome : undefined);

const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".woff2": "font/woff2",
};

const student = {
  id: "11111111-1111-1111-1111-111111111111",
  actor_type: "student", email: "taylor@example.com", display_name: "Taylor Reed",
  is_active: true, is_verified: true,
};
const recruiter = { ...student, id: "22222222-2222-2222-2222-222222222222", actor_type: "recruiter", email: "hiring@acme.test", display_name: "Acme Hiring" };

const iso = "2026-02-01T10:00:00Z";
const resource = (id, title, category, locked = false) => ({
  id, title, description: `${title} — a short course that gets you to the point.`,
  category, icon: "📘", level: "Beginner", tags: ["career", category.toLowerCase()],
  estimated_duration_minutes: 45, external_url: null, is_published: true, is_locked: locked,
  created_at: iso, updated_at: iso, modules: [],
});
const roadmap = (slug, title, popularity) => ({
  slug, title, description: `Become a ${title} with a week-by-week plan.`, difficulty: "Intermediate",
  duration_weeks_min: 8, duration_weeks_max: 12, popularity, is_saved: false,
  total_tasks: 24, completed_tasks: 6, overall_progress_percent: 25,
});

const FIXTURES = new Map(Object.entries({
  "/api/v1/auth/session": { actor: student, actors: [student, recruiter], csrf_token: "shots" },
  "/api/v1/dashboard/student": {
    user: { first_name: "Taylor", nickname: "taylor", email: student.email },
    stats: { overall_progress: 62, total_applications: 14, interviews_scheduled: 3, offers_received: 1 },
    progress: { resume: 80, linkedin: 55, interview_prep: 40, portfolio: 20 },
    application_breakdown: { applied: 14, in_review: 5, interviews: 3, offers: 1 },
    resources: [
      { title: "ATS-Friendly Resume Templates", icon: "📄" },
      { title: "LinkedIn Headline Examples", icon: "💼" },
      { title: "Interview Question Bank", icon: "🎯" },
      { title: "Portfolio Checklist", icon: "🎨" },
    ],
    resource_navigation: { resume: "/resources", linkedin: "/resources", interview_prep: "/resources", portfolio: "/resources" },
  },
  "/api/v1/resources": [
    resource("r1", "Resume Foundations", "Career"),
    resource("r2", "LinkedIn That Gets Replies", "Professional"),
    resource("r3", "Behavioural Interviews", "Learning"),
    resource("r4", "Salary Negotiation", "Career", true),
  ],
  "/api/v1/roadmaps": [
    roadmap("web-developer", "Web Developer", 412),
    roadmap("data-scientist", "Data Scientist", 318),
    roadmap("product-manager", "Product Manager", 260),
    roadmap("ux-designer", "UX Designer", 143),
  ],
  "/api/v1/me/roadmaps": [{ saved_at: iso, roadmap: { ...roadmap("web-developer", "Web Developer", 412), is_saved: true } }],
  "/api/v1/jobs/board": [
    { id: "j1", company_id: "c1", title: "Junior Frontend Developer", company_name: "Northwind Studio", location: "Toronto, ON", is_active: true, created_at: iso, updated_at: iso },
    { id: "j2", company_id: "c2", title: "Data Analyst Intern", company_name: "Lakeshore Analytics", location: "Niagara Falls, ON", is_active: true, created_at: iso, updated_at: iso },
    { id: "j3", company_id: "c3", title: "Product Support Associate", company_name: "Bluepeak", location: "Remote", is_active: true, created_at: iso, updated_at: iso },
  ],
  "/api/v1/applications/eligible-resumes": [
    { id: "res1", original_filename: "taylor-reed-resume.pdf", created_at: iso, overall_score: 9, approved_at: iso, is_latest: true },
  ],
  "/api/v1/applications/page": {
    items: [
      { id: "a1", job_title: "Junior Frontend Developer", company_name: "Northwind Studio", status: "in_review", application_date: iso, notes: null, selected_interview_slot: null, available_interview_slots: [] },
      { id: "a2", job_title: "Data Analyst Intern", company_name: "Lakeshore Analytics", status: "interview", application_date: iso, notes: null, selected_interview_slot: { id: "s1", starts_at: iso, ends_at: iso }, available_interview_slots: [] },
    ],
    has_more: false,
    next_cursor: null,
  },
}));

const json = (route, body, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

const server = createServer(async (request, response) => {
  const path = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
  const candidate = join(DIST, normalize(path));
  const file = existsSync(candidate) && extname(candidate) ? candidate : join(DIST, "index.html");
  response.writeHead(200, { "content-type": MIME[extname(file)] ?? "application/octet-stream" });
  response.end(await readFile(file));
});

const ROUTES = process.argv.slice(2).length > 0 ? process.argv.slice(2) : [
  "/", "/about", "/login", "/register", "/dashboard", "/resources", "/roadmaps",
];

mkdirSync(OUT, { recursive: true });
await new Promise((resolve) => server.listen(PORT, resolve));
const browser = await chromium.launch({ executablePath, headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });

// `/login`, `/register` and `/admin/login` are behind `RequireAnonymous`, so a
// signed-in session would bounce the shot straight to the dashboard.
const ANONYMOUS = new Set(["/login", "/register", "/admin/login"]);
let anonymous = false;

await page.route("**/api/v1/**", (route) => {
  const path = new URL(route.request().url()).pathname;
  if (anonymous && path === "/api/v1/auth/session") {
    return json(route, { error: { code: "unauthorized", message: "Not signed in", details: null, request_id: "shots" } }, 401);
  }
  const fixture = FIXTURES.get(path);
  if (fixture !== undefined) return json(route, fixture);
  return json(route, { error: { code: "not_found", message: `No fixture for ${path}`, details: null, request_id: "shots" } }, 404);
});

for (const target of ROUTES) {
  anonymous = ANONYMOUS.has(target);
  await page.goto(`http://127.0.0.1:${PORT}${target}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  const name = target === "/" ? "home" : target.replace(/^\//, "").replaceAll("/", "-");
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
  console.log(`shot ${target} -> .ui-shots/${name}.png`);
}

await browser.close();
server.close();
