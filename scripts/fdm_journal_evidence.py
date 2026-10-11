"""Consume original FDM progress bytes; custody and runtime acceptance stay external."""
import json
import re
import argparse
import hashlib
import sys
from datetime import datetime

FIXED = frozenset((
    'fdm_initial_price_wait_start', 'fdm_initial_price_wait_complete',
    'fdm_physical_preparation_start', 'fdm_physical_preparation_complete',
    'fdm_quote_request_start', 'fdm_quote_request_complete', 'loaded_setup_start',
    'failed_setup_cleanup_start', 'failed_setup_cleanup_complete',
    'failed_setup_cleanup_failed', 'loaded_upload_start', 'part_pipeline_wait_start',
    'part_pipeline_wait_complete', 'part_price_wait_start', 'part_price_wait_complete',
    'pdf_case_start', 'pdf_render_start', 'pdf_render_complete',
))
HTTP = re.compile(r'http_(GetEstimate|GetOrderTotal|UploadFile|UploadEstimate)_(request|redirect_request|failed|response_[1-5][0-9]{2})')
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)')
PAIRS = (
    ('fdm_initial_price_wait_start', 'fdm_initial_price_wait_complete'),
    ('fdm_physical_preparation_start', 'fdm_physical_preparation_complete'),
    ('fdm_quote_request_start', 'fdm_quote_request_complete'),
    ('part_pipeline_wait_start', 'part_pipeline_wait_complete'),
    ('part_price_wait_start', 'part_price_wait_complete'),
    ('pdf_render_start', 'pdf_render_complete'),
)

class JournalError(ValueError):
    """Refuse without reflecting input values or customer data."""

def require(condition):
    if not condition:
        raise JournalError('FDM journal evidence rejected')

def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result

def timestamp(value):
    require(type(value) is str and STAMP.fullmatch(value) is not None)
    try:
        # Preserve the seventh .NET tick instead of accepting a rounded boundary.
        fraction = re.search(r'\.(\d{1,7})(?:Z|\+00:00)$', value)
        tick = int(fraction.group(1).ljust(7, '0')[-1]) if fraction else 0
        return datetime.fromisoformat(value.replace('Z', '+00:00')), tick
    except ValueError:
        raise JournalError('FDM journal evidence rejected') from None

def consume(data, started_utc, finished_utc):
    """Parse retained bytes inside a caller-supplied interval, never certify custody."""
    require(type(data) is bytes and 0 < len(data) <= 4 * 1024 * 1024)
    start, finish = timestamp(started_utc), timestamp(finished_utc)
    require(start < finish)
    try:
        lines = data.decode('utf-8').splitlines()
        require(0 < len(lines) <= 16384)
        rows = []
        for line in lines:
            require(line and len(line.encode('utf-8')) <= 1024)
            row = json.loads(line, object_pairs_hook=unique, parse_constant=lambda _: require(False))
            require(type(row) is dict and set(row) == {'atUtc', 'phase', 'parts'})
            require(type(row['phase']) is str and (row['phase'] in FIXED or HTTP.fullmatch(row['phase']) is not None))
            require(type(row['parts']) is int and 1 <= row['parts'] <= 2147483647)
            require(start <= timestamp(row['atUtc']) <= finish)
            rows.append(row)
        return rows
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise JournalError('FDM journal evidence rejected') from None

def assess(rows, required_fixed, scenario):
    """Report operation completion only; required labels come from reviewed test bindings."""
    require(type(required_fixed) is list and 0 < len(required_fixed) == len(set(required_fixed)))
    require(all(type(name) is str and name in FIXED for name in required_fixed))
    require(scenario in ('normal', 'setup-failure'))
    names = [r['phase'] for r in rows]
    require(set(required_fixed) <= set(names))
    if scenario == 'normal':
        require(not any(name.startswith('failed_setup_cleanup_') for name in names))
    else:
        pending = set()
        attempts = 0
        for row in rows:
            name, parts = row['phase'], row['parts']
            if name == 'failed_setup_cleanup_start':
                # No attempt ID exists. Overlapping starts for the same part
                # cannot be safely assigned an outcome, so retain and refuse.
                require(parts not in pending)
                pending.add(parts)
                attempts += 1
            elif name in ('failed_setup_cleanup_complete', 'failed_setup_cleanup_failed'):
                require(parts in pending)
                pending.remove(parts)
        require(attempts > 0 and not pending)
    for beginning, ending in PAIRS:
        outstanding = {}
        for row in rows:
            if row['phase'] == beginning:
                outstanding[row['parts']] = outstanding.get(row['parts'], 0) + 1
            elif row['phase'] == ending:
                require(outstanding.get(row['parts'], 0) > 0)
                outstanding[row['parts']] -= 1
        # Interrupted operations remain visible and cannot count as completed.
        require(not any(outstanding.values()))
    adverse = any(name.endswith('_failed') or
                  (HTTP.fullmatch(name) is not None and '_response_' in name and
                   int(name.rsplit('_', 1)[1]) >= 400) for name in names if name.startswith('http_'))
    # The source caps observations at32 and has no request IDs. Successful
    # responses, absent responses or an empty network slice cannot certify
    # complete network execution. Do not fabricate request/response pairs.
    return {'fixedOperationsComplete': 'failed_setup_cleanup_failed' not in names,
            'journalOperationsComplete': False,
            'networkDiagnostics': 'adverse' if adverse else 'unknown',
            'networkCompleteness': 'unverifiable-original-cap-no-request-ids',
            'observations': len(rows), 'headCustodyVerified': False,
            'runtimeAcceptance': False, 'activationPermitted': False}


def diagnose(data, started_utc, finished_utc, required_fixed, scenario):
    """Public diagnostic contract; supplied intervals do not authenticate custody."""
    rows = consume(data, started_utc, finished_utc)
    return {'schema': 'fdm-journal-diagnostic/v1',
            'journalSha256': hashlib.sha256(data).hexdigest(), 'journalBytes': len(data),
            **assess(rows, required_fixed, scenario)}


class DiagnosticParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error can reflect arbitrary input values.
        raise JournalError('FDM journal evidence rejected')


def main(argv=None):
    try:
        parser = DiagnosticParser()
        parser.add_argument('--root', required=True)
        parser.add_argument('--journal', required=True)
        parser.add_argument('--started-utc', required=True)
        parser.add_argument('--finished-utc', required=True)
        parser.add_argument('--required-fixed', action='append', required=True)
        parser.add_argument('--scenario', choices=('normal', 'setup-failure'), required=True)
        args = parser.parse_args(argv)
        # Reuse the accepted bounded regular-file/identity custody read. This
        # verifies stable bytes, not a producer's head or invocation receipt.
        from fdm_validation_guards import read_file
        data, _ = read_file(args.root, args.journal, 4 * 1024 * 1024)
        print(json.dumps(diagnose(data, args.started_utc, args.finished_utc,
                                 args.required_fixed, args.scenario), sort_keys=True))
        return 0
    except (JournalError, OSError, ValueError, TypeError, KeyError, RecursionError):
        print('FDM journal evidence rejected', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
