from sdb_reader.schema import (
    SafetyDataSheet,
)


def test_safety_data_sheet_defaults() -> None:
    sheet = SafetyDataSheet(
        product_identifier=None,
        issue_date=None,
        revision_date=None,
        version=None,
        language="de",
    )

    assert sheet.hazard_statements.hazard_codes == []
    assert sheet.contact_info.supplier_name is None
    assert sheet.section_text == {}
