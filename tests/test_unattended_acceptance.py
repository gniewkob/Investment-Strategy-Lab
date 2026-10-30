"""Synthetic metadata fixtures only; never query the real supervisor or accounts."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import unattended_acceptance as m


def sample(now, checkpoint=None):
    return {'observed_at': now, 'checkpoint_at': checkpoint if checkpoint is not None else now,
            'status': 'OBSERVATION_OK', 'expires_at': now + 1800,
            'runtime': {'pid': 123, 'process_start': 'fixed-start', 'clean': True,
                        'commit': m.EXPECTED_SHA, 'unique_natural_supervisor': True,
                        'publicnode': True, 'runtime_bound': True, 'launchagents_ok': True},
            'sources': dict.fromkeys(m.SOURCE_NAMES, 'OK'), 'coverage_ok': True,
            'watchdog_fresh': True, 'watchdog_matches': True,
            'backfill': {'available': True}, 'http_429_count': None, 'financial_operations': 0}


def fixture():
    iso = lambda x: __import__('datetime').datetime.fromtimestamp(x, __import__('datetime').timezone.utc).isoformat()
    h = {'checked_at_utc': iso(1000), 'expires_at_utc': iso(2800),
         'status': 'OBSERVATION_OK', 'financial_operations': 0}
    p = {**h, 'sources': {k: {'status': 'OK', 'checked_at_utc': iso(995),
                             'data': {'address': 'PRIVATE', 'balance': 'PRIVATE'}} for k in
                             ['exchange','history','market','usdpln','chain_PRIVATE_1',
                              'chain_PRIVATE_8453','cdp_PRIVATE_1','cdp_PRIVATE_8453']},
         'holdings': ['PRIVATE'], 'alerts': ['PRIVATE'],
         'history_coverage': {'latest_source_incomplete': False, 'historical_gap_detected': False,
                             'gap_range_count': 0, 'streams': {'PRIVATE': {
                                 'first_complete_from_block': 10, 'last_complete_to_block': 1009,
                                 'latest_status': 'COMPLETE_RANGE', 'gap_ranges': [],
                                 'gap_range_overflow': False, 'scope_reset': False}}},
         'history_backfill': {'status': 'NO_ELIGIBLE_GAP', 'recovered_block_count': 0, 'financial_operations': 0}}
    return p, h, {'checked_at_utc': iso(1000), 'signature': 'OBSERVATION_OK:'}


class AcceptanceTests(unittest.TestCase):
    def test_runtime_requires_loaded_provider_path_unique_process_and_watchdog(self):
        import plistlib
        runtime = Path('/synthetic/runtime')
        definitions = [plistlib.dumps({'KeepAlive': True, 'RunAtLoad': True,
                        'WorkingDirectory': str(runtime)}),
                       plistlib.dumps({'StartInterval': 300, 'WorkingDirectory': str(runtime),
                                       'ProgramArguments': ['--check-health']})]
        job = 'pid = 123\nworking directory = /synthetic/runtime\nISL_BASE_RPC_SOURCE => PUBLICNODE'
        def commands(args, cwd=None):
            if args[0] == 'launchctl':
                return 'run interval = 300 seconds\nworking directory = /synthetic/runtime' if args[-1].endswith('-health') else job
            if args[:2] == ['ps','-axo']:
                return '123 python -m scripts.autonomous_portfolio --enable-live-read'
            if args[0] == 'ps': return 'fixed-start'
            return m.EXPECTED_SHA if 'rev-parse' in args else ''
        with patch.object(m, 'command', side_effect=commands), patch.object(Path,'read_bytes',side_effect=definitions):
            result = m.inspect_runtime(runtime)
        for key in ['unique_natural_supervisor','runtime_bound','launchagents_ok','publicnode','clean']:
            self.assertTrue(result[key])
        self.assertEqual(len(result['launchagent_hashes']),2)

    def test_separate_reviewed_watchdog_checkout_is_recognized(self):
        runtime = Path('/synthetic/runtime')
        directory = runtime.parent / 'notification-app'
        definition = {'WorkingDirectory': str(directory)}
        loaded = 'working directory = ' + str(directory)
        with patch.object(m, 'command', side_effect=[m.NOTIFICATION_SHA, '']):
            self.assertTrue(m.watchdog_attestation(runtime, definition, loaded)['recognized'])
        for revision, dirty in [('f' * 40, ''), (m.NOTIFICATION_SHA, ' M code.py')]:
            with patch.object(m, 'command', side_effect=[revision, dirty]):
                self.assertFalse(m.watchdog_attestation(runtime, definition, loaded)['recognized'])
        with patch.object(m, 'command') as command:
            self.assertFalse(m.watchdog_attestation(runtime, definition, 'working directory = /other')['recognized'])
            command.assert_not_called()
        definition['WorkingDirectory'] = '/unreviewed'
        self.assertFalse(m.watchdog_attestation(runtime, definition, loaded)['recognized'])

    def test_git_attestation_rejects_untrusted_runtime_and_watchdog_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'runtime'
            git = root / '.git'
            git.mkdir(parents=True)
            config = git / 'config'
            for value in (
                '[core]\nfsmonitor = /untrusted/program\n',
                '[filter "external"]\nprocess = /untrusted/program\n',
                '[core] worktree = /decoy\n',
                '[include]\npath = /untrusted/config\n',
            ):
                config.write_text(value, encoding='utf-8')
                with self.subTest(value=value.splitlines()[0]):
                    with patch.object(m.subprocess, 'check_output',
                                      side_effect=AssertionError('unsafe git subprocess')):
                        with self.assertRaises(ValueError):
                            m.command(['git', 'status', '--porcelain'], cwd=root)
            config.write_text('[core]\nrepositoryformatversion = 0\n')
            (git / 'commondir').write_text('../redirect\n')
            with patch.object(m.subprocess, 'check_output',
                              side_effect=AssertionError('unsafe git subprocess')):
                with self.assertRaises(ValueError):
                    m.command(['git', 'rev-parse', 'HEAD'], cwd=root)

    def test_git_runtime_and_watchdog_use_safe_system_binary_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'runtime'
            git = root / '.git'
            git.mkdir(parents=True)
            (git / 'config').write_text('[core]\nrepositoryformatversion = 0\n')
            with patch.dict(os.environ, {
                'GIT_DIR': '/untrusted/repository',
                'GIT_WORK_TREE': '/untrusted/decoy',
                'GIT_CONFIG_COUNT': '1',
                'GIT_CONFIG_KEY_0': 'core.fsmonitor',
                'GIT_CONFIG_VALUE_0': '/untrusted/program',
            }):
                with patch.object(m.subprocess, 'check_output',
                                  return_value='') as out:
                    m.command(['git', 'status', '--porcelain'], cwd=root)
            args = out.call_args.args[0]
            env = out.call_args.kwargs['env']
            self.assertEqual(args[0], '/usr/bin/git')
            for part in ('--no-optional-locks', 'core.fsmonitor=false',
                         'core.hooksPath=/dev/null', '--ignore-submodules=all'):
                self.assertIn(part, args)
            for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_CONFIG_COUNT'):
                self.assertNotIn(key, env)
            self.assertEqual(env['GIT_OPTIONAL_LOCKS'], '0')
            self.assertEqual(env['GIT_CONFIG_NOSYSTEM'], '1')
            with patch.object(m.subprocess, 'check_output', return_value='a' * 40) as out:
                m.command(['git', 'rev-parse', 'HEAD'], cwd=root)
            self.assertNotIn('--ignore-submodules=all', out.call_args.args[0])

    def test_transport_metadata_keeps_unknown_and_rejects_extra_private_fields(self):
        p,h,w=fixture()
        self.assertIsNone(m.transport_metadata(p))
        p['rpc_diagnostics']={'mode':'SCOPED_RPC_TRANSPORT_METADATA_V1','scope':'ETHEREUM_BASE_RPC_ONLY',
                              'chains':{k:dict.fromkeys(m.RPC_COUNTERS,0) for k in ['1','8453']}}
        p['rpc_diagnostics']['chains']['1']['requests']=2
        p['rpc_diagnostics']['chains']['1']['http_429']=2
        self.assertEqual(m.project(p,h,w,{},1010)['http_429_count'],2)
        p['rpc_diagnostics']['chains']['1']['private_address']='PRIVATE'
        self.assertIsNone(m.project(p,h,w,{},1010)['http_429_count'])
        del p['rpc_diagnostics']['chains']['1']['private_address']
        p['rpc_diagnostics']['chains']['1']['http_429']=True
        self.assertIsNone(m.transport_metadata(p))

    def test_429_counts_do_not_multiply_with_polls_or_include_baseline(self):
        rows=[sample(0),sample(900),sample(960,900)]
        for row,count in zip(rows,[1,2,2]):row['http_429_count']=count
        self.assertEqual(m.summarize(rows)['http_429_count'],2)

    def test_full_known_telemetry_window_can_pass_without_certifying_notification_delivery(self):
        rows=[sample(n,(n//900)*900) for n in range(0,86401,60)]
        for row in rows:row['http_429_count']=0
        result=m.summarize(rows)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['reasons'],[])
        self.assertFalse(result['watchdog_transitions_certified'])

    def test_expected_runtime_pin_is_explicit(self):
        row=sample(1000)
        row['runtime']['commit']='a'*40
        self.assertFalse(m.healthy(row))
        row['runtime']['expected_commit']='a'*40
        self.assertTrue(m.healthy(row))
        with self.assertRaises(ValueError):m.record(Path('/unused'),Path('/unused'),Path('/unused'),0,'not-a-full-sha')

    def test_repeated_checkpoint_and_baseline_excluded(self):
        result = m.summarize([sample(1000), sample(1060,1000), sample(1960,1900)])
        self.assertEqual(result['natural_unique_checkpoints'], 1)
        self.assertIn('LESS_THAN_24H', result['reasons'])

    def test_full_day_does_not_invent_http_telemetry(self):
        rows = [sample(n, (n // 900) * 900) for n in range(0, 86401, 60)]
        result = m.summarize(rows)
        self.assertEqual(result['natural_unique_checkpoints'], 96)
        self.assertEqual(result['reasons'], ['HTTP_429_TELEMETRY_NOT_PERSISTED'])
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertIsNone(result['http_429_count'])

    def test_restart_outage_and_collector_gap_are_not_erased(self):
        rows = [sample(0), sample(60), sample(120), sample(1200)]
        rows[1]['runtime']['pid'] = 456
        rows[2]['sources']['rpc_base'] = 'PARTIAL'
        result = m.summarize(rows)
        for reason in ['PROCESS_IDENTITY_CHANGED','COLLECTOR_INTERRUPTION','UNHEALTHY_OR_UNVERIFIED_SAMPLE']:
            self.assertIn(reason, result['reasons'])

    def test_manual_process_excluded(self):
        rows = [sample(0), sample(900)]
        rows[-1]['runtime']['unique_natural_supervisor'] = False
        self.assertEqual(m.summarize(rows)['natural_unique_checkpoints'], 0)

    def test_slow_missing_and_too_fast_cycles(self):
        for gap in (100, 2100):
            result = m.summarize([sample(0), sample(900), sample(900 + gap)])
            self.assertIn('CYCLE_CADENCE_OUTSIDE_900_TO_1020_SECONDS', result['reasons'])

    def test_projection_discards_identifiers_balances_and_labels(self):
        p,h,w = fixture()
        row = m.project(p,h,w,sample(1000)['runtime'],1010)
        self.assertNotIn('PRIVATE', json.dumps(row))
        self.assertTrue(m.healthy(row))
        self.assertIsNone(row['http_429_count'])

    def test_checkpoint_mismatch_future_and_financial_operations_fail(self):
        for field,value in [('checked_at_utc','2026-01-01T00:00:00+00:00'),('financial_operations',True)]:
            p,h,w = fixture(); p[field] = value
            with self.assertRaises(ValueError): m.project(p,h,w,{},1010)

    def test_backfill_limit_and_coverage_fail_closed(self):
        p,h,w = fixture(); p['history_backfill']['recovered_block_count'] = 81
        with self.assertRaises(ValueError): m.project(p,h,w,{},1010)
        p,h,w = fixture(); p['history_coverage']['streams']['PRIVATE']['gap_range_overflow'] = True
        self.assertFalse(m.project(p,h,w,{},1010)['coverage_ok'])

    def test_watchdog_stale_or_mismatch(self):
        p,h,w = fixture()
        self.assertFalse(m.project(p,h,w,{},1500)['watchdog_fresh'])
        w['signature'] = 'PARTIAL:PRIVATE'
        self.assertFalse(m.project(p,h,w,{},1010)['watchdog_matches'])

    def test_persistence_failure_record_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); root.chmod(0o700)
            with patch.object(m,'project',return_value=sample(1000)), patch.object(m,'load',return_value={}), patch.object(m,'inspect_runtime',return_value={}):
                result = m.record(root,root,root,1000)
            self.assertEqual(result['sample_count'],1)
            with patch.object(m,'load',side_effect=ValueError('PRIVATE')):
                result = m.record(root,root,root,1060)
            self.assertEqual(result['status_samples']['INVALID'],1)
            self.assertNotIn('PRIVATE',(root/'samples.jsonl').read_text())
            self.assertEqual((root/'samples.jsonl').stat().st_mode & 0o777,0o600)
            self.assertEqual((root/'summary.json').stat().st_mode & 0o777,0o600)
            with self.assertRaises(ValueError): m.record(root,root,root,1050)

    def test_symlink_input_output_and_unsafe_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); root.chmod(0o700)
            target = root/'target'; target.write_text('{}'); target.chmod(0o600)
            link = root/'link'; link.symlink_to(target)
            with self.assertRaises(OSError): m.load(link)
            (root/'samples.jsonl').symlink_to(target)
            with patch.object(m,'load',side_effect=ValueError()):
                with self.assertRaises(ValueError): m.record(root,root,root,1000)
            root.chmod(0o755)
            with self.assertRaises(ValueError): m.private_directory(root)


if __name__ == '__main__': unittest.main()
