import { expect, test } from "@playwright/test";

test("real PDF canvas, coordinates, outline and page navigation", async ({ page }) => {
  const failures:string[]=[];
  page.on("pageerror",e=>failures.push(e.message));
  await page.setViewportSize({width:1440,height:1000});
  await page.goto("/");
  await page.getByLabel("选择样本").selectOption("single-column");
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  const pixel = await page.locator('canvas').evaluate((canvas:HTMLCanvasElement)=>{
    const data=canvas.getContext('2d')!.getImageData(0,0,canvas.width,canvas.height).data;
    let ink=0; for(let i=0;i<data.length;i+=4) if(data[i]<200&&data[i+3]>0)ink++;
    return ink;
  });
  expect(pixel).toBeGreaterThan(100);
  await page.getByRole("button",{name:"2 Conclusion",exact:true}).click();
  await expect(page.getByLabel("页码",{exact:true})).toHaveValue("2");
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  await expect(page.locator(".bbox.selected")).toHaveCount(1);
  await expect(page.locator(".block.active")).toContainText("2 Conclusion");
  await page.getByLabel("上一页").click();
  await expect(page.getByLabel("页码",{exact:true})).toHaveValue("1");
  if (await page.locator('select[aria-label="选择样本"] option[value="transformer"]').count()) {
    await page.getByLabel("选择样本").selectOption("transformer");
    await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
    await expect(page.locator("h1")).toContainText("Attention Is All You Need");
  }
  await page.screenshot({path:"test-results/stage0-desktop.png",fullPage:true});
  expect(failures).toEqual([]);
});

test("scan and formulas disclose limitations; mobile remains within viewport",async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");
  await page.getByLabel("选择样本").selectOption("scan-like");
  await expect(page.getByText("此页没有可提取的文本层")).toBeVisible();
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  await page.screenshot({path:"test-results/stage0-mobile.png",fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.getByLabel("选择样本").selectOption("formula-dense");
  await expect(page.locator(".formula-warning")).toHaveCount(3);
  await expect(page.getByRole("button",{name:/Copy LaTeX/})).toHaveCount(0);
});

test("failure is visible and retry recovers",async({page})=>{
  await page.route("**/api/samples",route=>route.fulfill({status:503,body:"unavailable"}));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("无法连接后端");
  await page.unroute("**/api/samples");
  await page.getByRole("button",{name:"重试"}).click();
  await expect(page.locator(".panels")).toBeVisible();
});


test("rotated baseline pages render and disclose missing extraction",async({page})=>{
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("选择样本").selectOption("rotated");
  const response = await page.request.get("/api/samples/rotated/document");
  const paperDocument = await response.json();
  for (const number of [1,2,3,4]) {
    await page.getByLabel("页码",{exact:true}).selectOption(String(number));
    await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
    const blocks = paperDocument.blocks.filter((b: { page: number }) => b.page === number);
    await expect(page.locator(".block")).toHaveCount(blocks.length);
    if (blocks.length) {
      await page.locator('.meta button').first().click();
      await expect(page.locator('.bbox.selected')).toHaveCount(1);
    } else {
      expect(paperDocument.pages[number - 1].text_status).toBe("missing");
      await expect(page.getByText("此页没有可提取的文本层")).toBeVisible();
      await expect(page.locator(".bbox")).toHaveCount(0);
    }
  }
  expect(errors).toEqual([]);
});


test("Chinese PDF uses local font resources and renders",async({page})=>{
  const failures:string[]=[];
  page.on("requestfailed",r=>failures.push(r.url()));
  await page.goto("/");
  await page.getByLabel("选择样本").selectOption("paired-zh");
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  await expect(page.locator('.blocks-scroll')).toContainText("合成测试文档");
  await page.screenshot({path:"test-results/stage0-chinese.png",fullPage:true});
  expect(failures.filter(url=>url.includes('/pdfjs/'))).toEqual([]);
});

test("Marker paper keeps the abstract together and complete tables selectable", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.locator(".panels")).toBeVisible();
  test.skip(!await page.locator('select[aria-label="选择样本"] option[value="transformer"]').count(), "Local paper not present");
  await page.getByLabel("选择样本").selectOption("transformer");
  const response = await page.request.get("/api/samples/transformer/document");
  const paperDocument = await response.json();
  test.skip(!paperDocument.parser_version.startsWith("marker-"), "Marker cache not prepared");
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  const abstract = page.locator(".block").filter({ hasText: "The dominant sequence transduction models" });
  await expect(abstract).toHaveCount(1);
  await expect(abstract).toContainText("41.8");
  await expect(abstract).not.toContainText("7v26730");
  await abstract.getByRole("button").click();
  await expect(page.locator(".bbox.selected")).toHaveCount(1);
  await page.screenshot({ path: "test-results/marker-desktop.png", fullPage: true });
  const table = paperDocument.blocks.find((b: { type: string }) => b.type === "table");
  expect(table).toBeTruthy();
  await page.getByLabel("页码", { exact: true }).selectOption(String(table.page));
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  await page.locator(`[id="${table.id}"] .meta button`).click();
  await expect(page.locator(".bbox.selected")).toHaveCount(1);
  await page.getByLabel("页码", { exact: true }).selectOption("1");
  await page.setViewportSize({ width: 390, height: 844 });
  await abstract.getByRole("button").click();
  await expect(page.locator('.pdf-sheet[data-rendered="true"]')).toBeVisible();
  await expect(abstract).toBeVisible();
  await expect(abstract).toHaveClass(/active/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  const ink = await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
    const pixels = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4) if (pixels[i] < 200 && pixels[i + 3] > 0) count++;
    return count;
  });
  expect(ink).toBeGreaterThan(100);
  await page.screenshot({ path: "test-results/marker-mobile.png", fullPage: true });
});
