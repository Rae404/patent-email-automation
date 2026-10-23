import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from mom_automation.mail_parser import load_samples_json, parse_samples
from mom_automation.normalization import normalize_identifier


class ParserTests(unittest.TestCase):
    def test_normalize_identifier(self):
        self.assertEqual(normalize_identifier("209910000001.1"), "2099100000011")
        self.assertEqual(normalize_identifier("CN209930000005.X"), "209930000005X")

    def test_parse_samples_dedupes_and_detects_statuses(self):
        samples = load_samples_json(Path(__file__).resolve().parents[1] / "samples" / "emails.json")
        events = parse_samples(samples)
        by_no_event = {(e.normalized_no, e.event): e for e in events}
        self.assertEqual(len(events), 7)
        self.assertIn(("2099100000011", "专利证书"), by_no_event)
        self.assertIn(("2099200000020", "办理登记手续通知书"), by_no_event)
        self.assertEqual(by_no_event[("2099200000020", "办理登记手续通知书")].duplicate_count, 2)
        self.assertIn(("2099100000033", "专利申请受理通知书"), by_no_event)
        self.assertIn(("2099100000044", "专利申请受理通知书"), by_no_event)
        self.assertIn(("2099100000044", "收费减缴审批通知书"), by_no_event)
        self.assertIn(("209930000005X", "办理登记手续通知书"), by_no_event)
        self.assertEqual(by_no_event[("209930000005X", "办理登记手续通知书")].duplicate_count, 2)
        self.assertIn(("2099200000066", "驳回决定通知书"), by_no_event)
        self.assertEqual(
            by_no_event[("209930000005X", "办理登记手续通知书")].title,
            "虚构示例装置",
        )


if __name__ == "__main__":
    unittest.main()
