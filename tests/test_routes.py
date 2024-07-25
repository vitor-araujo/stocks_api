import pytest
from app.main import create_app
from flask import json


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_get_stock(client):
    response = client.get("/stock/AAPL")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "company_code" in data


def test_get_stock_with_date(client):
    response = client.get("/stock/AAPL/2024-05-01")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "company_code" in data


def test_get_stock_invalid_date(client):
    response = client.get("/stock/AAPL/invalid-date")
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Invalid date format. Use YYYY-MM-DD."


def test_post_stock(client):
    response = client.post("/stock/AAPL", json={"amount": 10})
    assert response.status_code == 201
    data = json.loads(response.data)
    assert "message" in data


def test_post_stock_negative_amount(client):
    response = client.post("/stock/AAPL", json={"amount": -10})
    assert response.status_code == 201
    data = json.loads(response.data)
    assert "message" in data


def test_post_stock_no_amount(client):
    response = client.post("/stock/AAPL", json={})
    assert response.status_code == 400


def test_post_stock_invalid_symbol(client):
    response = client.post("/stock/LONGERTHANUSUALSTOCK", json={"amount": 10})
    assert response.status_code == 400
