"""Offline, no-network tests for DataCite DOI provenance; no market data."""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts import swinkels_datacite_doi_lineage_v01 as s


def records():
    shared = {
        "creators": [{"name": s.AUTHOR}],
        "titles": [{"title": s.TITLE}],
        "rightsList": [{"rightsIdentifier": "cc-by-4.0"}],
    }
    old = {"data": {"attributes": {
        **deepcopy(shared),
        "doi": s.HISTORIC_DOI,
        "url": "https://doi.org/" + s.CURRENT_DOI.upper(),
        "publicationYear": 2023,
        "sizes": ["1040468 Bytes"],
        "relatedIdentifiers": [
            {"relationType": "IsIdenticalTo",
             "relatedIdentifierType": "DOI",
             "relatedIdentifier": s.HISTORIC_BASE_DOI}],
    }}}
    new = {"data": {"attributes": {
        **deepcopy(shared),
        "doi": s.CURRENT_DOI,
        "publicationYear": 2025,
        "sizes": ["913425", "127043"],
        "version": "1.0",
        "dates": [{"dateType": "Available", "date": "2025-08-22"}],
        "alternateIdentifiers": [
            {"alternateIdentifier": "https://doi.org/" + s.HISTORIC_BASE_DOI}],
    }}}
    return old, new


class SourceDOILineageTests(unittest.TestCase):
    def rejected(self, code, change):
        old, new = records()
        change(old, new)
        with self.assertRaisesRegex(s.CrosswalkBlocked, code):
            s.audit(old, new)

    def test_primary_metadata_linkage_without_asserting_byte_identity(self):
        old, new = records()
        receipt = s.audit(old, new)
        self.assertTrue(receipt["metadata_doi_and_author_lineage_confirmed"])
        self.assertTrue(receipt["package_size_match"])
        self.assertEqual(receipt["historic_package_size"], 1040468)
        self.assertEqual(sum(receipt["current_original_file_sizes"]), 1040468)
        self.assertFalse(receipt["old_v6_and_new_dataverse_bytes_identical"])
        self.assertFalse(receipt["historical_pit_certified"])
        self.assertFalse(receipt["first_available_at_for_historic_months_confirmed"])
        self.assertEqual(receipt["qualified_model_series"], [])
        self.assertEqual(receipt["financial_operations"], 0)
        self.assertEqual(receipt["model_state"], "HOLD_CASH")

    def test_legacy_version_identity(self):
        self.rejected("DOI_IDENTITY_MISMATCH", lambda a, b:
                      a["data"]["attributes"].update(doi=s.HISTORIC_BASE_DOI))

    def test_new_dataset_identity(self):
        self.rejected("DOI_IDENTITY_MISMATCH", lambda a, b:
                      b["data"]["attributes"].update(doi="10.34894/other"))

    def test_publication_chain_must_be_direct_from_data_cite(self):
        self.rejected("PUBLISHER_DOI_CROSSWALK_MISSING", lambda a, b:
                      a["data"]["attributes"].update(url="https://example.org"))

    def test_old_related_record_cannot_be_replaced_with_only_title_match(self):
        self.rejected("PUBLISHER_DOI_CROSSWALK_MISSING", lambda a, b:
                      a["data"]["attributes"].update(relatedIdentifiers=[]))

    def test_new_alternate_identifier_required(self):
        self.rejected("PUBLISHER_DOI_CROSSWALK_MISSING", lambda a, b:
                      b["data"]["attributes"].update(alternateIdentifiers=[]))

    def test_same_title_and_creator_required(self):
        self.rejected("PUBLISHER_TITLE_AUTHOR_MISMATCH", lambda a, b:
                      b["data"]["attributes"].update(creators=[{"name":"Other"}]))

    def test_licence_not_inferred_from_public_doi(self):
        self.rejected("PUBLISHER_CCBY_LICENSE_MISSING", lambda a, b:
                      a["data"]["attributes"].update(rightsList=[]))

    def test_historical_package_size_mismatch(self):
        self.rejected("PUBLISHER_PACKAGE_SIZE_MISMATCH", lambda a, b:
                      a["data"]["attributes"].update(sizes=["1040469 Bytes"]))

    def test_current_single_file_size_mismatch(self):
        self.rejected("PUBLISHER_PACKAGE_SIZE_MISMATCH", lambda a, b:
                      b["data"]["attributes"].update(sizes=["913426","127042"]))

    def test_do_not_use_version_label_to_prove_historic_pit(self):
        self.rejected("PUBLISHER_VERSION_CHRONOLOGY_MISMATCH", lambda a, b:
                      b["data"]["attributes"].update(version="6.0"))

    def test_migration_release_date_is_different_from_historic_observation(self):
        self.rejected("PUBLISHER_RELEASE_DATE_MISSING", lambda a, b:
                      b["data"]["attributes"].update(dates=[
                          {"dateType": "Available", "date":"2022-12-31"}]))

    def test_unapproved_metadata_endpoint_refused_before_network(self):
        with self.assertRaisesRegex(s.CrosswalkBlocked, "UNAUTHORIZED_METADATA_URL"):
            s.fetch_doi_metadata("https://example.org/claim-source")

    def test_malformed_response_never_assumed_accepted(self):
        with self.assertRaisesRegex(s.CrosswalkBlocked, "DOI_METADATA_MISSING"):
            s.audit({}, records()[1])


if __name__ == "__main__":
    unittest.main()
