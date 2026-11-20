"""Run the viewer package and check the same browser action filmed in the promo."""
import json
import subprocess
import sys

from playwright.sync_api import sync_playwright
from series_recipe import ROOT


def test_viewer_can_filter_and_export_an_actual_issue(tmp_path):
    skill = ROOT / "audience/ecommerce-automation"
    subprocess.run([sys.executable, "-B", str(skill/"scripts/ecommerce.py"), "run", "--module", "B",
                    "--input", str(skill/"assets/demo/B.json"), "--output", str(tmp_path)], check=True)
    report = next(tmp_path.glob("*/report.html"))
    result = json.loads(report.with_name("result.json").read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(report.as_uri())
            page.locator("#tables").select_option("issues")
            page.locator("#query").fill("conflicting_price")
            expected = [i for i,r in enumerate(result["tables"]["issues"]) if r["category"]=="conflicting_price"]
            rows = page.locator("button.record")
            assert rows.count() == len(expected) == 2
            rows.last.click()
            with page.expect_download() as download:
                page.locator("#exportrow").click()
            saved = json.loads(download.value.path().read_text(encoding="utf-8"))
            assert saved == {"run_id":result["run_id"], "table":"issues", "index":expected[-1],
                             "row":result["tables"]["issues"][expected[-1]]}
        finally:
            browser.close()

