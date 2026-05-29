import os
import sys

import pytest

# Allow imports from jordan_automation/ when running pytest from that directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def config():
    return {
        "fabric": {
            "endpoint": "test.fabric.microsoft.com",
            "database": "Gold",
            "tenant_id": "test-tenant-id",
            "auth_mode": "service_principal",
        },
        "jordan_customers": ["0010033", "0010174", "0005505"],
        "qualifying_batches": ["WH ORDER REVIEW", "WH NEW ORDER"],
        "threshold": {"volume_cf": 2200},
        "schedule": {
            "interval_days": 14,
            "skip_window_after_threshold_days": 3,
        },
        "inbound": {
            "no_response_window_days": 2,
            "jordan_reply_addresses": ["bchartier@jordans.com", "traffic@jordans.com"],
        },
        "email": {
            "to": "traffic@jordans.com",
            "cc": ["bchartier@jordans.com", "rszewczyk@maxwoodfurniture.com"],
            "from": "logistics@maxwoodfurniture.com",
            "internal_notify": ["hcollins@maxwoodfurniture.com"],
        },
        "paths": {
            "state_file": "state.json",
            "log_file": "jordan_automation.log",
        },
    }


@pytest.fixture
def empty_state():
    return {
        "last_threshold_send": None,
        "last_scheduled_send": None,
        "last_reminder_sent": None,
        "last_run": None,
        "jordan_reply_received": False,
        "reminder_sent": False,
        "orders_at_last_threshold_send": [],
        "volume_at_last_threshold_send": None,
    }


@pytest.fixture
def sample_order_lines():
    return [
        {
            "sales_doc_num": "WH00121966",
            "cust_po_num": "MAXWC0309600B",
            "short_description": "710705-152",
            "item_description": "Bed Side Rails incl. Support Bar (Full)",
            "qty": 4.0,
            "volume_cf_per_unit": 1.30,
            "line_volume_cf": 5.20,
            "weight_per_unit": 2.10,
            "line_weight_lbs": 8.40,
            "cartons_per_unit": 1,
            "line_cartons": 4,
        },
        {
            "sales_doc_num": "WH00121967",
            "cust_po_num": "MAXWC0309601A",
            "short_description": "710331-131",
            "item_description": "Full Slat HeadBoard & FootPanel incl. Slat Roll",
            "qty": 1.0,
            "volume_cf_per_unit": 11.90,
            "line_volume_cf": 11.90,
            "weight_per_unit": 85.0,
            "line_weight_lbs": 85.0,
            "cartons_per_unit": 1,
            "line_cartons": 1,
        },
    ]
