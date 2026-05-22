from food_order_bot.agents.food_request import FoodRequestAnalyzer
from food_order_bot.models import SwiggySurface


def test_hinglish_food_request_extracts_query_quantity_and_budget() -> None:
    request = FoodRequestAnalyzer().analyze(
        "2 chappati and aalo gobi kii sabji an dsome minm rate"
    )

    assert request.surface == SwiggySurface.FOOD
    assert request.query == "chapati aloo gobi sabzi"
    assert request.quantities == {"chapati": 2}
    assert request.budget_preference == "minimum_price"


def test_instamart_request_routes_to_instamart() -> None:
    request = FoodRequestAnalyzer().analyze("instamart milk bread cheap")

    assert request.surface == SwiggySurface.INSTAMART
    assert request.query == "instamart milk bread"
