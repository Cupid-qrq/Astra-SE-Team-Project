"""Commit title policy: registered developer and meaningful Chinese description."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_commits import valid_subject


class CommitTitleTests(unittest.TestCase):
    def test_registered_developers_and_optional_scope_are_accepted(self):
        for title in [
            '（A覃锐谦）feat: 开发实现课程作业管理',
            '（B祝祎帆）fix(judging): 修复过期租约结果回写',
            '（A覃锐谦）docs：完善双人阶段开发规划',
            '（B祝祎帆）chore: 合并最新主线并验证集成',
        ]:
            with self.subTest(title=title):
                self.assertTrue(valid_subject(title))

    def test_missing_or_mismatched_developer_is_rejected(self):
        for title in [
            'feat: 开发实现课程作业管理',
            '（A祝祎帆）feat: 开发实现课程作业管理',
            '（B覃锐谦）feat: 开发实现课程作业管理',
            '（C其他人）feat: 开发实现课程作业管理',
            '（A）feat: 开发实现课程作业管理',
            '(A覃锐谦)feat: 开发实现课程作业管理',
        ]:
            with self.subTest(title=title):
                self.assertFalse(valid_subject(title))

    def test_invalid_type_or_description_is_rejected(self):
        for title in [
            '（A覃锐谦）update: 开发实现课程作业管理',
            '（B祝祎帆）feat: implement grading module',
            '（A覃锐谦）feat: 更新',
            '（B祝祎帆）fix: ',
            '（A覃锐谦）feat: 开发实现课程管理\n第二行',
        ]:
            with self.subTest(title=title):
                self.assertFalse(valid_subject(title))


if __name__ == '__main__':
    unittest.main()
