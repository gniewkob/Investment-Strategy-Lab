"""Offline guard tests. No real Neon connection or secret material."""
import unittest
from unittest.mock import patch

from src.isl_v2.staging_healthcheck import validate_target, check_connection


# This literal is an inert example for parsing tests. It cannot authenticate.
VALID = (
    "postgresql://isl_agent_staging_limited:ci-placeholder-not-real@"
    "ep-synthetic.eu-central-1.aws.neon.tech/investment_lab?sslmode=verify-full"
)


class StagingConnectionGuardTests(unittest.TestCase):
    def test_explicit_neon_staging_url_allowed(self):
        validate_target(VALID)

    def test_missing_secret_fails_closed(self):
        with self.assertRaises(ValueError):
            validate_target("")

    def test_owner_role_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace("isl_agent_staging_limited", "investment_lab_owner"))

    def test_main_user_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace("isl_agent_staging_limited", "isl_agent_prod_login"))

    def test_wrong_database_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace("/investment_lab?", "/postgres?"))

    def test_external_host_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace("ep-synthetic.eu-central-1.aws.neon.tech", "example.org"))

    def test_multiple_hosts_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace("ep-synthetic.eu-central-1.aws.neon.tech",
                                          "ep-synthetic.eu-central-1.aws.neon.tech,evil.org"))

    def test_direct_ip_host_override_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID + "&hostaddr=127.0.0.1")

    def test_weak_tls_mode_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace("sslmode=verify-full", "sslmode=require"))

    def test_no_password_rejected(self):
        with self.assertRaises(ValueError):
            validate_target(VALID.replace(":ci-placeholder-not-real@", "@"))

    def test_invalid_target_rejected_before_psycopg_connect(self):
        with patch("psycopg.connect") as connect:
            with self.assertRaises(ValueError):
                check_connection(VALID.replace("isl_agent_staging_limited", "investment_lab_owner"))
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
