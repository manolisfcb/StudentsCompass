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
  "/api/v1/users/me": {
    id: student.id, email: student.email, first_name: "Taylor", last_name: "Reed", nickname: "taylor",
    phone: "+1 905 555 0142", sex: "Prefer not to say", age: 22, address: "Niagara Falls, ON", is_active: true, is_verified: true, is_superuser: false,
  },
  "/api/v1/questionnaire/profile": {
    completed_at: iso,
    results: [
      { career: "Data Analyst", score: 41 },
      { career: "Product Designer", score: 33 },
      { career: "Frontend Developer", score: 28 },
    ],
  },
  "/api/v1/resumes": [
    { id: "res1", original_filename: "taylor-reed-resume.pdf", view_url: "https://files.invalid/resume.pdf", created_at: iso },
  ],
  "/api/v1/resume-course-audits/attempts": { attempts_remaining: 2, attempts_used: 1 },
  "/api/v1/friends/requests/incoming": [],
  "/api/v1/friends/requests/outgoing": [],
  "/api/v1/friends": [
    { friend: { id: "u9", display_name: "Jordan Blake", email: "jordan@example.com" }, created_at: iso },
  ],
  "/api/v1/communities": [
    { id: "c1", name: "Frontend Study Group", description: "Weekly practice, code review and interview prep.", icon: "💻", member_count: 128, tags: ["react", "css"] },
    { id: "c2", name: "Data Careers", description: "SQL, analytics and the road into data roles.", icon: "📊", member_count: 74, tags: ["sql"] },
    { id: "c3", name: "Newcomers to Canada", description: "Resume norms, references and first-job questions.", icon: "🍁", member_count: 213, tags: [] },
  ],
  "/api/v1/conversations": [
    { id: "cv1", other_user: { id: "u9", display_name: "Jordan Blake" }, unread_count: 2, last_message_preview: "Sounds good — I will send the deck tonight." },
  ],
  "/api/v1/companies/me/dashboard": {
    company: { id: "co1", company_name: "Northwind Studio" },
    current_recruiter: { id: "rc1", first_name: "Sam", last_name: "Okafor", email: "sam@northwind.test", role: "owner" },
    stats: { active_job_postings: 6, total_applications: 48, scheduled_interviews: 7, shortlisted: 12 },
    recent_job_postings: [
      { id: "j1", title: "Junior Frontend Developer", location: "Toronto, ON", application_count: 19, status: "active", status_label: "Active" },
      { id: "j2", title: "Data Analyst Intern", location: "Remote", application_count: 12, status: "inactive", status_label: "Paused" },
    ],
  },
  "/api/v1/admin/stats": {
    total_users: 1284, total_companies: 42, total_communities: 18, total_resources: 36,
    total_jobs: 91, total_applications: 640, total_resumes: 812, total_questionnaires: 517, recent_users: 23,
  },
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

/**
 * Viewports. `--mobile` / `--tablet` shoot one width; the default shoots
 * desktop. The refactor's responsive pass is only meaningful if the harness
 * can actually see a phone — "it works on my 1440px screen" is how the
 * horizontal-overflow bugs got in.
 */
const VIEWPORTS = {
  desktop: { width: 1440, height: 1000 },
  tablet: { width: 834, height: 1112 },
  mobile: { width: 390, height: 844 },
};
const flags = process.argv.slice(2).filter((a) => a.startsWith("--")).map((a) => a.slice(2));
const sizes = flags.filter((f) => f in VIEWPORTS);
const SIZES = sizes.length > 0 ? sizes : ["desktop"];

const ROUTES = process.argv.slice(2).filter((a) => !a.startsWith("--")).length > 0
  ? process.argv.slice(2).filter((a) => !a.startsWith("--"))
  : [
  "/", "/about", "/login", "/register", "/dashboard", "/resources", "/roadmaps",
  "/jobs", "/jobs/applications", "/profile", "/community", "/messages", "/career-lab",
  "/company", "/admin", "/admin/login",
];

mkdirSync(OUT, { recursive: true });
await new Promise((resolve) => server.listen(PORT, resolve));
const browser = await chromium.launch({ executablePath, headless: true });
const page = await browser.newPage({ viewport: VIEWPORTS.desktop, deviceScaleFactor: 1 });

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

for (const size of SIZES) {
  await page.setViewportSize(VIEWPORTS[size]);
  for (const target of ROUTES) {
    anonymous = ANONYMOUS.has(target);
    await page.goto(`http://127.0.0.1:${PORT}${target}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);

    // Horizontal overflow is invisible in a full-page screenshot — the shot
    // just comes out wider — so it is asserted rather than looked at.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    if (overflow > 0) console.warn(`  ⚠ ${target} [${size}] overflows by ${overflow}px`);

    const base = target === "/" ? "home" : target.replace(/^\//, "").replaceAll("/", "-");
    const name = size === "desktop" ? base : `${base}.${size}`;
    await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
    console.log(`shot ${target} [${size}] -> .ui-shots/${name}.png`);
  }
}

await browser.close();
server.close();
