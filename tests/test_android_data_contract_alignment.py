from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_android_schema_contract_and_unit_test_are_aligned():
    contract = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataContract.java").read_text(encoding="utf-8")
    test = (ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/data/DataContractTest.java").read_text(encoding="utf-8")

    assert "MIN_SUPPORTED_SCHEMA_VERSION = 9" in contract
    assert "MAX_SUPPORTED_SCHEMA_VERSION = 10" in contract
    assert "assertFalse(DataContract.supportsSchema(8))" in test
    assert "assertTrue(DataContract.supportsSchema(9))" in test
    assert "assertTrue(DataContract.supportsSchema(10))" in test
    assert "assertFalse(DataContract.supportsSchema(11))" in test
