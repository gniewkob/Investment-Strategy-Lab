"""Strict offline tests. All URLs use a fake password and never connect."""
import unittest
from io import StringIO
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.staging_preflight import validate_dsn, check_connection, main, ConfigurationError, EXPECTED_HOST

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

    def test_fail_before_any_network_request(self):
        with patch("psycopg.connect") as connect:
            with self.assertRaises(ValueError):
                check_connection(GOOD.replace("isl_agent_staging_limited", "neon_superuser"))
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
