from fabric_client import _build_sql, _validate_row


class TestValidateRow:
    def test_clean_row_no_warnings(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "MAXWC001",
            "line_volume_cf": 5.20,
            "line_weight_lbs": 10.0,
            "short_description": "710705-152",
        }
        assert _validate_row(row) == []

    def test_null_volume_warning(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "X",
            "line_volume_cf": None,
            "line_weight_lbs": 10.0,
            "short_description": "SKU",
        }
        warnings = _validate_row(row)
        assert any("volume" in w.lower() for w in warnings)

    def test_null_weight_warning(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "X",
            "line_volume_cf": 5.0,
            "line_weight_lbs": None,
            "short_description": "SKU",
        }
        warnings = _validate_row(row)
        assert any("weight" in w.lower() for w in warnings)

    def test_missing_sku_warning(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "X",
            "line_volume_cf": 5.0,
            "line_weight_lbs": 10.0,
            "short_description": "",
        }
        warnings = _validate_row(row)
        assert any("sku" in w.lower() for w in warnings)

    def test_null_sku_warning(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "X",
            "line_volume_cf": 5.0,
            "line_weight_lbs": 10.0,
            "short_description": None,
        }
        warnings = _validate_row(row)
        assert any("sku" in w.lower() for w in warnings)

    def test_multiple_issues_returns_all_warnings(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "X",
            "line_volume_cf": None,
            "line_weight_lbs": None,
            "short_description": "",
        }
        warnings = _validate_row(row)
        assert len(warnings) == 3


class TestBuildSql:
    def test_injects_customers_and_batches(self, config):
        sql = _build_sql(config)
        assert "'0010033'" in sql
        assert "'0010174'" in sql
        assert "'0005505'" in sql
        assert "'WH ORDER REVIEW'" in sql
        assert "'WH NEW ORDER'" in sql

    def test_excludes_voided_orders(self, config):
        sql = _build_sql(config)
        assert "VOIDSTTS = 0" in sql

    def test_returns_string(self, config):
        sql = _build_sql(config)
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_contains_required_joins(self, config):
        sql = _build_sql(config)
        assert "SALESDOC_HEADER" in sql
        assert "SALESDOC_DETAIL" in sql
        assert "WDS_Items_Current" in sql
