from app.services import get_stock_data, update_stock_amount


def test_get_stock_data():
    stock = get_stock_data("AAPL", "2024-05-01")
    assert stock["company_code"] == "AAPL"
    assert stock["company_name"] != ""
    assert stock["status"] == "active"
    assert stock["purchased_amount"] >= 0
    assert stock["purchased_status"] == "confirmed"


def test_add_stock_amount():

    # Add
    result = update_stock_amount("YELP", 100)
    assert result["success"] is True


def test_subtract_stock_amount():

    # Subtract
    result = update_stock_amount("YELP", -50)
    assert result["success"] is True


def test_negative_stock_amount():
    # Set the purchased_amount to a negative value, which should result in zero
    result = update_stock_amount("YELP", -20000)
    assert result["success"] is True
