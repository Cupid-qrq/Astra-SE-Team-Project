"""v1.0-rc1 document checks and reference examples, not OJ system tests.

Python >= 3.10, standard library only. No network or student code execution.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
import platform
import re

HERE = Path(__file__).resolve().parent
DOC = next((p / '01_需求分析文档.md' for p in (HERE, HERE.parent)
            if (p / '01_需求分析文档.md').is_file()), None)
if DOC is None:
    raise SystemExit('Place script beside 01_需求分析文档.md or in its child directory.')
text = DOC.read_text(encoding='utf-8-sig')
results = []


def check(name, condition, detail):
    results.append({'name': name, 'passed': bool(condition), 'detail': detail})


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed


def formal(open_at, due_at, accepted_at):
    return timestamp(open_at) <= timestamp(accepted_at) < timestamp(due_at)


def tokens(value):
    return [v for v in re.split(rb'[ \t\n\r\v\f]+', value.replace(b'\r\n', b'\n')) if v]


def grade(points, current_records):
    # Caller supplies only the currently active generation; old generations
    # are intentionally never merged into this input.
    formal_records = [r for r in current_records if r['mode'] == 'FORMAL']
    pending = any(r['verdict'] in (None, 'SE') for r in formal_records)
    passed_items = {r['item'] for r in formal_records if r['verdict'] == 'AC'}
    return sum(points[i] for i in passed_items), 'PENDING' if pending else 'PROVISIONAL'


def record(item, verdict, mode='FORMAL'):
    return {'item': item, 'verdict': verdict, 'mode': mode}


def compensation(old_due, recovered_at, approved_at, outage_seconds):
    return max(timestamp(v) for v in (old_due, recovered_at, approved_at)) + timedelta(seconds=max(600, outage_seconds))


def quota_allows(ready, reserved):
    return ready + reserved < 20


def local_day(accepted_at):
    return timestamp(accepted_at).astimezone(timezone(timedelta(hours=8))).date().isoformat()


def quality(d_scores, a_scores, safety_scores):
    return (len(d_scores) == len(a_scores) == len(safety_scores) == 30
            and sum(d_scores) >= 24 and sum(a_scores) >= 27 and all(safety_scores))


def main():
    fr_section = text.split('## 8. 功能需求', 1)[1].split('## 9.', 1)[0]
    nfr_section = text.split('### 10.2 非功能需求表', 1)[1].split('### 10.3', 1)[0]
    fr_rows = re.findall(r'^\| FR-(\d{2}) ([高中低])[^\n]*', fr_section, re.M)
    nfr_rows = re.findall(r'^\| NFR-(\d{2}) ([高中低])[^\n]*', nfr_section, re.M)
    check('DOC-FR', [n for n, _ in fr_rows] == [f'{i:02}' for i in range(1, 30)], '29 unique ordered FR definitions')
    check('DOC-NFR', [n for n, _ in nfr_rows] == [f'{i:02}' for i in range(1, 25)], '24 unique ordered NFR definitions')
    check('DOC-PRIORITY', Counter(p for _, p in fr_rows) == {'高': 25, '中': 3, '低': 1}
          and Counter(p for _, p in nfr_rows) == {'高': 22, '中': 1, '低': 1}, 'FR=25/3/1; NFR=22/1/1')
    fr_lines = [line for line in fr_section.splitlines() if re.match(r'^\| FR-\d{2} ', line)]
    nfr_lines = [line for line in nfr_section.splitlines() if re.match(r'^\| NFR-\d{2} ', line)]
    check('DOC-AC-SOURCE', all(f'AC-{i:02}：' in line and re.search(r'(?:A-|U-|S\d|BR-)\d*', line.split('|')[2])
          for i, line in enumerate(fr_lines, 1)), 'Each FR has own AC and a source/BR')
    check('DOC-NT-SOURCE', all(f'NT-{i:02}：' in line and '来源' in line
          for i, line in enumerate(nfr_lines, 1)), 'Each NFR has own NT and source')
    trace = text.split('### 13.1.1', 1)[1].split('### 13.2', 1)[0]
    trace_rows = re.findall(r'^\| FR-(\d{2}) \| AC-(\d{2}) \|', trace, re.M)
    check('DOC-TRACE', trace_rows == [(f'{i:02}', f'{i:02}') for i in range(1, 30)], '29 row FR-to-AC trace index')
    st_section = text.split('### 12.2', 1)[1].split('### 12.3', 1)[0]
    st_ids = re.findall(r'^\| ST-(\d{2}) ', st_section, re.M)
    check('DOC-ST', st_ids == [f'{i:02}' for i in range(1, 18)], '17 cross-functional test definitions')
    limits = {'FR': 29, 'NFR': 24, 'AC': 29, 'NT': 24, 'ST': 17, 'BR': 17, 'DD': 11, 'IF': 9, 'V': 10}
    bad = [(kind, num) for kind, num in re.findall(r'(?<![A-Z])(NFR|FR|AC|NT|ST|BR|DD|IF|V)-(\d{2})', text)
           if not 1 <= int(num) <= limits[kind]]
    check('DOC-REF-RANGE', not bad, f'Out-of-range references: {bad}')
    time_section = text.split('### 7.3', 1)[1].split('## 8.', 1)[0]
    check('DOC-TIME', all(s in time_section for s in ('FR-18/23', 'FR-27/29', 'NFR-11/17/20')), 'Grade release and retention included')
    check('DOC-FENCES', sum(line.startswith('```') for line in text.splitlines()) % 2 == 0, 'Balanced Markdown code fences')

    opened = '2026-10-08T19:00:00+08:00'
    due = '2026-10-08T20:00:00+08:00'
    boundary = [('2026-10-08T18:59:59.999+08:00', False), (opened, True),
                ('2026-10-08T19:59:59.999+08:00', True), (due, False),
                ('2026-10-08T20:00:00.001+08:00', False)]
    check('RULE-TIME', all(formal(opened, due, t) == expected for t, expected in boundary), 'Open inclusive; due exclusive; +/-1ms')
    check('RULE-ZONE', timestamp(due) == timestamp('2026-10-08T12:00:00Z'), 'UTC and UTC+8 equivalent')
    try:
        timestamp('2026-10-08T20:00:00')
        no_zone_rejected = False
    except ValueError:
        no_zone_rejected = True
    check('RULE-NO-ZONE', no_zone_rejected, 'Naive timestamps rejected')
    comparisons = [(b'1 2', b'1\n2', True), (b'1\r\n2', b'1\n2', True),
                   (b'01', b'1', False), (b'1.0', b'1', False), (b'Ab', b'ab', False),
                   (b'', b' \n\t', True), ('1\u00a02'.encode(), b'1 2', False)]
    check('RULE-TOKENS', all((tokens(a) == tokens(b)) == expected for a, b, expected in comparisons), '7 token comparisons, including non-ASCII whitespace')
    points = {1: 30, 2: 30, 3: 40}
    check('RULE-SE', grade(points, [record(1,'WA'), record(1,'AC'), record(2,'WA'), record(3,'SE')]) == (30,'PENDING'), '30 confirmed and pending, not final zero for SE')
    check('RULE-RECOVERY', grade(points, [record(1,'AC'), record(2,'WA'), record(3,'AC')]) == (70,'PROVISIONAL'), 'Recovery yields 70')
    check('RULE-PRACTICE', grade(points, [record(1,'AC'), record(2,'AC','PRACTICE'), record(3,'AC')]) == (70,'PROVISIONAL'), 'Practice does not add formal points')
    check('RULE-REJUDGE', grade(points, [record(1,'WA'), record(2,'WA'), record(3,'AC')]) == (40,'PROVISIONAL'), 'New active version yields 40, not old 70')
    check('RULE-PENDING', grade(points, [record(1,'AC'), record(1,None)]) == (30,'PENDING'), 'An AC does not mask another pending submission')
    check('RULE-QUOTA', quota_allows(19,0) and not quota_allows(19,1) and not quota_allows(20,0), 'Quota counts READY + reservations')
    check('RULE-QUOTA-DAY', local_day('2026-10-08T15:59:59Z') == '2026-10-08'
          and local_day('2026-10-08T16:00:00Z') == '2026-10-09', 'Quota uses acceptance date in UTC+8')
    check('RULE-COMPENSATION', compensation(due, '2026-10-08T20:03:00+08:00', '2026-10-08T20:04:00+08:00', 300)
          == timestamp('2026-10-08T20:14:00+08:00'), '5-minute outage -> 10-minute minimum window')
    check('RULE-LONG-OUTAGE', compensation(due, '2026-10-08T20:20:00+08:00', '2026-10-08T20:25:00+08:00', 1800)
          == timestamp('2026-10-08T20:55:00+08:00'), '30-minute outage -> 30-minute window after approval')
    check('RULE-CAPACITY', 100/600 < 4/10 < 300/600 and math.ceil(100/4)*10 == 250 and (4/10)*600 == 240, '100-student average fits; 300-student average exceeds assumed service rate')
    d_scores, a_scores = [1]*24+[0]*6, [1]*27+[0]*3
    check('RULE-QUALITY', quality(d_scores,a_scores,[1]*30) and not quality(d_scores,a_scores,[1]*29+[0])
          and not quality([1]*23+[0]*7,a_scores,[1]*30), 'Thresholds and single safety failure are independent gates')
    score = sum(map(Decimal, ['18.4','18.8','18.8','9.2','9.2','17.6']))
    check('RECORD-SCORE', score == Decimal('92.0'), 'Feedback components sum to 92.0')

    summary = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'srs_sha256': hashlib.sha256(DOC.read_bytes()).hexdigest(),
        'test_count': len(results), 'failed': sum(not r['passed'] for r in results),
        'fr_priorities': dict(Counter(p for _,p in fr_rows)),
        'nfr_priorities': dict(Counter(p for _,p in nfr_rows)),
        'scope': 'AI document structure and reference examples only; no system acceptance',
        'results': results,
    }
    lines = [f"Executed UTC: {summary['generated_at']}", f"Python: {summary['python']}",
             f"Script SHA256: {summary['script_sha256']}", f"SRS SHA256: {summary['srs_sha256']}",
             summary['scope'], '']
    lines += [f"{'PASS' if r['passed'] else 'FAIL'} {r['name']}: {r['detail']}" for r in results]
    lines += ['', f"Checks={summary['test_count']}; failed={summary['failed']}"]
    output = '\n'.join(lines) + '\n'
    (HERE / 'rule_check_output.txt').write_text(output, encoding='utf-8')
    (HERE / 'validation_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(output)
    raise SystemExit(1 if summary['failed'] else 0)


if __name__ == '__main__':
    main()
