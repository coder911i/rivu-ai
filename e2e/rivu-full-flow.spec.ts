import { test, expect } from "@playwright/test";

const api = () => process.env.E2E_API_URL || "http://127.0.0.1:8000/api/v1";

test("Rivu full data-refinery flow", async ({ page, request }) => {
  const stamp = Date.now();
  const email = `e2e+${stamp}@rivu.test`;
  const password = "RivuE2E@2026!";
  const username = `e2e_${stamp}`;
  const projectName = `E2E Refinery ${stamp}`;

  // 1. Signup through the real UI.
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Rivu E2E");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // 2. Create a project through the product UI.
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByPlaceholder("Customer Data Refinery").fill(projectName);
  await page.getByRole("button", { name: /Create project/ }).click();
  await expect(page.getByText(projectName)).toBeVisible();

  // 3. Obtain the access token created by the real signup flow.
  const token = await page.evaluate(() => localStorage.getItem("rivu_access_token"));
  expect(token).toBeTruthy();
  const auth = { Authorization: `Bearer ${token}` };

  const projects = await request.get(`${api()}/projects/`, { headers: auth });
  expect(projects.ok()).toBeTruthy();
  const projectBody = await projects.json();
  const project = projectBody.projects.find((p: { name: string }) => p.name === projectName);
  expect(project).toBeTruthy();

  // 4. Upload a deliberately imperfect CSV.
  const csv = [
    "id,name,email",
    "1, Alice ,ALICE@EXAMPLE.COM",
    "1,Alice,alice@example.com",
    "2, Bob ,bob@example.com",
    "3,,bad-email",
  ].join("\n");
  const upload = await request.post(`${api()}/datasets/projects/${project.id}/upload`, {
    headers: auth,
    multipart: {
      file: { name: "e2e-data.csv", mimeType: "text/csv", buffer: Buffer.from(csv) },
      name: "E2E Data",
    },
  });
  expect(upload.status()).toBe(202);
  const uploadBody = await upload.json();
  const datasetId = uploadBody.dataset.id;
  expect(datasetId).toBeTruthy();

  // 4b. Tenant isolation: a second workspace must not read the first dataset.
  const intruderStamp = Date.now();
  const intruder = await request.post(`${api()}/auth/signup`, {
    headers: { "Content-Type": "application/json" },
    data: {
      full_name: "Rivu Isolation Test",
      username: `isolation_${intruderStamp}`,
      email: `isolation+${intruderStamp}@rivu.test`,
      password: "RivuE2E@2026!",
    },
  });
  expect(intruder.status()).toBe(201);
  const intruderBody = await intruder.json();
  const intruderAuth = {
    Authorization: `Bearer ${intruderBody.tokens.access_token}`,
  };

  for (const endpoint of [
    `/datasets/${datasetId}`,
    `/datasets/${datasetId}/profile`,
    `/datasets/${datasetId}/quality`,
    `/reports/${datasetId}/dashboard`,
  ]) {
    const response = await request.get(`${api()}${endpoint}`, { headers: intruderAuth });
    expect(response.status(), `cross-tenant access must be denied for ${endpoint}`).toBe(404);
  }

  // 5. Wait for the real profile/quality worker path to finish.
  let profileResponse;
  for (let i = 0; i < 40; i++) {
    profileResponse = await request.get(`${api()}/datasets/${datasetId}/profile`, { headers: auth });
    if (profileResponse.ok()) break;
    expect([202, 404]).toContain(profileResponse.status());
    await new Promise(r => setTimeout(r, 1500));
  }
  expect(profileResponse?.ok()).toBeTruthy();
  const profile = await profileResponse!.json();
  expect(profile.profile.row_count).toBe(4);
  expect(profile.profile.column_count).toBe(3);

  const qualityResponse = await request.get(`${api()}/datasets/${datasetId}/quality`, { headers: auth });
  expect(qualityResponse.ok()).toBeTruthy();
  const quality = await qualityResponse.json();
  expect(quality.overall_score).toBeGreaterThanOrEqual(0);
  expect(quality.overall_score).toBeLessThanOrEqual(100);

  // 6. Generate an AI transformation plan.
  const planResponse = await request.post(`${api()}/datasets/${datasetId}/ai-plan`, { headers: auth });
  expect(planResponse.ok()).toBeTruthy();
  const plan = await planResponse.json();
  expect(plan.id).toBeTruthy();
  expect(Array.isArray(plan.operations)).toBeTruthy();

  // 7. Preview, explicitly approve, then execute the deterministic transformation.
  const preview = await request.post(`${api()}/datasets/${datasetId}/transform/preview`, {
    headers: { ...auth, "Content-Type": "application/json" },
    data: { plan_id: plan.id },
  });
  expect(preview.ok()).toBeTruthy();

  const approve = await request.post(`${api()}/datasets/${datasetId}/transform/approve`, {
    headers: { ...auth, "Content-Type": "application/json" },
    data: { plan_id: plan.id },
  });
  expect(approve.ok()).toBeTruthy();

  const execute = await request.post(`${api()}/datasets/${datasetId}/transform/execute`, {
    headers: { ...auth, "Content-Type": "application/json" },
    data: { plan_id: plan.id },
  });
  expect(execute.status()).toBe(201);
  const execution = await execute.json();
  expect(execution.run.status).toMatch(/^completed/);
  expect(execution.version.number).toBeGreaterThan(1);
  expect(execution.artifacts.csv.download_url).toBeTruthy();
  expect(execution.artifacts.xlsx.download_url).toBeTruthy();
  expect(execution.artifacts.json.download_url).toBeTruthy();
  expect(execution.artifacts.parquet.download_url).toBeTruthy();

  // 7b. Verify the actual generated bytes, not just metadata.
  const csvArtifact = await request.get(execution.artifacts.csv.download_url);
  expect(csvArtifact.ok()).toBeTruthy();
  const csvBytes = await csvArtifact.body();
  const csvText = csvBytes.toString("utf8");
  expect(csvText).toContain("id,name,email");
  expect(csvText).toContain("alice@example.com");

  const xlsxArtifact = await request.get(execution.artifacts.xlsx.download_url);
  expect(xlsxArtifact.ok()).toBeTruthy();
  const xlsxBytes = await xlsxArtifact.body();
  expect(xlsxBytes.subarray(0, 2).toString()).toBe("PK");

  const jsonArtifact = await request.get(execution.artifacts.json.download_url);
  expect(jsonArtifact.ok()).toBeTruthy();
  const jsonBody = JSON.parse((await jsonArtifact.body()).toString("utf8"));
  expect(Array.isArray(jsonBody)).toBeTruthy();

  const parquetArtifact = await request.get(execution.artifacts.parquet.download_url);
  expect(parquetArtifact.ok()).toBeTruthy();
  expect((await parquetArtifact.body()).subarray(0, 4).toString()).toBe("PAR1");

  // 8. Verify the live report and PDF endpoints after refinement.
  const xlsxExport = await request.get(
    `${api()}/datasets/${datasetId}/export/${execution.version.number}?format=xlsx`,
    { headers: auth },
  );
  expect(xlsxExport.ok()).toBeTruthy();
  const xlsxExportBody = await xlsxExport.json();
  expect(xlsxExportBody.format).toBe("xlsx");
  const xlsxExportDownload = await request.get(xlsxExportBody.download_url);
  expect(xlsxExportDownload.ok()).toBeTruthy();
  expect((await xlsxExportDownload.body()).subarray(0, 2).toString()).toBe("PK");

  const dashboard = await request.get(`${api()}/reports/${datasetId}/dashboard`, { headers: auth });
  expect(dashboard.ok()).toBeTruthy();
  const report = await dashboard.json();
  expect(report.dataset.version).toBe(execution.version.number);
  expect(report.quality.overall).toBeGreaterThanOrEqual(0);

  const pdf = await request.get(`${api()}/reports/${datasetId}/pdf`, { headers: auth });
  expect(pdf.ok()).toBeTruthy();
  expect(pdf.headers()["content-type"]).toContain("application/pdf");

  // 9. Confirm the UI can open the refined dataset report.
  await page.reload();
  await expect(page.getByText("E2E Data")).toBeVisible();
  await page.getByRole("button", { name: "Inspect" }).last().click();
  await expect(page.getByText(/DATA READINESS|Dataset intelligence/)).toBeVisible();
});
