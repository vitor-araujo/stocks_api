from datetime import datetime, timedelta

from flask import jsonify, request

from app.services import get_stock_data, update_stock_amount


def setup_routes(app):
    @app.route("/stock/<string:stock_symbol>", defaults={"date": None}, methods=["GET"])
    @app.route("/stock/<string:stock_symbol>/<string:date>", methods=["GET"])
    def get_stock(stock_symbol, date):
        if date:
            try:
                # Validate date format
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
        else:
            # Default to yesterday if no date is provided
            yesterday = datetime.now() - timedelta(days=1)
            date = yesterday.strftime("%Y-%m-%d")

        stock_data = get_stock_data(stock_symbol, date)
        return jsonify(stock_data)

    @app.route("/stock/<string:stock_symbol>", methods=["POST"])
    def post_stock(stock_symbol):
        data = request.get_json()
        if data is None:
            return jsonify({"error": "Request body must be JSON."}), 400

        amount = data.get("amount")

        # Validations
        if not isinstance(stock_symbol, str) or not stock_symbol:
            return (
                jsonify(
                    {
                        "error": "Please provide a valid stock symbol as a non-empty string."
                    }
                ),
                400,
            )
        if len(stock_symbol) > 5:
            return (
                jsonify(
                    {
                        "error": f"Stock symbol must be 5 characters or less. You sent: {stock_symbol}"
                    }
                ),
                400,
            )

        if amount is None:
            return jsonify({"error": "Amount is required."}), 400
        if not isinstance(amount, (int, float)):
            return (
                jsonify(
                    {
                        "error": f"Amount must be a number. You sent: {amount} ({type(amount).__name__})"
                    }
                ),
                400,
            )

        update_stock_amount(stock_symbol, amount)
        return (
            jsonify(
                {
                    "message": f"{amount} units of stock {stock_symbol} were added to your stock record"
                }
            ),
            201,
        )
