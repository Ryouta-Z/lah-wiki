import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.card_history import attach_card_history
from scripts.lah_quickref import ROOT, render_static_html, write_static_site


def release(date, version="v1.0.0"):
    return {
        "date": date,
        "version": version,
        "context": "活动名称",
        "sources": [{"label": "日区 Wiki", "url": "https://wikiwiki.jp/live-a-hero/バレル"}],
    }


class CardHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "card_history.json"
        self.catalog = {"metadata": {}, "cards": []}
        self.hero_raw = {}
        self.sidekick_raw = {}

    def card(self, kind, card_id, stock_id, character_id, name="バレル", resource="barrel"):
        card = {"key": f"{kind}:{card_id}", "kind": kind, "cardId": str(card_id), "name": "同名"}
        self.catalog["cards"].append(card)
        raw = self.hero_raw if kind == "hero" else self.sidekick_raw
        raw[str(card_id)] = {
            "stockId": stock_id, "characterId": character_id,
            "cardName": name, "resourceName": resource,
        }
        return card

    def attach(self, records):
        self.path.write_text(json.dumps({
            "schemaVersion": 1, "verifiedAt": "2026-10-13", "cards": records,
        }), encoding="utf-8")
        attach_card_history(self.catalog, self.hero_raw, self.sidekick_raw, self.path)

    def test_stock_id_survives_star_upgrade_and_separates_card_kinds(self):
        hero = self.card("hero", 100714, 10071, 7)
        sidekick = self.card("sidekick", 100716, 10071, 7)
        records = {
            "hero:10071": {"release": release("2020-10-16")},
            "sidekick:10071": {"release": release("2020-10-17")},
        }
        self.attach(records)
        self.assertEqual(hero["variantId"], "10071")
        self.assertEqual(hero["history"]["release"]["date"], "2020-10-16")
        self.assertEqual(sidekick["history"]["release"]["date"], "2020-10-17")
        hero["cardId"] = "100719"
        hero["key"] = "hero:100719"
        self.hero_raw["100719"] = self.hero_raw["100714"]
        self.attach(records)
        self.assertEqual(hero["history"]["release"]["date"], "2020-10-16")
        self.assertEqual(sidekick["history"]["baseCardKey"], "hero:100719")

    def test_each_sp_uses_the_original_release_and_excludes_custom(self):
        second_sp = self.card("hero", 100732, 10073, 7)
        custom = self.card("hero", 900722, 90072, 7, "清涼のバレル(+カスタム)")
        base = self.card("hero", 100713, 10071, 7)
        first_sp = self.card("hero", 100722, 10072, 7)
        sidekick = self.card("sidekick", 100716, 10071, 7)
        self.attach({
            "hero:10071": {"release": release("2020-10-16")},
            "hero:10072": {"release": release("2021-09-30")},
            "hero:10073": {"release": release("2025-10-07")},
            "hero:90072": {"release": release("2022-01-01")},
        })
        self.assertEqual(base["history"]["variantKind"], "base")
        self.assertEqual(first_sp["history"]["variantKind"], "sp")
        self.assertEqual(first_sp["history"]["daysFromBase"], 349)
        self.assertEqual(second_sp["history"]["daysFromBase"], 1817)
        self.assertEqual(custom["history"]["variantKind"], "custom")
        self.assertIsNone(custom["history"]["daysFromBase"])
        self.assertEqual(sidekick["history"]["variantKind"], "sidekick")
        self.assertEqual(first_sp["history"]["familyCardKeys"], [
            base["key"], sidekick["key"], first_sp["key"], second_sp["key"], custom["key"],
        ])

    def test_character_id_keeps_xeno_separate_despite_matching_display_names(self):
        base = self.card("hero", 100114, 10011, 1, "アカシ", "akashi")
        xeno = self.card("hero", 131812, 13181, 318, "⇌アカシ", "xenoAkashi")
        self.attach({
            "hero:10011": {"release": release("2020-09-30")},
            "hero:13181": {"release": release("2025-09-30")},
        })
        self.assertEqual(base["characterId"], "1")
        self.assertEqual(xeno["characterId"], "318")
        self.assertEqual(xeno["history"]["variantKind"], "base")
        self.assertEqual(xeno["history"]["familyCardKeys"], [xeno["key"]])
        self.assertIsNone(xeno["history"]["daysFromBase"])

    def test_missing_base_date_does_not_promote_an_sp_or_guess_an_interval(self):
        base = self.card("hero", 100114, 10011, 1)
        sp = self.card("hero", 100122, 10012, 1)
        self.attach({"hero:10012": {"release": release("2021-08-06")}})
        self.assertIsNone(base["history"]["release"])
        self.assertEqual(base["history"]["variantKind"], "base")
        self.assertEqual(sp["history"]["variantKind"], "sp")
        self.assertIsNone(sp["history"]["daysFromBase"])

    def test_missing_path_and_unknown_raw_still_attach_pending_history(self):
        card = {"key": "hero:missing", "kind": "hero", "cardId": "missing"}
        self.catalog["cards"].append(card)
        attach_card_history(self.catalog, {}, {}, self.path)
        self.assertIsNone(card["characterId"])
        self.assertIsNone(card["variantId"])
        self.assertEqual(card["history"], {
            "release": None, "events": [], "familyCardKeys": [card["key"]],
            "baseCardKey": None, "variantKind": "unknown", "daysFromBase": None,
        })
        self.assertIsNone(self.catalog["metadata"]["cardHistory"]["verifiedAt"])
        attach_card_history(self.catalog, {}, {}, None)
        self.assertEqual(self.catalog["metadata"]["cardHistory"]["recordCount"], 0)

    def test_soldier_and_custom_without_a_normal_hero_have_no_base(self):
        soldier = self.card("hero", 115416, 11541, 154, "火のアンドロイド兵", "androidSoldierFire")
        custom = self.card("hero", 908212, 90821, 82, "ボレアリス(+カスタム)")
        self.attach({})
        self.assertEqual(soldier["history"]["variantKind"], "soldier")
        self.assertIsNone(soldier["history"]["baseCardKey"])
        self.assertEqual(custom["history"]["variantKind"], "custom")
        self.assertIsNone(custom["history"]["baseCardKey"])

    def test_tree_event_and_evidence_notes_survive(self):
        card = self.card("hero", 100114, 10011, 1)
        event = {**release("2023-01-17", None), "type": "tree", "note": "具体客户端版本待核对"}
        initial = {**release(None, None), "versionNote": "首发版本待核对"}
        self.attach({"hero:10011": {"release": initial, "events": [event]}})
        self.assertEqual(card["history"]["events"], [event])
        self.assertEqual(card["history"]["release"], initial)
        self.assertEqual(self.catalog["metadata"]["cardHistory"]["eventCount"], 1)
        self.assertEqual(self.catalog["metadata"]["cardHistory"]["releaseCount"], 0)

    def test_invalid_dates_fail_instead_of_becoming_verified_records(self):
        for value in ("2025-02-29", "2026-1-1", "20261013", "2026-10-13T12:00:00", 20261013):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                self.attach({"hero:10011": {"release": release(value)}})

    def test_sources_allow_http_https_and_reject_unsafe_or_relative_urls(self):
        self.card("hero", 100114, 10011, 1)
        for url in ("https://wikiwiki.jp/live-a-hero/アカシ#status", "http://example.org/release"):
            record = release("2020-09-30")
            record["sources"][0]["url"] = url
            self.attach({"hero:10011": {"release": record}})
        for url in ("javascript:alert(1)", "data:text/html,test", "/relative", "https://", "https://[invalid"):
            record = release("2020-09-30")
            record["sources"][0]["url"] = url
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "HTTP\\(S\\)"):
                self.attach({"hero:10011": {"release": record}})

    def test_unsupported_schema_and_unknown_card_kinds_are_rejected(self):
        self.path.write_text('{"schemaVersion": 2, "cards": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schemaVersion"):
            attach_card_history(self.catalog, {}, {}, self.path)
        with self.assertRaisesRegex(ValueError, "kind:stockId"):
            self.attach({"other:10011": {"release": release("2020-09-30")}})

    def test_fresh_html_embeds_history_and_has_no_remote_script_or_style_dependency(self):
        self.card("hero", 100114, 10011, 1)
        self.attach({"hero:10011": {"release": release("2020-09-30")}})
        html = render_static_html(self.catalog)
        self.assertEqual(html.count('id="card-history-style"'), 1)
        self.assertEqual(html.count('id="card-history-script"'), 1)
        self.assertIn('"date": "2020-09-30"', html)
        self.assertIn("cardReleaseMarkup(card)", html)
        self.assertIn("renderCardHistoryDetail(card);", html)
        self.assertNotRegex(html, r'<script\b[^>]*\bsrc=["\']https?://')
        self.assertNotRegex(html, r'<link\b[^>]*\bhref=["\']https?://')
        self.assertNotRegex(html, r'@import\s|url\(["\']?https?://')
        history_script = re.search(r'<script id="card-history-script">(.*?)</script>', html, re.S)[1]
        self.assertNotRegex(history_script, r'\b(?:fetch|importScripts)\s*\(')

    def test_repeated_refresh_preserves_formal_query_interface_and_one_history_copy(self):
        self.card("hero", 100114, 10011, 1)
        self.attach({"hero:10011": {"release": release("2020-09-30")}})
        site = Path(self.temp.name) / "index.html"
        existing = (ROOT / "quickref" / "index.html").read_text(encoding="utf-8")
        site.write_text(existing, encoding="utf-8")
        write_static_site(self.catalog, site)
        write_static_site(self.catalog, site)
        html = site.read_text(encoding="utf-8")
        self.assertIn("// 查询界面层：", html)
        for toolbar_control in ('id="openFilters"', 'id="openSort"', 'id="filterDialog"', 'id="sortDialog"'):
            self.assertIn(toolbar_control, existing)
            self.assertIn(toolbar_control, html)
        self.assertEqual(html.count('id="card-history-style"'), 1)
        self.assertEqual(html.count('id="card-history-script"'), 1)
        self.assertEqual(html.count("      renderCardHistoryDetail(card);"), 1)
        embedded = re.search(r"(?m)^    const catalog = (.*);$", html)
        self.assertIsNotNone(embedded)
        self.assertEqual(json.loads(embedded[1]), self.catalog)


if __name__ == "__main__":
    unittest.main()
