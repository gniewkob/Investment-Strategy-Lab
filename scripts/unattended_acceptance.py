"""Local metadata-only acceptance recorder. No network, credentials or supervisor writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import fcntl
import json
import math
import os
import plistlib
from pathlib import Path
import re
import stat
import subprocess
import tempfile

EXPECTED_SHA = 'c0b543015f61692a85808f11e577c8c13fd4dc8f'
NOTIFICATION_SHA = 'fcc7c2cc774b98d29af5a4286278c8ebac432038'
RPC_COUNTERS = ('requests', 'http_200', 'http_429', 'http_other', 'network_errors',
                'rpc_capacity_errors', 'rpc_other_errors', 'rejected_responses', 'retries')
SOURCE_NAMES = ('exchange', 'history', 'cdp_ethereum', 'cdp_base',
                'rpc_ethereum', 'rpc_base', 'market', 'nbp')
STATUSES = {'OK', 'PARTIAL', 'UNAVAILABLE', 'STALE', 'UNKNOWN'}


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.timestamp()


def private_directory(path):
    info = Path(path).lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('unsafe directory')


def load(path, limit=2_000_000):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('unsafe file')
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('oversized input')
        return json.loads(raw)


def _open_checkout_fd(directory):
    """Open every checkout ancestor without symlinks or unsafe write perms.

    Preserve this fd through the Git invocation so parent rename attacks
    cannot redirect the command to an unvalidated checkout.
    """
    path = Path(directory)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('invalid git checkout')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open('/', flags)
    try:
        for i, name in enumerate(path.parts[1:]):
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            root_sticky = (info.st_uid == 0 and
                           info.st_mode & stat.S_ISVTX and
                           info.st_mode & 0o002)
            if not (stat.S_ISDIR(info.st_mode) and
                    info.st_uid in (0, os.getuid()) and
                    (not info.st_mode & 0o022 or root_sticky)):
                raise ValueError('unsafe git ancestor')
            if i == len(path.parts) - 2 and (
                    info.st_uid != os.getuid() or info.st_mode & 0o022):
                raise ValueError('unsafe git checkout')
        return fd
    except Exception:
        os.close(fd)
        raise


def _require_git(condition):
    if not condition:
        raise ValueError('untrusted git metadata')


def _checked_git_metadata_file(path, uid, limit=4096):
    """Bounded no-follow read of owner-controlled git metadata, never Git."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        _require_git(stat.S_ISREG(info.st_mode) and info.st_uid == uid
                and not (info.st_mode & 0o022)
                and 0 < info.st_size <= limit)
        raw = stream.read(limit + 1)
    _require_git(len(raw) == info.st_size)
    return raw


def _trusted_git_config_path(root, uid):
    """Resolve either standalone .git or a verified linked-worktree gitfile.

    All real directories are traversed with O_NOFOLLOW and ownership/mode
    checks. A gitfile may point only to a canonical, owner-controlled
    $COMMON/worktrees/<id>, with a matching absolute backlink and common
    directory. Reject nested commondir/config.worktree and symlinks.
    """
    root = Path(root)
    dotgit = root / ".git"
    info = dotgit.lstat()
    _require_git(info.st_uid == uid and not (info.st_mode & 0o022))
    if stat.S_ISDIR(info.st_mode):
        for name in ("config.worktree", "commondir"):
            extra = dotgit / name
            _require_git(not extra.exists() and not extra.is_symlink())
        return dotgit / "config"

    _require_git(stat.S_ISREG(info.st_mode))
    gitfile = _checked_git_metadata_file(dotgit, uid)
    pointer = re.fullmatch(rb"gitdir: ([^\r\n\x00]{1,4000})\r?\n?", gitfile)
    _require_git(pointer is not None)
    try:
        target = Path(os.fsdecode(pointer.group(1)))
    except (UnicodeError, ValueError):
        raise ValueError('untrusted git metadata') from None
    _require_git(target.is_absolute() and ".." not in target.parts
            and "." not in target.parts
            and str(target) == os.path.normpath(str(target)))
    target_fd = _open_checkout_fd(target)
    try:
        actual = target.lstat()
        bound = os.fstat(target_fd)
        _require_git((actual.st_dev, actual.st_ino) == (bound.st_dev, bound.st_ino))
    finally:
        os.close(target_fd)
    _require_git(target.parent.name == "worktrees" and bool(target.name))
    common = target.parent.parent
    common_fd = _open_checkout_fd(common)
    try:
        actual = common.lstat()
        bound = os.fstat(common_fd)
        _require_git((actual.st_dev, actual.st_ino) == (bound.st_dev, bound.st_ino))
    finally:
        os.close(common_fd)

    commondir = _checked_git_metadata_file(target / "commondir", uid)
    # Git's standard per-worktree admin dir points two levels up.
    _require_git(commondir.rstrip(b"\r\n") == b"../..")
    backlink = _checked_git_metadata_file(target / "gitdir", uid)
    try:
        linked_path = Path(os.fsdecode(backlink.rstrip(b"\r\n")))
    except (UnicodeError, ValueError):
        raise ValueError('untrusted git metadata') from None
    _require_git(linked_path.is_absolute() and
            str(linked_path) == str(dotgit) and
            not any(c in backlink for c in (b"\x00",)))
    for p in (target / "config.worktree", common / "commondir",
              common / "config.worktree"):
        _require_git(not p.exists() and not p.is_symlink())
    return common / "config"



def _trusted_git_checkout(directory):
    """Fail closed on standalone or linked-worktree Git metadata.

    Copied collector is self-contained under Python -I; this mirrors the
    M1 preflight's pinned metadata checks and does not run untrusted Git
    until all pointers and common configuration have been checked.
    """
    root = Path(directory)
    fd = _open_checkout_fd(root)
    try:
        bound, current = os.fstat(fd), root.lstat()
        if (bound.st_dev, bound.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('untrusted git root')
    finally:
        os.close(fd)
    config = _trusted_git_config_path(root, os.getuid())
    raw = _checked_git_metadata_file(config, os.getuid(), limit=64_000)
    try:
        config_text = raw.decode('utf-8').lower()
    except UnicodeDecodeError:
        raise ValueError('unreadable git config') from None

    allowed = {
        'core': {'repositoryformatversion', 'filemode', 'bare',
                 'logallrefupdates', 'ignorecase', 'precomposeunicode',
                 'symlinks', 'protecthfs', 'protectntfs', 'quotepath'},
        'remote': {'url', 'fetch', 'pushurl', 'tagopt', 'mirror'},
        'branch': {'remote', 'merge', 'rebase', 'description'},
        'user': {'name', 'email', 'signingkey'},
        'pull': {'rebase', 'ff'},
        'init': {'defaultbranch'},
        'gc': {'auto'},
    }
    section = None
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', ';')):
            continue
        if stripped.endswith('\\'):
            raise ValueError('git config continuation not allowed')
        if stripped.startswith('['):
            match = re.fullmatch(
                r'\[([a-z][a-z0-9-]*)(?:\s+"[^"\\\n]{1,128}")?\]',
                stripped)
            if not match or match.group(1) not in allowed:
                raise ValueError('git config section not allowed')
            section = match.group(1)
            continue
        match = re.fullmatch(r'([a-z][a-z0-9-]*)\s*=\s*(.*)', stripped)
        if not match or section is None or match.group(1) not in allowed[section]:
            raise ValueError('git config key not allowed')


def command(args, cwd=None):
    if args and args[0] == 'git':
        if cwd is None:
            raise ValueError('git attestation requires explicit checkout')
        _trusted_git_checkout(cwd)
        # Never trust inherited GIT_* (including config counters and alternate
        # worktrees). Always invoke system Git with execution hooks disabled.
        clean_env = {name: value for name, value in os.environ.items()
                     if not name.startswith('GIT_')}
        clean_env.update({
            'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_ATTR_NOSYSTEM': '1',
            'GIT_OPTIONAL_LOCKS': '0',
            'GIT_TERMINAL_PROMPT': '0',
            'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
        })
        fd = _open_checkout_fd(cwd)
        try:
            checked, current = os.fstat(fd), Path(cwd).lstat()
            if (checked.st_dev, checked.st_ino) != (
                    current.st_dev, current.st_ino):
                raise ValueError('git checkout changed')
            args = ['/usr/bin/git', '--no-optional-locks',
                    '-c', 'core.fsmonitor=false',
                    '-c', 'core.hooksPath=/dev/null',
                    '-c', 'core.untrackedCache=false',
                    '-c', 'core.attributesFile=/dev/null',
                    '-c', 'core.excludesFile=/dev/null',
                    '-c', 'submodule.recurse=false', *args[1:]]
            if 'status' in args:
                args = [*args, '--ignore-submodules=all']
            # macOS cannot chdir('/dev/fd/N') to an opened directory.
            # fchdir in the forked child binds Git to the verified inode,
            # without reopening an ancestor pathname. This collector is
            # a single-threaded CLI; never run this from threaded workers.
            return subprocess.check_output(
                args, pass_fds=(fd,), preexec_fn=lambda: os.fchdir(fd),
                text=True, stderr=subprocess.DEVNULL,
                timeout=10, env=clean_env).strip()
        finally:
            os.close(fd)
    return subprocess.check_output(
        args, cwd=cwd, text=True, stderr=subprocess.DEVNULL,
        timeout=10).strip()


def watchdog_attestation(runtime, definition, loaded_job, expected_commit=EXPECTED_SHA):
    """Attest the reviewed, separately pinned notification checkout, without reading ntfy config."""
    directory = definition.get('WorkingDirectory')
    allowed = {str(runtime): expected_commit,
               str(runtime.parent / 'notification-app'): NOTIFICATION_SHA}
    loaded = re.search(r'^\s*working directory = (.+)$', loaded_job, re.M)
    if directory not in allowed or loaded is None or loaded[1] != directory:
        return {'recognized': False, 'commit': None, 'clean': False}
    sha = command(['git', 'rev-parse', 'HEAD'], cwd=directory)
    clean = not bool(command(['git', 'status', '--porcelain'], cwd=directory))
    return {'recognized': sha == allowed[directory] and clean,
            'commit': sha if re.fullmatch('[0-9a-f]{40}', sha) else None, 'clean': clean}


def inspect_runtime(runtime, expected_commit=EXPECTED_SHA):
    """Store only allowlisted process metadata; never persist command lines."""
    job = command(['launchctl', 'print', f'gui/{os.getuid()}/pl.gniewkob.isl.portfolio'])
    match = re.search(r'^\s*pid = (\d+)$', job, re.M)
    pid = int(match[1]) if match else None
    rows = command(['ps', '-axo', 'pid=,command=']).splitlines()
    supervisors = []
    for row in rows:
        parts = row.strip().split(None, 1)
        if len(parts) == 2 and re.search(r'-m\s+scripts\.autonomous_portfolio(?:\s|$)', parts[1]) and '--check-health' not in parts[1]:
            supervisors.append((int(parts[0]), '--once' in parts[1]))
    natural = bool(pid and supervisors == [(pid, False)])
    cwd_match = re.search(r'^\s*working directory = (.+)$', job, re.M)
    definitions = []
    definition_hashes = []
    for label in ('pl.gniewkob.isl.portfolio', 'pl.gniewkob.isl.portfolio-health'):
        path = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
        raw = path.read_bytes()
        definitions.append(plistlib.loads(raw))
        definition_hashes.append(sha256(raw).hexdigest())
    supervisor, watchdog = definitions
    watchdog_job = command(['launchctl', 'print', f'gui/{os.getuid()}/pl.gniewkob.isl.portfolio-health'])
    watchdog_code = watchdog_attestation(runtime, watchdog, watchdog_job, expected_commit)
    schedule_ok = (supervisor.get('KeepAlive') is True and supervisor.get('RunAtLoad') is True and
                   watchdog.get('StartInterval') == 300 and
                   watchdog_code['recognized'] and
                   '--check-health' in watchdog.get('ProgramArguments', []) and
                   'run interval = 300 seconds' in watchdog_job)
    provider_ok = 'ISL_BASE_RPC_SOURCE => PUBLICNODE' in job
    bound_runtime = bool(cwd_match and cwd_match[1] == str(runtime) and
                         supervisor.get('WorkingDirectory') == str(runtime))
    start = command(['ps', '-p', str(pid), '-o', 'lstart=']) if pid else None
    sha = command(['git', 'rev-parse', 'HEAD'], cwd=runtime)
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('invalid revision')
    return {'pid': pid, 'process_start': start, 'unique_natural_supervisor': natural,
            'expected_commit': expected_commit,
            'watchdog_code': watchdog_code,
            'launchagent_hashes': definition_hashes, 'launchagents_ok': schedule_ok, 'publicnode': provider_ok, 'runtime_bound': bound_runtime,
            'commit': sha, 'clean': not bool(command(['git', 'status', '--porcelain'], cwd=runtime))}


def source_name(key):
    if key in {'exchange', 'history', 'market'}:
        return key
    if key == 'usdpln':
        return 'nbp'
    for prefix, group in [('chain_', 'rpc'), ('cdp_', 'cdp')]:
        if key.startswith(prefix):
            for suffix, network in [('_8453', 'base'), ('_1', 'ethereum')]:
                if key.endswith(suffix):
                    return group + '_' + network
    return None


def transport_metadata(portfolio):
    """Absent/invalid instrumentation remains UNKNOWN; copy fixed integer counters only."""
    value = portfolio.get('rpc_diagnostics')
    if not isinstance(value, dict) or value.get('mode') != 'SCOPED_RPC_TRANSPORT_METADATA_V1' or value.get('scope') != 'ETHEREUM_BASE_RPC_ONLY':
        return None
    chains = value.get('chains')
    if not isinstance(chains, dict) or set(chains) != {'1', '8453'}:
        return None
    clean = {}
    for chain, counters in chains.items():
        if not isinstance(counters, dict) or set(counters) != set(RPC_COUNTERS) or any(
                type(count) is not int or not 0 <= count <= 1_000_000 for count in counters.values()):
            return None
        if (sum(counters[k] for k in ('http_200', 'http_429', 'http_other')) > counters['requests'] or
                counters['network_errors'] > counters['requests'] or counters['retries'] > counters['requests']):
            return None
        clean[chain] = {key: counters[key] for key in RPC_COUNTERS}
    return clean


def project(portfolio, health, watchdog, runtime, now):
    """Project through a fixed schema: never copy labels, alerts, errors or data rows."""
    checked = timestamp(health['checked_at_utc'])
    expires = timestamp(health['expires_at_utc'])
    if (portfolio['checked_at_utc'] != health['checked_at_utc'] or
            portfolio['status'] != health['status'] or
            portfolio['expires_at_utc'] != health['expires_at_utc'] or not checked < expires <= checked + 1800 or
            checked > now + 5):
        raise ValueError('inconsistent checkpoint')
    if any(type(x.get('financial_operations')) is not int or x['financial_operations'] != 0
           for x in (portfolio, health)):
        raise ValueError('financial invariant')
    sources = {name: [] for name in SOURCE_NAMES}
    for key, value in portfolio['sources'].items():
        name = source_name(key)
        if name:
            state = value.get('status')
            if state not in STATUSES:
                state = 'UNKNOWN'
            when = timestamp(value['checked_at_utc'])
            if when > checked + 5 or checked - when > 1800:
                state = 'STALE'
            sources[name].append(state)
    sources = {name: ('OK' if values and all(x == 'OK' for x in values)
                      else 'UNKNOWN' if not values else next(x for x in values if x != 'OK'))
               for name, values in sources.items()}
    coverage = portfolio['history_coverage']
    streams = []
    for value in coverage['streams'].values():
        first, last = value.get('first_complete_from_block'), value.get('last_complete_to_block')
        if any(x is not None and (type(x) is not int or x < 0) for x in (first, last)):
            raise ValueError('invalid coverage')
        streams.append({'first_block': first, 'last_block': last,
                        'complete_range': value.get('latest_status') == 'COMPLETE_RANGE',
                        'gap_count': len(value['gap_ranges']),
                        'overflow': value.get('gap_range_overflow') is not False,
                        'scope_reset': value.get('scope_reset') is not False})
    backfill = portfolio['history_backfill']
    recovered = backfill['recovered_block_count']
    if type(recovered) is not int or not 0 <= recovered <= 80 or type(backfill['financial_operations']) is not int or backfill['financial_operations'] != 0:
        raise ValueError('invalid backfill')
    watchdog_age = now - timestamp(watchdog['checked_at_utc'])
    watchdog_status = str(watchdog.get('signature', '')).split(':', 1)[0]
    if watchdog_status not in {'OBSERVATION_OK', 'PARTIAL', 'UNAVAILABLE', 'STALE', 'INVALID_OR_MISSING'}:
        watchdog_status = 'UNKNOWN'
    transport = transport_metadata(portfolio)
    status = health['status'] if health['status'] in {'OBSERVATION_OK', 'PARTIAL', 'UNAVAILABLE'} else 'UNKNOWN'
    return {'observed_at': now, 'checkpoint_at': checked, 'expires_at': expires,
            'status': status if now < expires else 'STALE', 'runtime': runtime,
            'sources': sources, 'streams': streams,
            'coverage_ok': bool(streams) and coverage['latest_source_incomplete'] is False and
                coverage['historical_gap_detected'] is False and coverage['gap_range_count'] == 0 and
                all(s['complete_range'] and not s['overflow'] and not s['scope_reset'] for s in streams),
            'backfill': {'within_limit': True, 'recovered_blocks': recovered,
                         'available': backfill['status'] != 'UNAVAILABLE'},
            'watchdog_fresh': -5 <= watchdog_age <= 420,
            'watchdog_at': timestamp(watchdog['checked_at_utc']), 'watchdog_status': watchdog_status,
            'watchdog_matches': watchdog.get('signature') == status + ':' and status == 'OBSERVATION_OK',
            'rpc_transport': transport,
            'http_429_count': sum(c['http_429'] for c in transport.values()) if transport is not None else None,
            'financial_operations': 0}


def healthy(row):
    r = row.get('runtime', {})
    return (row.get('status') == 'OBSERVATION_OK' and r.get('unique_natural_supervisor') is True and
            r.get('clean') is True and r.get('launchagents_ok') is True and
            r.get('publicnode') is True and r.get('runtime_bound') is True and
            r.get('commit') == r.get('expected_commit', EXPECTED_SHA) and
            row.get('coverage_ok') is True and row.get('watchdog_fresh') is True and
            row.get('watchdog_matches') is True and row.get('backfill', {}).get('available') is True and
            set(row.get('sources', {})) == set(SOURCE_NAMES) and
            all(x == 'OK' for x in row['sources'].values()))


def summarize(rows):
    """Fail closed; baseline and repeated reads never count as new natural cycles."""
    if not rows:
        raise ValueError('empty evidence')
    now = rows[-1]['observed_at']
    first = rows[0]['observed_at']
    identities = {(r.get('runtime', {}).get('pid'), r.get('runtime', {}).get('process_start')) for r in rows}
    checkpoints = sorted({r['checkpoint_at'] for r in rows if r.get('checkpoint_at', 0) > first and
                          r.get('runtime', {}).get('unique_natural_supervisor') is True and
                          r['checkpoint_at'] <= r['observed_at'] + 5})
    gaps = [b - a for a, b in zip(checkpoints, checkpoints[1:])]
    poll_gaps = [b['observed_at'] - a['observed_at'] for a, b in zip(rows, rows[1:])]
    reasons = ['HTTP_429_TELEMETRY_NOT_PERSISTED'] if any(r.get('http_429_count') is None for r in rows) else []
    if now - first < 86400:
        reasons.append('LESS_THAN_24H')
    definitions = {tuple(r.get('runtime', {}).get('launchagent_hashes', [])) for r in rows}
    if len(definitions) != 1:
        reasons.append('LAUNCHAGENT_DEFINITIONS_CHANGED')
    if len(identities) != 1:
        reasons.append('PROCESS_IDENTITY_CHANGED')
    if any(not healthy(r) for r in rows):
        reasons.append('UNHEALTHY_OR_UNVERIFIED_SAMPLE')
    if any(x > 120 or x <= 0 for x in poll_gaps):
        reasons.append('COLLECTOR_INTERRUPTION')
    if any(x < 900 or x > 1020 for x in gaps):
        reasons.append('CYCLE_CADENCE_OUTSIDE_900_TO_1020_SECONDS')
    # Both endpoints must be within one permitted cycle of the observed window.
    if not checkpoints or checkpoints[0] - first > 1020 or now - checkpoints[-1] > 1020:
        reasons.append('CHECKPOINT_ENDPOINT_COVERAGE_INCOMPLETE')
    if now - first >= 86400 and len(checkpoints) < math.floor((now - first) / 1020):
        reasons.append('INSUFFICIENT_NATURAL_CHECKPOINTS')
    unique = {r['checkpoint_at']: r for r in rows if r.get('checkpoint_at') in checkpoints}
    return {'status': 'PARTIAL' if reasons else 'PASS', 'reasons': reasons, 'start_utc': datetime.fromtimestamp(first, timezone.utc).isoformat(),
            'end_utc': datetime.fromtimestamp(now, timezone.utc).isoformat(), 'span_seconds': now - first,
            'sample_count': len(rows), 'natural_unique_checkpoints': len(checkpoints),
            'baseline_checkpoints_excluded': 1,
            'nominal_900_second_intervals': math.floor((now - first) / 900),
            'schedule_semantics': 'sleep(900) after cycle completion; execution time adds drift',
            'max_checkpoint_interval_seconds': max(gaps, default=None),
            'delayed_intervals_over_1020': sum(x > 1020 for x in gaps),
            'max_poll_interval_seconds': max(poll_gaps, default=None),
            'status_samples': dict(Counter(r.get('status', 'INVALID') for r in rows)),
            'source_status_samples': {name: dict(Counter(r.get('sources', {}).get(name, 'UNKNOWN') for r in rows)) for name in SOURCE_NAMES},
            'source_status_changes': {name: sum(a.get('sources', {}).get(name) != b.get('sources', {}).get(name)
                                               for a, b in zip(rows, rows[1:])) for name in SOURCE_NAMES},
            'watchdog_status_samples': dict(Counter(r.get('watchdog_status', 'UNKNOWN') for r in rows)),
            'watchdog_observed_status_changes': sum('watchdog_status' in a and 'watchdog_status' in b and
                                                   a['watchdog_status'] != b['watchdog_status']
                                                   for a, b in zip(rows, rows[1:])),
            'recovered_blocks_unique_natural_cycles': sum(r.get('backfill', {}).get('recovered_blocks', 0)
                                                        for r in unique.values()),
            'process_identity_count': len(identities), 'all_samples_healthy': all(healthy(r) for r in rows),
            'http_429_count': None if any(r.get('http_429_count') is None for r in rows) else
                sum(r['http_429_count'] for r in unique.values()),
            'watchdog_transitions_certified': False,
            'prior_history_certified': False, 'financial_operations': 0}


def atomic(path, data):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def record(state, runtime, output, now, expected_commit=EXPECTED_SHA):
    if not re.fullmatch('[0-9a-f]{40}', expected_commit):
        raise ValueError('full expected revision required')
    private_directory(state); private_directory(output)
    # Separate lock: never acquire or mutate the supervisor lock/state.
    fd = os.open(output / 'collector.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('unsafe lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            row = project(load(state / 'portfolio.json'), load(state / 'health.json'),
                          load(state / 'watchdog.json'), inspect_runtime(runtime, expected_commit), now)
        except Exception:
            row = {'observed_at': now, 'status': 'INVALID', 'financial_operations': 0}
        ledger = output / 'samples.jsonl'
        rows = []
        if ledger.exists() or ledger.is_symlink():
            # Validate safety before opening the append-only metadata journal.
            info = ledger.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('unsafe ledger')
            if info.st_size > 64_000_000:
                raise ValueError('evidence limit; preserve and review')
            with ledger.open() as stream:
                rows = [json.loads(line) for line in stream]
        if rows and now <= rows[-1]['observed_at']:
            raise ValueError('clock regression')
        fd = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as stream:
            stream.write(json.dumps(row, sort_keys=True) + '\n'); stream.flush(); os.fsync(stream.fileno())
        summary = summarize(rows + [row])
        atomic(output / 'summary.json', summary)
        return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-directory', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-commit', default=EXPECTED_SHA)
    args = parser.parse_args(argv)
    try:
        summary = record(args.state_directory, args.runtime, args.output, datetime.now(timezone.utc).timestamp(), args.expected_commit)
        print('UNATTENDED_ACCEPTANCE_' + summary['status'])
        return 0
    except Exception:
        print('UNATTENDED_ACCEPTANCE_RECORDING_FAILED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
