import { chromium } from "playwright";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";

const localChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const executablePath = process.env.PLAYWRIGHT_CHROME_PATH ?? (existsSync(localChrome) ? localChrome : undefined);
const base = process.env.ADMIN_QA_BASE_URL ?? "http://127.0.0.1:4173";
const actor = {
  id: "7674de34-7a8c-40c2-bcdc-81d14ac36473",
  actor_type: "student",
  email: "baseline-admin@example.com",
  display_name: "Baseline Admin",
  is_active: true,
  is_verified: true,
};
let users = [
  { id: actor.id, email: actor.email, first_name: "Baseline", last_name: "Admin", nickname: "baseline_admin", is_active: true, is_superuser: true, is_verified: true },
  { id: "09e52b5d-3781-44a2-9b87-feae1a341adf", email: "student@example.com", first_name: "Taylor", last_name: "Student", nickname: "taylor", is_active: true, is_superuser: false, is_verified: true },
];
let resources = [{
  id: "3dd926b0-77c3-41cc-a7f6-f1a03b1bb20d", title: "Baseline Course", description: "Visual fixture", category: "career", icon: "📘", level: "beginner", tags: ["baseline"], estimated_duration_minutes: 45, external_url: null, is_published: true, is_locked: false, created_at: "2026-01-05T12:00:00Z", updated_at: "2026-01-05T12:00:00Z",
}];
const observedAdminRequests = [];

const json = (route, status, body) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
async function installApi(page, { forbidden = false } = {}) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.startsWith("/api/v1/admin/")) observedAdminRequests.push(`${request.method()} ${path}`);
    if (path === "/api/v1/auth/session") return json(route, 200, { actor, actors: [actor], csrf_token: "qa" });
    if (path === "/api/v1/admin/stats") {
      if (forbidden) return json(route, 403, { error: { code: "forbidden", message: "Admin privileges required.", details: null, request_id: "qa-403" } });
      return json(route, 200, { total_users: users.length, total_companies: 1, total_communities: 1, total_resources: resources.length, total_jobs: 1, total_applications: 1, total_resumes: 1, total_questionnaires: 1, recent_users: 0 });
    }
    if (path === "/api/v1/admin/users" && request.method() === "GET") return json(route, 200, { items: users, users, page: 1, page_size: 20, total: users.length });
    if (path.startsWith("/api/v1/admin/users/") && request.method() === "PATCH") {
      const id = path.split("/").at(-1); const patch = request.postDataJSON();
      users = users.map((user) => user.id === id ? { ...user, ...patch } : user);
      return json(route, 200, users.find((user) => user.id === id));
    }
    if (path === "/api/v1/admin/resources" && request.method() === "GET") return json(route, 200, { items: resources, resources, page: 1, page_size: 20, total: resources.length });
    if (path === "/api/v1/admin/resources" && request.method() === "POST") {
      const payload = request.postDataJSON();
      resources = [...resources, { ...payload, id: "new-resource", created_at: new Date().toISOString(), updated_at: new Date().toISOString() }];
      return json(route, 201, { id: "new-resource", title: payload.title, is_published: payload.is_published, is_locked: payload.is_locked });
    }
    if (path === "/api/v1/admin/resource-files" && request.method() === "POST") return json(route, 201, { file_key: "resources/lesson.txt", file_url: "https://files.invalid/lesson.txt", original_filename: "lesson.txt", content_type: "text/plain" });
    if (path.startsWith("/api/v1/admin/resources/") && request.method() === "PATCH") {
      const id = path.split("/").at(-1); const patch = request.postDataJSON();
      resources = resources.map((resource) => resource.id === id ? { ...resource, ...patch } : resource);
      const resource = resources.find((item) => item.id === id);
      return json(route, 200, { id, title: resource.title, is_published: resource.is_published, is_locked: resource.is_locked });
    }
    return json(route, 404, { error: { code: "not_found", message: "Not found", details: null, request_id: "qa-404" } });
  });
}

const browser = await chromium.launch({ executablePath, headless: true });
const consoleErrors = [];
try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await desktop.newPage();
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await installApi(page);
  await page.goto(`${base}/admin`);
  await page.getByText("Total Users").waitFor();
  assert.equal(await page.getByText("Questionnaires").count(), 1);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false);
  await page.screenshot({ path: "/private/tmp/admin-playwright-dashboard.png" });

  await page.getByRole("link", { name: /Users/ }).click();
  await page.getByPlaceholder("Search users…").fill("Taylor");
  assert.equal(await page.locator("tbody tr").count(), 1);
  await page.getByPlaceholder("Search users…").fill("");
  const studentRow = page.locator("tbody tr", { hasText: "student@example.com" });
  await studentRow.getByRole("button", { name: "Deactivate" }).click();
  await studentRow.getByRole("button", { name: "Activate" }).waitFor();

  await page.getByRole("link", { name: /Resources/ }).click();
  await page.getByRole("button", { name: "Unpublish" }).click();
  await page.getByRole("button", { name: "Publish" }).waitFor();
  await page.getByRole("button", { name: "New Resource" }).click();
  assert.equal(await page.evaluate(() => document.body.style.overflow), "hidden");
  await page.getByLabel("Title").fill("Playwright Course");
  await page.getByLabel("Category").fill("career");
  await page.getByLabel("Description").fill("Created through browser controls.");
  await page.getByRole("button", { name: "Add Module" }).click();
  await page.getByLabel("Module title").fill("Module One");
  await page.getByLabel("Lesson title").fill("Lesson One");
  await page.locator('input[type="file"]').setInputFiles({ name: "lesson.txt", mimeType: "text/plain", buffer: Buffer.from("lesson") });
  await page.getByLabel("Resource URL").waitFor();
  assert.equal(await page.getByLabel("Resource URL").inputValue(), "https://files.invalid/lesson.txt");
  await page.getByRole("button", { name: "Save Resource" }).click();
  await page.getByText("Playwright Course").waitFor();
  assert.equal(await page.evaluate(() => document.body.style.overflow), "");
  await page.screenshot({ path: "/private/tmp/admin-playwright-resources.png" });

  const forbiddenPage = await desktop.newPage();
  await installApi(forbiddenPage, { forbidden: true });
  await forbiddenPage.goto(`${base}/admin`);
  await forbiddenPage.getByText("Admin privileges required.").waitFor();
  assert.match(await forbiddenPage.textContent("body"), /qa-403/);
  await desktop.close();

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const mobilePage = await mobile.newPage();
  await installApi(mobilePage);
  await mobilePage.goto(`${base}/admin`);
  await mobilePage.screenshot({ path: "/private/tmp/admin-playwright-mobile-dashboard.png" });
  await mobilePage.getByRole("button", { name: /navigation/i }).click();
  await mobilePage.waitForTimeout(200);
  await mobilePage.screenshot({ path: "/private/tmp/admin-playwright-mobile-menu.png" });
  await mobilePage.getByRole("link", { name: /Resources/ }).click();
  await mobilePage.getByRole("button", { name: "New Resource" }).waitFor();
  await mobilePage.waitForTimeout(200);
  assert.equal(await mobilePage.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false);
  await mobilePage.screenshot({ path: "/private/tmp/admin-playwright-mobile.png" });
  await mobile.close();

  assert.deepEqual(consoleErrors, []);
  const legacyRequests = observedAdminRequests.filter((entry) =>
    entry.includes("/toggle-") || entry.includes("/resources/upload-file") || entry.includes("/admin/jobs"),
  );
  assert.deepEqual(legacyRequests, []);
  console.log(JSON.stringify({ dashboard: true, userSearch: true, userStateCycle: true, resourceStateCycle: true, resourceCreate: true, resourceUpload: true, forbidden: true, mobileNavigation: true, horizontalOverflow: false, legacyRequests: legacyRequests.length }));
} finally {
  await browser.close();
}
