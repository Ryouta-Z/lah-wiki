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

function cardRows(kind) {
  return catalog.cards.filter((card) => card.kind === kind).map((card) => [
    card.cardId,
    card.name,
    card.originalName,
    "★".repeat(card.rarity),
    card.element?.label ?? "不适用",
    card.role.label,
    card.stats.level1.hp ?? null,
    card.stats.level1.attack ?? null,
    card.stats.level1.agility ?? null,
    card.stats.max.hp ?? null,
    card.stats.max.attack ?? null,
    card.stats.max.agility ?? null,
    card.skills.map((skill) => `${skill.relation}｜${skill.name}\n${skill.description}`).join("\n\n"),
    card.skills.some((skill) => skill.nameSource === "日文原文" || skill.descriptionSource === "日文原文")
      ? "含日文原文"
      : "官方简中",
  ]);
}

function buildCardSheet(name, kind, headerColor, tableName) {
  const sheet = workbook.worksheets.add(name);
  const headers = [
    "卡片编号", "姓名", "日文名", "稀有度", "元素", "定位",
    "1级 HP", "1级 攻击", "1级 速度", "满级 HP", "满级 攻击", "满级 速度",
    "关联技能", "文本来源",
  ];
  const rows = cardRows(kind);
  sheet.showGridLines = false;
  sheet.mergeCells("A1:N1");
  sheet.getRange("A1").values = [[`Live A Hero ${name}速查`]];
  sheet.getRange("A1").format = { fill: headerColor, font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "left" };
  sheet.mergeCells("A2:N2");
  sheet.getRange("A2").values = [[`快照 ${catalog.metadata.snapshotId} · ${rows.length} 张卡 · 仅官方简中，缺失文本标为日文原文`]];
  sheet.getRange("A2").format = { font: { color: theme.muted, italic: true } };
  sheet.getRange("A4:N4").values = [headers];
  sheet.getRangeByIndexes(4, 0, rows.length, headers.length).values = rows;
  const dataRange = sheet.getRangeByIndexes(3, 0, rows.length + 1, headers.length);
  sheet.tables.add(`A4:N${rows.length + 4}`, true, tableName);
  sheet.getRange("A4:N4").format = { fill: headerColor, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
  dataRange.format.font = { color: theme.text };
  dataRange.format.borders = { preset: "insideHorizontal", style: "thin", color: theme.border };
  sheet.getRange(`G5:L${rows.length + 4}`).format.numberFormat = "#,##0";
  sheet.getRange(`A5:N${rows.length + 4}`).format.wrapText = true;
  sheet.getRange(`N5:N${rows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
  sheet.getRange("A:A").format.columnWidth = 14;
  sheet.getRange("B:B").format.columnWidth = 16;
  sheet.getRange("C:C").format.columnWidth = 18;
  sheet.getRange("D:F").format.columnWidth = 12;
  sheet.getRange("G:L").format.columnWidth = 12;
  sheet.getRange("M:M").format.columnWidth = 62;
  sheet.getRange("N:N").format.columnWidth = 14;
  sheet.getRange("1:1").format.rowHeight = 28;
  sheet.getRange("2:2").format.rowHeight = 22;
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(2);
}

buildCardSheet("英雄卡", "hero", theme.hero, "HeroCards");
buildCardSheet("助手卡", "sidekick", theme.sidekick, "SidekickCards");

const skillSheet = workbook.worksheets.add("技能");
const skillHeaders = ["技能编号", "关联类型", "中文名称", "日文名", "名称来源", "技能说明", "说明来源"];
const skillRows = catalog.skills.map((skill) => [
  skill.skillId,
  skill.relation,
  skill.name,
  skill.originalName,
  skill.nameSource,
  skill.description,
  skill.descriptionSource,
]);
skillSheet.showGridLines = false;
skillSheet.mergeCells("A1:G1");
skillSheet.getRange("A1").values = [["Live A Hero 技能速查"]];
skillSheet.getRange("A1").format = { fill: theme.skill, font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "left" };
skillSheet.mergeCells("A2:G2");
skillSheet.getRange("A2").values = [[`快照 ${catalog.metadata.snapshotId} · ${skillRows.length} 个去重技能`]];
skillSheet.getRange("A2").format = { font: { color: theme.muted, italic: true } };
skillSheet.getRange("A4:G4").values = [skillHeaders];
skillSheet.getRangeByIndexes(4, 0, skillRows.length, skillHeaders.length).values = skillRows;
skillSheet.tables.add(`A4:G${skillRows.length + 4}`, true, "Skills");
skillSheet.getRange("A4:G4").format = { fill: theme.skill, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
skillSheet.getRange(`A5:G${skillRows.length + 4}`).format.wrapText = true;
skillSheet.getRange(`A5:G${skillRows.length + 4}`).format.borders = { preset: "insideHorizontal", style: "thin", color: theme.border };
skillSheet.getRange(`E5:E${skillRows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
skillSheet.getRange(`G5:G${skillRows.length + 4}`).conditionalFormats.add("containsText", { text: "日文", format: { fill: theme.japanese } });
skillSheet.getRange("A:A").format.columnWidth = 15;
skillSheet.getRange("B:B").format.columnWidth = 14;
skillSheet.getRange("C:D").format.columnWidth = 22;
skillSheet.getRange("E:E").format.columnWidth = 14;
skillSheet.getRange("F:F").format.columnWidth = 68;
skillSheet.getRange("G:G").format.columnWidth = 14;
skillSheet.getRange("1:1").format.rowHeight = 28;
skillSheet.getRange("2:2").format.rowHeight = 22;
skillSheet.freezePanes.freezeRows(4);
skillSheet.freezePanes.freezeColumns(2);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const checks = [];
for (const [sheetName, range] of [["英雄卡", "A1:N8"], ["助手卡", "A1:N8"], ["技能", "A1:G8"]]) {
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

for (const sheetName of ["英雄卡", "助手卡", "技能"]) {
  const preview = await workbook.render({ sheetName, range: "A1:N12", scale: 1, format: "png" });
  await preview.arrayBuffer();
}

console.log(JSON.stringify({
  outputPath,
  sheets: ["英雄卡", "助手卡", "技能"],
  skillCount: skillRows.length,
  checks: checks.map((check) => check.ndjson),
  formulaErrors: formulaErrors.ndjson,
}));
