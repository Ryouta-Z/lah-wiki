import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [catalogPath, outputPath] = process.argv.slice(2);
if (!catalogPath || !outputPath) {
  throw new Error("Usage: node scripts/build_quickref_excel.mjs <catalog.json> <output.xlsx>");
}

const catalog = JSON.parse(await fs.readFile(catalogPath, "utf8"));
const theme = {
  hero: "#1E40AF",
  sidekick: "#7E22CE",
  skill: "#0F766E",
  text: "#172033",
  muted: "#4B5563",
  border: "#D6DFEF",
  japanese: "#FFF7D6",
};

const workbook = Workbook.create();

function skillText(skill) {
  const cost = skill.viewCost == null ? "" : ` · 消耗 View：${skill.viewCost}`;
  return `${skill.relation}｜${skill.name}${cost}\n${skill.description}`;
}

function officialChineseAvailability(skill) {
  return skill.officialChineseAvailability ?? (skill.descriptionSource === "官方简中" ? "完整官方简中" : "无官方简中");
}

function statusTermSources(skill) {
  return skill.statusTermSources || "—";
}

function cardRows(kind) {
  return catalog.cards.filter((card) => card.kind === kind).map((card) => {
    const identity = [
    card.cardId,
    card.name,
    card.originalName,
    "★".repeat(card.rarity),
    ];
    return kind === "hero"
      ? [
        ...identity,
        card.element?.label ?? "不适用",
        card.role?.label ?? "不适用",
        card.stats.level60.hp ?? null,
        card.stats.level60.attack ?? null,
        card.stats.level60.agility ?? null,
        card.skills.map(skillText).join("\n\n"),
        card.skills.some((skill) => skill.nameSource === "日文原文" || skill.descriptionSource === "日文原文")
          ? "含日文原文"
          : "官方简中",
      ]
      : [
        ...identity,
        ...[
          card.stats.level1.hp ?? null,
          card.stats.level1.attack ?? null,
          card.stats.level1.agility ?? null,
          card.stats.max.hp ?? null,
          card.stats.max.attack ?? null,
          card.stats.max.agility ?? null,
        ],
        card.skills.map(skillText).join("\n\n"),
        card.skills.some((skill) => skill.nameSource === "日文原文" || skill.descriptionSource === "日文原文")
          ? "含日文原文"
          : "官方简中",
      ];
  });
}

function buildCardSheet(name, kind, headerColor, tableName) {
  const sheet = workbook.worksheets.add(name);
  const isHero = kind === "hero";
  const headers = isHero
    ? ["卡片编号", "姓名", "日文名", "稀有度", "属性", "职能", "60级 HP", "60级 攻击", "60级 速度", "关联技能", "文本来源"]
    : ["卡片编号", "姓名", "日文名", "稀有度", "1级 HP", "1级 攻击", "1级 速度", "最高阶段 HP", "最高阶段 攻击", "最高阶段 速度", "关联技能", "文本来源"];
  const lastColumn = isHero ? "K" : "L";
  const skillColumn = isHero ? "J" : "K";
  const sourceColumn = isHero ? "K" : "L";
  const rows = cardRows(kind);
  sheet.showGridLines = false;
  sheet.mergeCells(`A1:${lastColumn}1`);
  sheet.getRange("A1").values = [[`Live A Hero ${name}速查`]];
  sheet.getRange("A1").format = { fill: headerColor, font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "left" };
  sheet.mergeCells(`A2:${lastColumn}2`);
  sheet.getRange("A2").values = [[`快照 ${catalog.metadata.snapshotId} · ${rows.length} 张卡 · ${kind === "hero" ? catalog.metadata.heroStatPolicy : catalog.metadata.sidekickSkillPolicy}`]];
  sheet.getRange("A2").format = { font: { color: theme.muted, italic: true } };
  sheet.getRange(`A4:${lastColumn}4`).values = [headers];
  sheet.getRangeByIndexes(4, 0, rows.length, headers.length).values = rows;
  const dataRange = sheet.getRangeByIndexes(3, 0, rows.length + 1, headers.length);
  sheet.tables.add(`A4:${lastColumn}${rows.length + 4}`, true, tableName);
  sheet.getRange(`A4:${lastColumn}4`).format = { fill: headerColor, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
  dataRange.format.font = { color: theme.text };
  dataRange.format.borders = { preset: "insideHorizontal", style: "thin", color: theme.border };
  sheet.getRange(`${isHero ? "G" : "E"}5:${isHero ? "I" : "J"}${rows.length + 4}`).format.numberFormat = "#,##0";
  sheet.getRange(`A5:${lastColumn}${rows.length + 4}`).format.wrapText = true;
  sheet.getRange(`${sourceColumn}5:${sourceColumn}${rows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
  sheet.getRange("A:A").format.columnWidth = 14;
  sheet.getRange("B:B").format.columnWidth = 16;
  sheet.getRange("C:C").format.columnWidth = 18;
  sheet.getRange(isHero ? "D:F" : "D:J").format.columnWidth = 12;
  sheet.getRange(isHero ? "G:I" : "E:J").format.columnWidth = 12;
  sheet.getRange(`${skillColumn}:${skillColumn}`).format.columnWidth = 62;
  sheet.getRange(`${sourceColumn}:${sourceColumn}`).format.columnWidth = 14;
  sheet.getRange("1:1").format.rowHeight = 28;
  sheet.getRange("2:2").format.rowHeight = 22;
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(2);
}

buildCardSheet("英雄卡", "hero", theme.hero, "HeroCards");
buildCardSheet("助手卡", "sidekick", theme.sidekick, "SidekickCards");

const skillSheet = workbook.worksheets.add("技能");
const skillHeaders = ["技能编号", "关联类型", "View 消耗", "中文名称", "日文名", "名称来源", "技能说明", "说明来源", "官方简中可用性", "词条说明来源"];
const skillRows = catalog.skills.map((skill) => [
  skill.skillId,
  skill.relation,
  skill.viewCost,
  skill.name,
  skill.originalName,
  skill.nameSource,
  skill.description,
  skill.descriptionSource,
  officialChineseAvailability(skill),
  statusTermSources(skill),
]);
skillSheet.showGridLines = false;
skillSheet.mergeCells("A1:J1");
skillSheet.getRange("A1").values = [["Live A Hero 技能速查"]];
skillSheet.getRange("A1").format = { fill: theme.skill, font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "left" };
skillSheet.mergeCells("A2:J2");
skillSheet.getRange("A2").values = [[`快照 ${catalog.metadata.snapshotId} · ${skillRows.length} 个去重技能`]];
skillSheet.getRange("A2").format = { font: { color: theme.muted, italic: true } };
skillSheet.getRange("A4:J4").values = [skillHeaders];
skillSheet.getRangeByIndexes(4, 0, skillRows.length, skillHeaders.length).values = skillRows;
skillSheet.tables.add(`A4:J${skillRows.length + 4}`, true, "Skills");
skillSheet.getRange("A4:J4").format = { fill: theme.skill, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
skillSheet.getRange(`A5:J${skillRows.length + 4}`).format.wrapText = true;
skillSheet.getRange(`A5:J${skillRows.length + 4}`).format.borders = { preset: "insideHorizontal", style: "thin", color: theme.border };
skillSheet.getRange(`C5:C${skillRows.length + 4}`).format.numberFormat = "#,##0";
skillSheet.getRange(`F5:F${skillRows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
skillSheet.getRange(`H5:H${skillRows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
skillSheet.getRange("A:A").format.columnWidth = 15;
skillSheet.getRange("B:B").format.columnWidth = 24;
skillSheet.getRange("C:C").format.columnWidth = 12;
skillSheet.getRange("D:E").format.columnWidth = 22;
skillSheet.getRange("F:F").format.columnWidth = 14;
skillSheet.getRange("G:G").format.columnWidth = 68;
skillSheet.getRange("H:H").format.columnWidth = 14;
skillSheet.getRange("I:J").format.columnWidth = 18;
skillSheet.getRange("1:1").format.rowHeight = 28;
skillSheet.getRange("2:2").format.rowHeight = 22;
skillSheet.freezePanes.freezeRows(4);
skillSheet.freezePanes.freezeColumns(2);

const upgradeSheet = workbook.worksheets.add("技能强化");
const upgradeHeaders = ["英雄编号", "英雄名称", "日文名", "强化阶段", "任务编号", "强化前技能", "强化前说明", "强化后技能", "强化后（最高等级）说明", "文本来源", "官方简中可用性", "词条说明来源"];
const upgradeRows = catalog.skillUpgrades.map((upgrade) => [
  upgrade.cardId,
  upgrade.cardName,
  upgrade.cardOriginalName,
  upgrade.skillLevel ?? null,
  upgrade.questId ?? null,
  upgrade.before.name,
  upgrade.before.description,
  upgrade.after.name,
  upgrade.after.description,
  [upgrade.before, upgrade.after].some((skill) => skill.nameSource === "日文原文" || skill.descriptionSource !== "官方简中") ? "含日文原文" : "官方简中",
  officialChineseAvailability(upgrade.after),
  statusTermSources(upgrade.after),
]);
upgradeSheet.showGridLines = false;
upgradeSheet.mergeCells("A1:L1");
upgradeSheet.getRange("A1").values = [["Live A Hero 技能强化速查"]];
upgradeSheet.getRange("A1").format = { fill: "#B45309", font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "left" };
upgradeSheet.mergeCells("A2:L2");
upgradeSheet.getRange("A2").values = [[`快照 ${catalog.metadata.snapshotId} · ${upgradeRows.length} 项英雄技能强化（强化后说明为最高等级终态）`]];
upgradeSheet.getRange("A2").format = { font: { color: theme.muted, italic: true } };
upgradeSheet.getRange("A4:L4").values = [upgradeHeaders];
upgradeSheet.getRangeByIndexes(4, 0, upgradeRows.length, upgradeHeaders.length).values = upgradeRows;
upgradeSheet.tables.add(`A4:L${upgradeRows.length + 4}`, true, "SkillUpgrades");
upgradeSheet.getRange("A4:L4").format = { fill: "#B45309", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
upgradeSheet.getRange(`A5:L${upgradeRows.length + 4}`).format.wrapText = true;
upgradeSheet.getRange(`A5:L${upgradeRows.length + 4}`).format.borders = { preset: "insideHorizontal", style: "thin", color: theme.border };
upgradeSheet.getRange(`J5:J${upgradeRows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
upgradeSheet.getRange("A:A").format.columnWidth = 14;
upgradeSheet.getRange("B:C").format.columnWidth = 18;
upgradeSheet.getRange("D:E").format.columnWidth = 12;
upgradeSheet.getRange("F:F").format.columnWidth = 22;
upgradeSheet.getRange("G:G").format.columnWidth = 48;
upgradeSheet.getRange("H:H").format.columnWidth = 22;
upgradeSheet.getRange("I:I").format.columnWidth = 48;
upgradeSheet.getRange("J:J").format.columnWidth = 14;
upgradeSheet.getRange("K:L").format.columnWidth = 18;
upgradeSheet.getRange("1:1").format.rowHeight = 28;
upgradeSheet.getRange("2:2").format.rowHeight = 22;
upgradeSheet.freezePanes.freezeRows(4);
upgradeSheet.freezePanes.freezeColumns(2);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const checks = [];
for (const [sheetName, range] of [["英雄卡", "A1:K8"], ["助手卡", "A1:L8"], ["技能", "A1:J8"], ["技能强化", "A1:L8"]]) {
  checks.push(await workbook.inspect({ kind: "table", range: `${sheetName}!${range}`, include: "values,formulas", tableMaxRows: 8, tableMaxCols: 14 }));
}
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

for (const [sheetName, range] of [["英雄卡", "A1:K12"], ["助手卡", "A1:L12"], ["技能", "A1:J12"], ["技能强化", "A1:L12"]]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(path.dirname(outputPath), `${sheetName}.preview.png`), new Uint8Array(await preview.arrayBuffer()));
}

console.log(JSON.stringify({
  outputPath,
  sheets: ["英雄卡", "助手卡", "技能", "技能强化"],
  skillCount: skillRows.length,
  checks: checks.map((check) => check.ndjson),
  formulaErrors: formulaErrors.ndjson,
}));
