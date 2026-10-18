"""Strict offline tests. All URLs use a fake password and never connect."""
import unittest
from io import StringIO
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.staging_preflight import validate_dsn, check_connection, main, ConfigurationError, EXPECTED_HOST, classify_operational_error

GOOD = (f"postgresql://isl_agent_staging_limited:nonsecret-ci-dummy@{EXPECTED_HOST}/"
        "investment_lab?sslmode=verify-full")


class PreflightDSNTests(unittest.TestCase):
    def test_minimal_staging_url(self):
        validate_dsn(GOOD)

    def test_reject_missing_url(self):
        with self.assertRaises(ValueError):
            validate_dsn("")

    def test_reject_wrong_role(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace("isl_agent_staging_limited", "investment_lab_owner"))

    def test_reject_wrong_database(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace("/investment_lab?", "/neondb?"))

    def test_reject_another_neon_branch(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace(EXPECTED_HOST, "ep-prod.other.eu-central-1.aws.neon.tech"))

    def test_reject_pooled_endpoint(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace(".c-8.", "-pooler.c-8."))

    def test_reject_insecure_ssl(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace("sslmode=verify-full", "sslmode=require"))

    def test_reject_absent_password(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace(":nonsecret-ci-dummy@", "@"))

    def test_reject_hostaddr_override(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD + "&hostaddr=127.0.0.1")

    def test_reject_service_file(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD + "&service=fake")

    def test_reject_multiple_hosts(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace(EXPECTED_HOST, EXPECTED_HOST + ",host.example"))

    def test_reject_host_port_override(self):
        with self.assertRaises(ValueError):
            validate_dsn(GOOD.replace(EXPECTED_HOST, EXPECTED_HOST + ":5555"))

    def test_config_code_for_wrong_endpoint_or_pooling(self):
        invalid = GOOD.replace(".c-8.", "-pooler.c-8.")
        with self.assertRaises(ConfigurationError) as ctx:
            validate_dsn(invalid)
        self.assertEqual(str(ctx.exception), "HOST_OR_POOLING_MISMATCH")

    def test_config_code_for_tls_parameter(self):
        with self.assertRaises(ConfigurationError) as ctx:
            validate_dsn(GOOD.replace("sslmode=verify-full", "sslmode=require"))
        self.assertEqual(str(ctx.exception), "TLS_VERIFY_FULL_REQUIRED")

    def test_config_code_for_database_role(self):
        with self.assertRaises(ConfigurationError) as ctx:
            validate_dsn(GOOD.replace("isl_agent_staging_limited", "investment_lab_owner"))
        self.assertEqual(str(ctx.exception), "ROLE_MISMATCH")

    def test_diagnostics_never_log_password_or_dsn(self):
        private_synthetic = GOOD.replace("nonsecret-ci-dummy", "do-not-print-this")
        wrong_tls = private_synthetic.replace("sslmode=verify-full", "sslmode=require")
        out = StringIO()
        with patch.dict("os.environ", {"NEON_DATABASE_URL": wrong_tls}):
            with redirect_stderr(out):
                self.assertEqual(main(), 2)
        self.assertEqual(out.getvalue().strip(),
                         "STAGING_PREFLIGHT_CONFIG: TLS_VERIFY_FULL_REQUIRED")
        self.assertNotIn("do-not-print-this", out.getvalue())
        self.assertNotIn(EXPECTED_HOST, out.getvalue())

    def test_postgres_uses_system_ca_bundle_for_hostname_verification(self):
        with patch("psycopg.connect", side_effect=RuntimeError("no-network-test")) as connect:
            with self.assertRaises(RuntimeError):
                check_connection(GOOD)
            self.assertEqual(connect.call_args.kwargs["sslmode"], "verify-full")
            self.assertEqual(connect.call_args.kwargs["sslrootcert"],
                             "/etc/ssl/certs/ca-certificates.crt")
            self.assertIn("default_transaction_read_only=on",
                          connect.call_args.kwargs["options"])

    def test_tls_error_emits_fixed_code_without_sensitive_details(self):
        from psycopg import OperationalError
        error = OperationalError("root certificate file: synthetic-hidden-host: fake-password")
        self.assertEqual(classify_operational_error(error), "TLS_CERTIFICATE_FAILED")
        out = StringIO()
        with patch.dict("os.environ", {"NEON_DATABASE_URL": GOOD}):
            with patch("psycopg.connect", side_effect=error):
                with redirect_stderr(out):
                    self.assertEqual(main(), 2)
        self.assertEqual(out.getvalue().strip(),
                         "STAGING_PREFLIGHT_CONNECT: TLS_CERTIFICATE_FAILED")
        self.assertNotIn("fake-password", out.getvalue())
        self.assertNotIn("synthetic-hidden-host", out.getvalue())

    def test_auth_error_emits_fixed_code(self):
        from psycopg import OperationalError
        error = OperationalError("password authentication failed for user 'fictional'")
        self.assertEqual(classify_operational_error(error), "AUTHENTICATION_FAILED")
        out = StringIO()
        with patch.dict("os.environ", {"NEON_DATABASE_URL": GOOD}):
            with patch("psycopg.connect", side_effect=error):
                with redirect_stderr(out):
                    self.assertEqual(main(), 2)
        self.assertEqual(out.getvalue().strip(),
                         "STAGING_PREFLIGHT_CONNECT: AUTHENTICATION_FAILED")

    def test_read_only_staging_session_succeeds_without_backend_ssl_flag(self):
        # Neon may terminate TLS at its proxy. This test confirms the driver
        # enforces verify-full while server-side pg_stat_ssl isn't a gate.
        class StubCursor:
            def __init__(self):
                self.queries = []
                self.last_sql = ""

            def __enter__(self): return self
            def __exit__(self, *exc): return False

            def execute(self, sql, params=None):
                self.last_sql = sql
                self.queries.append((sql, params))

            def fetchone(self):
                if "FROM pg_roles AS r WHERE r.rolname = current_user" in self.last_sql:
                    return ("isl_agent_staging_limited", "investment_lab", "on",
                            False, False, False, False, False, False, False, False,
                            True, False, True, False, True, True, False, False,
                            True, True, True, False, False)
                if "agent_cycles WHERE run_key" in self.last_sql:
                    return (1,)
                if "agent_paper_decisions " in self.last_sql:
                    return (3,)
                if "prices_asof" in self.last_sql:
                    return (0,)
                raise AssertionError("Unknown test SQL")

        class StubConnection:
            def __init__(self):
                self.cursor_obj = StubCursor()
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def cursor(self): return self.cursor_obj

        db = StubConnection()
        with patch("psycopg.connect", return_value=db) as connect:
            result = check_connection(GOOD)
        self.assertEqual(result["status"], "READ_ONLY_TLS_VALIDATED")
        self.assertEqual(result["writes"], 0)
        self.assertEqual(result["real_orders"], 0)
        self.assertEqual(connect.call_args.kwargs["sslmode"], "verify-full")
        self.assertEqual(connect.call_args.kwargs["sslrootcert"],
                         "/etc/ssl/certs/ca-certificates.crt")
        self.assertFalse(any("pg_stat_ssl" in q for q, _ in db.cursor_obj.queries))
        self.assertTrue(any("SET TRANSACTION READ ONLY" in q
                            for q, _ in db.cursor_obj.queries))

    def test_overprivileged_role_fails_with_same_read_only_staging_mock(self):
        class PermissionCursor:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def execute(self, sql, params=None): pass
            def fetchone(self):
                return ("isl_agent_staging_limited", "investment_lab", "on",
                        False, False, False, False, False, False, False, True,
                        True, False, True, False, True, True, False, False,
                        True, True, True, False, False)

        class PermissionConnection:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def cursor(self): return PermissionCursor()

        with patch("psycopg.connect", return_value=PermissionConnection()):
            with self.assertRaisesRegex(RuntimeError, "permissions"):
                check_connection(GOOD)

    def test_fail_before_any_network_request(self):
        with patch("psycopg.connect") as connect:
            with self.assertRaises(ValueError):
                check_connection(GOOD.replace("isl_agent_staging_limited", "neon_superuser"))
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
