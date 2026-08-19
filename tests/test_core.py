from __future__ import annotations

import unittest

from keplerset.exporters import apply_3le_aliases, decode_tle_catalog_field, parse_satellite_list
from keplerset.models import ElementSetProfile, SatelliteEntry
from keplerset.satcat import SatcatRecord, SatcatSearch, search_satcat
from keplerset.spacetrack import SpaceTrackClient


class Alpha5Tests(unittest.TestCase):
    def test_decode_numeric(self):
        self.assertEqual(decode_tle_catalog_field("25544"), 25544)

    def test_decode_alpha5(self):
        self.assertEqual(decode_tle_catalog_field("A0000"), 100000)
        self.assertEqual(decode_tle_catalog_field("E8493"), 148493)
        self.assertEqual(decode_tle_catalog_field("J2931"), 182931)
        self.assertEqual(decode_tle_catalog_field("P4018"), 234018)
        self.assertEqual(decode_tle_catalog_field("W1928"), 301928)
        self.assertEqual(decode_tle_catalog_field("Z9999"), 339999)


class AliasTests(unittest.TestCase):
    def test_3le_alias(self):
        source = (
            "ISS (ZARYA)\n"
            "1 25544U 98067A   24001.00000000  .00000000  00000-0  00000-0 0  9999\n"
            "2 25544  51.6400  10.0000 0001000  20.0000  30.0000 15.50000000123456\n"
        )
        profile = ElementSetProfile(
            name="test",
            format="3le",
            output_path="x.txt",
            satellites=[SatelliteEntry(25544, "ISS")],
        )
        out = apply_3le_aliases(source, profile)
        self.assertTrue(out.startswith("ISS\r\n1 25544"))
        self.assertIn("2 25544", out)


class ParserTests(unittest.TestCase):
    def test_parse_list(self):
        rows = parse_satellite_list("25544 ISS\n43017,AO-91\n#comment\n")
        self.assertEqual(rows, [(25544, "ISS"), (43017, "AO-91")])


class QueryTests(unittest.TestCase):
    def test_gp_url(self):
        url = SpaceTrackClient.build_gp_query_url([25544, 43017], "3le")
        self.assertIn("/class/gp/NORAD_CAT_ID/25544,43017/", url)
        self.assertIn("/orderby/NORAD_CAT_ID%20asc/format/3le/", url)
        self.assertTrue(url.endswith("emptyresult/show"))

    def test_satcat_url_uses_one_current_catalog_query(self):
        url = SpaceTrackClient.build_satcat_query_url()
        self.assertIn("/class/satcat/CURRENT/Y/", url)
        self.assertIn("/orderby/NORAD_CAT_ID%20asc/", url)
        self.assertTrue(url.endswith("format/json/emptyresult/show"))


class SatcatTests(unittest.TestCase):
    @staticmethod
    def _records():
        return [
            SatcatRecord(
                25544,
                "ISS (ZARYA)",
                "1998-067A",
                "PAYLOAD",
                "ISS",
                "1998-11-20",
                "",
                92.9,
                51.64,
                420,
                410,
            ),
            SatcatRecord(
                43017,
                "AO-91",
                "2017-073E",
                "PAYLOAD",
                "US",
                "2017-11-18",
                "",
                97.5,
                97.7,
                800,
                780,
            ),
            SatcatRecord(
                12345,
                "OLD DEBRIS",
                "1981-001Z",
                "DEBRIS",
                "US",
                "1981-01-01",
                "2001-02-03",
                100.0,
                60.0,
                1000,
                100,
            ),
        ]

    def test_from_api_accepts_current_satcat_fields(self):
        record = SatcatRecord.from_api(
            {
                "NORAD_CAT_ID": "25544",
                "OBJECT_NAME": "ISS (ZARYA)",
                "OBJECT_ID": "1998-067A",
                "OBJECT_TYPE": "PAYLOAD",
                "COUNTRY": "ISS",
                "LAUNCH": "1998-11-20",
                "DECAY": None,
                "PERIOD": "92.90",
                "INCLINATION": "51.64",
                "CURRENT": "Y",
            }
        )
        self.assertEqual(record.norad_cat_id, 25544)
        self.assertTrue(record.on_orbit)
        self.assertAlmostEqual(record.inclination or 0, 51.64)

    def test_name_search(self):
        result = search_satcat(self._records(), SatcatSearch(text="ao-91"), limit=None)
        self.assertEqual([r.norad_cat_id for r in result], [43017])

    def test_filter_type_and_inclination(self):
        result = search_satcat(
            self._records(),
            SatcatSearch(object_type="PAYLOAD", inclination_min=90),
            limit=None,
        )
        self.assertEqual([r.norad_cat_id for r in result], [43017])

    def test_on_orbit_filter_excludes_decayed(self):
        result = search_satcat(self._records(), SatcatSearch(on_orbit_only=True), limit=None)
        self.assertNotIn(12345, [r.norad_cat_id for r in result])

    def test_numeric_search_prioritizes_exact_catalog_number(self):
        result = search_satcat(self._records(), SatcatSearch(text="25544"), limit=None)
        self.assertEqual(result[0].norad_cat_id, 25544)


if __name__ == "__main__":
    unittest.main()
